"""Testa o backend Django de verdade: sobe o banco, grava, le e apaga.

Roda em SQLite por padrao, porque o teste precisa passar em qualquer
maquina. O caminho do Postgres e o mesmo codigo: muda so a string de
conexao em `DATABASES`. Com `DB_ENGINE=django.db.backends.postgresql` o
mesmo teste roda contra o Postgres de verdade.

    python tools/test_save_server.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SERVER))

# o banco do teste e separado: um teste nao pode mexer no save real
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")
os.environ.setdefault("DB_ENGINE", "django.db.backends.sqlite3")
if "sqlite" in os.environ["DB_ENGINE"]:
    os.environ["_TESTE_DB"] = str(SERVER / "teste.sqlite3")

import django  # noqa: E402


def main() -> int:
    from django.conf import settings as dj

    if "sqlite" in os.environ["DB_ENGINE"]:
        dj.DATABASES["default"]["NAME"] = os.environ["_TESTE_DB"]

    # o cliente de teste do Django manda Host: testserver, que nao esta
    # em ALLOWED_HOSTS (e nao deveria estar: e um host so de teste)
    if "testserver" not in dj.ALLOWED_HOSTS:
        dj.ALLOWED_HOSTS = [*dj.ALLOWED_HOSTS, "testserver"]

    django.setup()

    from django.core.management import call_command
    from django.test import Client

    banco = dj.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1]
    print(f"banco de teste: {banco}")
    print(f"nome: {dj.DATABASES['default']['NAME']}")

    client = Client()
    falhas: list[str] = []

    def checar(condicao: bool, descricao: str) -> None:
        print(f"  {'ok  ' if condicao else 'FALHA'} {descricao}")
        if not condicao:
            falhas.append(descricao)

    print("\nmigrate:")
    call_command("migrate", verbosity=0, run_syncdb=True)
    checar(True, "schema criado")

    print("\nsem save ainda:")
    resposta = client.get("/api/saves")
    checar(resposta.status_code == 200, "GET responde 200")
    checar(resposta.json().get("existe") is False, "slot vazio")

    print("\ngravando:")
    payload = {
        "area": "catacumbas",
        "x": 412.5,
        "y": 733.0,
        "direcao": "sul",
        "tempo_jogado": 61.25,
        "versao": 1,
        "extra": {"itens": 3},
    }
    resposta = client.put("/api/saves", data=json.dumps(payload),
                         content_type="application/json")
    checar(resposta.status_code == 200, "PUT responde 200")
    checar(resposta.json().get("existe") is True, "save criado")

    print("\nlendo de volta:")
    resposta = client.get("/api/saves")
    dados = resposta.json()
    salvo = dados.get("save", {})
    checar(dados.get("existe") is True, "slot existe")
    checar(salvo.get("area") == "catacumbas", "area preservada")
    checar(abs(salvo.get("x", 0) - 412.5) < 0.01, "x preservado")
    checar(abs(salvo.get("y", 0) - 733.0) < 0.01, "y preservado")
    checar(salvo.get("extra", {}).get("itens") == 3, "extra em json")
    checar("criado_em" in salvo, "carimbo de tempo")

    print("\nsobrescrevendo no mesmo slot:")
    payload2 = dict(payload, x=10.0, y=20.0)
    client.put("/api/saves", data=json.dumps(payload2),
               content_type="application/json")
    salvo2 = client.get("/api/saves").json()["save"]
    checar(abs(salvo2.get("x", 0) - 10.0) < 0.01, "x substituido")

    print("\nrejeitando entrada invalida:")
    resposta = client.put("/api/saves", data="{ nao e json",
                          content_type="application/json")
    checar(resposta.status_code == 400, "json quebrado devolve 400")
    resposta = client.put("/api/saves",
                          data=json.dumps({"x": "lado"}),
                          content_type="application/json")
    checar(resposta.status_code == 400, "texto no lugar de numero devolve 400")
    resposta = client.put("/api/saves", data=json.dumps({"extra": 7}),
                          content_type="application/json")
    checar(resposta.status_code == 400, "extra nao-objeto devolve 400")
    checar(abs(client.get("/api/saves").json()["save"]["x"] - 10.0) < 0.01,
           "save intacto depois das rejeicoes")

    print("\nhealth:")
    resposta = client.get("/api/health")
    checar(resposta.json().get("ok") is True, "health responde")

    print("\napagando:")
    resposta = client.delete("/api/saves")
    checar(resposta.status_code == 200, "DELETE responde 200")
    checar(client.get("/api/saves").json().get("existe") is False,
           "slot vazio de novo")

    if "sqlite" in os.environ["DB_ENGINE"]:
        # no Windows o arquivo so pode ser apagado depois que a conexao
        # fecha; sem isto a limpeza levanta PermissionError e o teste
        # "falha" num banco que passou em tudo
        from django.db import connections

        connections.close_all()
        Path(os.environ["_TESTE_DB"]).unlink(missing_ok=True)

    print()
    if falhas:
        print(f"FALHOU: {len(falhas)} verificacao(oes)")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print("OK: backend de save funcionando")
    return 0


if __name__ == "__main__":
    sys.exit(main())