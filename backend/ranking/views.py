"""As views do ranking: o que o jogo fala com o backend.

Uma API de duas operacoes, que e tudo que o cliente precisa:

    GET  /api/ranking/       devolve o ranking, do melhor para o pior
    POST /api/ranking/       grava uma partida terminada

Sobre CSRF
----------
A protecao contra CSRF do Django existe porque um NAVEGADOR carrega
cookies sozinho ao fazer um POST. Um cliente Python nao faz isso: o
`requests` nao tem cookie nenhum, entao o CSRF nao teria o que
validar — mas o Django checa a protecao antes de olhar o cliente, e
devolve 403 para quem nao manda o token.

Por isso a view de POST e `csrf_exempt`. Nao e um buraco: e
reconhecer que o cliente nao e um navegador, e portanto nao pode ser
victima de CSRF. Se algum dia o endpoint for chamado de uma pagina web,
essa linha e a que precisa sumir e o token voltar a valer.

Sobre validacao
---------------
`ModelForm` e usado de proposito, mesmo sendo um POST de JSON. Ele da
validacao de campo (tempo negativo, nome de 100 caracteres) com uma
linha, e devolve os erros no mesmo formato de JSON — em vez de uma
pagina HTML de erro, que o cliente teria que adivinhar.
"""
from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Ranking

ROTULOS = {
    "nome": "nome",
    "tempo": "tempo",
    "inimigos_derrotados": "inimigos derrotados",
    "pontuacao": "pontuacao",
}


def _erros_em_texto(erro: ValidationError) -> str:
    """Junta os erros de validacao em uma frase, um por linha.

    O `ValidationError` do Django guarda os erros por campo, e o
    `str()` dele devolve o dicionario inteiro. Para uma API, a resposta
    precisa ser lida por um humano no jogo: "nome: este campo nao pode
    estar vazio" diz o que aconteceu; o dict nao diz.
    """
    if hasattr(erro, "message_dict"):
        partes = [
            f"{ROTULOS.get(campo, campo)}: {'; '.join(mensagens)}"
            for campo, mensagens in erro.message_dict.items()
        ]
    else:
        partes = list(erro.messages)

    return " | ".join(partes) if partes else "dados invalidos"

# Quantas linhas o ranking devolve por padrao.
#
# O limite existe por um motivo concreto: `ordering = ["-pontuacao",
# "tempo"]` faz o banco ORDENAR antes de cortar, e ordenar tudo sem
# necessidade fica caro conforme a tabela cresce. Nenhum cliente precisa
# de dez mil linhas.
LIMITE_PADRAO = 20
LIMITE_MAXIMO = 100


def listar_ranking(request):
    """GET /api/ranking/ — o ranking, do melhor para o pior.

    A ordem vem do `Meta.ordering` do model, e nao e passada aqui. Duplicar
    a regra de ordenacao em dois lugares e a forma de o admin e a API
    divergirem sem ninguem perceber.
    """
    # `?limite=50` no endereco. O valor vem do cliente, entao precisa de
    # teto: sem ele, `?limite=999999` traz a tabela inteira.
    try:
        limite = int(request.GET.get("limite", LIMITE_PADRAO))
    except (TypeError, ValueError):
        return JsonResponse(
            {"erro": "o parametro 'limite' tem de ser um numero inteiro"},
            status=400,
        )

    limite = max(1, min(limite, LIMITE_MAXIMO))

    linhas = Ranking.objects.all()[:limite]

    return JsonResponse(
        {
            "quantidade": linhas.count(),
            "ranking": [
                {
                    "posicao": posicao,
                    "nome": linha.nome,
                    "pontuacao": linha.pontuacao,
                    "tempo": linha.tempo,
                    "inimigos_derrotados": linha.inimigos_derrotados,
                    "criado_em": linha.criado_em.isoformat(),
                }
                for posicao, linha in enumerate(linhas, start=1)
            ],
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def registrar_partida(request):
    """POST /api/ranking/ — grava uma partida terminada.

    Corpo esperado (JSON):

        {
            "nome": "John",
            "tempo": 431,
            "inimigos_derrotados": 12,
            "pontuacao": 8400
        }

    Devolve 201 com a linha gravada, ou 400 com o que estava errado.
    """
    if request.method != "POST":
        return JsonResponse(
            {"erro": "use POST para gravar uma partida"}, status=405
        )

    # O `import json` fica no topo do arquivo. Um import dentro de funcao
    # e executado a cada chamada: o modulo ja esta em cache depois da
    # primeira, entao o custo e proximo de zero, mas o que incomoda e a
    # leitura — quem le o arquivo nao ve de relance que ele depende de
    # `json`.
    try:
        corpo = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        return JsonResponse({"erro": f"JSON invalido: {erro}"}, status=400)

    if not isinstance(corpo, dict):
        # Uma lista ou um numero no lugar do objeto. Sem esta checagem, o
        # codigo abaixo quebraria com AttributeError ao chamar `.get` —
        # e o cliente receberia um 500 em vez de um 400 explicando o que
        # ele mandou de errado.
        return JsonResponse(
            {"erro": "o corpo tem de ser um objeto JSON"}, status=400
        )

    linha = Ranking(
        nome=corpo.get("nome", ""),
        tempo=corpo.get("tempo", 0),
        inimigos_derrotados=corpo.get("inimigos_derrotados", 0),
        pontuacao=corpo.get("pontuacao", 0),
    )

    # `full_clean` roda a validacao do model: tipos, tamanho do nome,
    # valores negativos. Sem ele, `save()` grava qualquer coisa e o erro
    # so aparece quando alguem tenta ler de volta.
    try:
        linha.full_clean()
    except ValidationError as erro:
        # O ValidationError do Django guarda os erros POR CAMPO, e o
        # `str()` dele devolve o dicionario inteiro:
        #     {'nome': ['Este campo nao pode estar vazio.']}
        #
        # Mandar isso para o cliente seria mandar repr de Python como
        # mensagem de erro. Quem le vai ver chaves e listas, nao uma
        # frase. A lista abaixo junta em texto, um erro por linha.
        #
        # A excecao NAO e capturada aqui como `Exception`: capturar a
        # classe base esconderia bug de verdade (AttributeError,
        # TypeError) dentro de um "erro de validacao" que nao existe.
        return JsonResponse(
            {"erro": _erros_em_texto(erro)}, status=400
        )

    linha.save()

    return JsonResponse(
        {
            "id": linha.id,
            "nome": linha.nome,
            "tempo": linha.tempo,
            "inimigos_derrotados": linha.inimigos_derrotados,
            "pontuacao": linha.pontuacao,
        },
        status=201,
        json_dumps_params={"ensure_ascii": False},
    )