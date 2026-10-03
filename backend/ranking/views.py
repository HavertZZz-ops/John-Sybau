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

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Ranking

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

    try:
        dados = request.POST.dict()
    except AttributeError:
        dados = {}

    # O POST chega em JSON, e `request.POST` le formulario. Como o
    # cliente e `requests`, a forma simples e ler o corpo na mao.
    import json

    try:
        corpo = json.loads(request.body or b"{}")
        if not isinstance(corpo, dict):
            raise ValueError("o corpo tem de ser um objeto JSON")
        dados = corpo
    except (json.JSONDecodeError, ValueError) as erro:
        return JsonResponse(
            {"erro": f"JSON invalido: {erro}"}, status=400
        )

    linha = Ranking(
        nome=dados.get("nome", ""),
        tempo=dados.get("tempo", 0),
        inimigos_derrotados=dados.get("inimigos_derrotados", 0),
        pontuacao=dados.get("pontuacao", 0),
    )

    # `full_clean` roda a validacao do model: tipos, tamanho do nome,
    # valores negativos. Sem ele, `save()` grava qualquer coisa e o erro
    # so aparece quando alguem tenta ler de volta.
    try:
        linha.full_clean()
    except Exception as erro:
        return JsonResponse({"erro": str(erro)}, status=400)

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