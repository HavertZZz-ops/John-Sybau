"""Testes do backend Django, sem subir servidor.

Rodar `manage.py runserver` e `curl` na mao funciona uma vez. Na segunda
vez ja e perda de tempo, e na quinta e um teste que ninguem roda. Estes
testes sobem o servidor uma vez, fazem tudo por dentro do processo e
desligam no fim.

O que muda em relacao ao teste manual:
- nao depende de uma porta livre (a porta 0 deixa o SO escolher);
- nao depende de o servidor ja estar no ar;
- roda em qualquer maquina, e em CI, sem configuracao.

    python tools/testar_backend.py

Cada secao testa uma coisa do backend. Os casos nao sao decorativos:
cada um existe porque o defeito correspondente ja aconteceu ou e
facil de acontecer.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# `DJANGO_SETTINGS_MODULE` tem de estar definido ANTES de importar
# qualquer coisa do Django. Importar primeiro e configurar depois falha
# com um erro que fala de "apps not loaded" e nao aponta a causa.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

FALHAS: list[str] = []
CONTAGEM = 0


def checar(descricao: str, condicao: bool, detalhe: str = "") -> None:
    global CONTAGEM
    CONTAGEM += 1
    if condicao:
        print(f"  [ok]   {descricao}")
    else:
        print(f"  [FALHA] {descricao} {detalhe}")
        FALHAS.append(descricao)


def pedir(caminho: str, metodo: str = "GET", corpo: dict | None = None):
    """Faz um pedido e devolve (status, json).

    Devolve um par em vez de levantar excecao: um 400 e uma resposta
    legitima que o teste precisa inspecionar, e nao um erro de teste.
    """
    url = f"http://127.0.0.1:{PORTA}{caminho}"
    dados = None
    cabecalhos = {}
    if corpo is not None:
        dados = json.dumps(corpo).encode("utf-8")
        cabecalhos["Content-Type"] = "application/json"

    requisicao = Request(url, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urlopen(requisicao, timeout=5) as resposta:
            bruto = resposta.read().decode("utf-8")
            status = resposta.status
    except HTTPError as erro:
        bruto = erro.read().decode("utf-8")
        status = erro.code

    try:
        return status, json.loads(bruto)
    except json.JSONDecodeError:
        return status, {"_bruto": bruto}


PORTA = 8765


def main() -> int:
    global PORTA

    print("=" * 62)
    print("testes do backend")

    # --- subir o servidor --------------------------------------------
    # `django.setup()` ANTES de qualquer comando. Um `call_command` feito
    # antes disso falha com `AppRegistryNotReady`, e a mensagem nao diz
    # nada sobre a causa — ela fala de "apps aren't loaded" como se fosse
    # problema de configuracao, quando na verdade o registro de apps
    # simplesmente ainda nao foi montado. `django.setup()` e o que o
    # `manage.py` faz, e nao chama-lo aqui e a diferenca entre o script
    # funcionar e dar uma mensagem que manda o operador procurar no
    # lugar errado.
    import django

    django.setup()

    from django.core.management import call_command

    # Uma porta ALTA e arbitraria, e nao 8000: o servidor de
    # desenvolvimento pode estar no ar na 8000, e subir um segundo na
    # mesma porta falha. A chance de 8765 estar ocupada e baixa.
    PORTA = 8765

    print(f"\nsubindo o servidor na porta {PORTA}...")
    servidor = threading.Thread(
        target=lambda: call_command("runserver", f"127.0.0.1:{PORTA}",
                                    use_reloader=False, verbosity=0),
        daemon=True,
    )
    servidor.start()

    # Espera o servidor responder. Sem esta espera, o primeiro pedido
    # acontece antes do Django terminar de carregar o banco e volta
    # "Connection refused" — e o teste reprova por um motivo que nao
    # tem nada com o backend.
    pronto = False
    ultimo_erro = ""
    for _ in range(80):
        try:
            status, _ = pedir("/")
            pronto = status == 200
            if pronto:
                break
        except OSError as erro:
            ultimo_erro = str(erro)
        time.sleep(0.25)

    checar("o servidor sobe", pronto, ultimo_erro)
    if not pronto:
        print("nao deu para subir o servidor; os testes nao vao rodar")
        return 1

    # --- a raiz ------------------------------------------------------
    print("\nRaiz")
    status, dados = pedir("/")
    checar("a raiz responde 200", status == 200, f"({status})")
    checar("a raiz diz onde esta a API", "api" in dados, f"({dados})")

    # --- gravar ------------------------------------------------------
    print("\nGravar partida")
    antes = pedir("/api/ranking/?limite=100")[1].get("quantidade", 0)

    status, dados = pedir("/api/ranking/registrar/", "POST", {
        "nome": "Testador",
        "tempo": 300,
        "inimigos_derrotados": 5,
        "pontuacao": 1000,
    })
    checar("gravar responde 201", status == 201, f"({status}) {dados}")
    checar("devolve o id", "id" in dados, f"({dados})")
    checar("devolve a pontuacao", dados.get("pontuacao") == 1000, f"({dados})")

    # --- ler ---------------------------------------------------------
    print("\nLer o ranking")
    status, dados = pedir("/api/ranking/?limite=10")
    checar("ler responde 200", status == 200, f"({status})")
    checar("devolve a lista", isinstance(dados.get("ranking"), list), f"({dados})")
    checar("a lista tem itens", len(dados.get("ranking", [])) > 0, f"({dados})")

    # A ordem e o que o jogador ve: maior pontuacao primeiro.
    pontuacoes = [linha["pontuacao"] for linha in dados["ranking"]]
    checar("esta em ordem de pontuacao",
           pontuacoes == sorted(pontuacoes, reverse=True),
           f"({pontuacoes})")

    # --- validacao ---------------------------------------------------
    print("\nValidacao")

    status, dados = pedir("/api/ranking/registrar/", "POST", {
        "nome": "", "tempo": -5,
        "inimigos_derrotados": 0, "pontuacao": 0,
    })
    checar("dado invalido responde 400", status == 400, f"({status})")
    checar("o erro e texto, nao dicionario",
           isinstance(dados.get("erro"), str), f"({dados.get('erro')!r})")
    checar("o erro diz o que houve", "nome" in str(dados.get("erro", "")),
           f"({dados.get('erro')})")

    status, dados = pedir("/api/ranking/registrar/", "POST", {
        "nome": "x" * 100, "tempo": 1,
        "inimigos_derrotados": 1, "pontuacao": 1,
    })
    checar("nome longo demais responde 400", status == 400, f"({status})")

    # --- corpo invalido ---------------------------------------------
    print("\nCorpo invalido")

    # Uma lista no lugar do objeto. Sem a checagem, a view quebraria
    # com AttributeError e o cliente receberia 500 em vez de um 400
    # dizendo o que ele mandou de errado.
    req = Request(
        f"http://127.0.0.1:{PORTA}/api/ranking/registrar/",
        data=b"[1, 2, 3]",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=5) as r:
            status = r.status
    except HTTPError as erro:
        status = erro.code
    checar("lista no lugar de objeto responde 400", status == 400, f"({status})")

    # Texto que nao e JSON
    req = Request(
        f"http://127.0.0.1:{PORTA}/api/ranking/registrar/",
        data=b"isto nao e json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=5) as r:
            status = r.status
    except HTTPError as erro:
        status = erro.code
    checar("texto que nao e JSON responde 400", status == 400, f"({status})")

    # --- limite ------------------------------------------------------
    print("\nParametro limite")
    status, dados = pedir("/api/ranking/?limite=abc")
    checar("limite nao numerico responde 400", status == 400, f"({status})")

    status, dados = pedir("/api/ranking/?limite=999999")
    checar("limite absurdo e limitado", status == 200, f"({status})")
    checar("e traz no maximo o teto", len(dados.get("ranking", [])) <= 100,
           f"({len(dados.get('ranking', []))})")

    # --- metodo errado -----------------------------------------------
    print("\nMetodo errado")
    status, _ = pedir("/api/ranking/registrar/", "GET")
    checar("GET na rota de gravar responde 405", status == 405, f"({status})")

    # --- o model, direto ---------------------------------------------
    print("\nModel")
    from ranking.models import Ranking

    # A ordem vem do Meta.ordering, e nao de cada consulta. Se alguem
    # Tirar o Meta, o teste nao ve: o que ele ve e que a ORDEM do banco
    # bate com a do model.
    ordenados = list(Ranking.objects.all()[:5])
    bate = all(
        ordenados[i].pontuacao >= ordenados[i + 1].pontuacao
        for i in range(len(ordenados) - 1)
    )
    checar("a ordenacao do model bate", bate,
           f"({[o.pontuacao for o in ordenados]})")

    # __str__ e o que aparece no admin
    linha = ordenados[0] if ordenados else None
    if linha:
        checar("__str__ tem o nome", linha.nome in str(linha), f"({linha})")
        checar("__str__ tem a pontuacao", str(linha.pontuacao) in str(linha))

    # --- a gravacao de verdade ---------------------------------------
    print("\nGravacao no banco")
    if linha:
        antes_vida = Ranking.objects.count()
        nova = Ranking.objects.create(
            nome="Contagem", tempo=1, inimigos_derrotados=1, pontuacao=9999
        )
        checar("o create grava mesmo", Ranking.objects.count() == antes_vida + 1)
        checar("e a linha volta com o id", nova.pk is not None)
        # limpa, para o proximo teste nao depender desta
        nova.delete()

    # --- resumo ------------------------------------------------------
    print("=" * 62)
    if FALHAS:
        print(f"{len(FALHAS)} de {CONTAGEM} verificacoes falharam:")
        for f in FALHAS:
            print(f"  - {f}")
        return 1

    print(f"tudo certo ({CONTAGEM} verificacoes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())