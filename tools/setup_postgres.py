"""Prepara o PostgreSQL para o save: cria o banco e aplica a migration.

Faz o passo a passo que seria chato de fazer na mao pelo pgAdmin, e
repete sem medo (idempotente): pode rodar quantas vezes quiser.

    python tools/setup_postgres.py

Precisa que o servidor do Postgres esteja rodando. Se estiver parado,
informa o servico e o que fazer.
"""
from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"

BANCO = "john_sybau"
USUARIO = "postgres"
HOST = "127.0.0.1"
PORTA = "5432"

# onde procurar o psql: o do PostgreSQL instalado no Windows
CANDIDATOS = [
    Path(r"C:\Program Files\PostgreSQL\18\bin"),
    Path(r"C:\Program Files\PostgreSQL\17\bin"),
    Path(r"C:\Program Files\PostgreSQL\16\bin"),
]


def achar_psql() -> Path | None:
    for pasta in CANDIDATOS:
        exe = pasta / "psql.exe"
        if exe.is_file():
            return exe
    achado = shutil_which("psql")
    return Path(achado) if achado else None


def shutil_which(nome: str) -> str | None:
    import shutil

    return shutil.which(nome)


def porta_aberta() -> bool:
    import socket

    with socket.socket() as s:
        s.settimeout(2)
        return s.connect_ex((HOST, int(PORTA))) == 0


def rodar_psql(psql: Path, senha: str, args: list[str]) -> tuple[int, str, str]:
    env = {**os.environ, "PGPASSWORD": senha}
    proc = subprocess.run(
        [str(psql), "-U", USUARIO, "-h", HOST, "-p", PORTA, *args],
        capture_output=True, text=True, env=env, timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    print("=" * 62)
    print("  PostgreSQL do John Sybau")
    print("=" * 62)

    psql = achar_psql()
    if psql is None:
        print("\npsql nao encontrado. Instale o PostgreSQL ou ajuste o PATH.")
        return 1
    print(f"\npsql:  {psql}")

    if not porta_aberta():
        print(f"\nO servidor nao esta escutando em {HOST}:{PORTA}.")
        print("\nPara subir (precisa de Administrador, ou use o pgAdmin):")
        print("  net start postgresql-x64-18")
        print("\nOu, sem privilegios de administrador:")
        print('  & "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_ctl.exe" start -D '
              '"C:\\Program Files\\PostgreSQL\\18\\data"')
        return 1
    print(f"servidor: escutando em {HOST}:{PORTA}")

    print(f"\nSenha do usuario '{USUARIO}' (fica So nesta execucao):")
    try:
        senha = getpass.getpass("  ")
    except (EOFError, KeyboardInterrupt):
        return 1
    if not senha:
        print("  senha vazia: cancelado")
        return 1

    print("\nconferindo a conexao...")
    codigo, saida, erro = rodar_psql(
        psql, senha, ["-d", "postgres", "-tAc", "select 1;"]
    )
    if codigo != 0:
        print("  FALHOU a conexao:", erro.strip()[:200])
        print("\nA senha esta errada, ou o Postgres exige outro metodo de")
        print("autenticacao. No pgAdmin: Connect Server > com a senha certa.")
        return 1
    print("  ok")

    print(f"\noversao: {saida.strip()}")

    # o banco pode ja existir; CREATE DATABASE nao aceita IF NOT EXISTS
    codigo, saida, _ = rodar_psql(
        psql, senha, ["-d", "postgres", "-tAc",
                      f"select 1 from pg_database where datname='{BANCO}';"]
    )
    if saida.strip() == "1":
        print(f"\nbanco '{BANCO}': ja existe")
    else:
        print(f"\ncriando o banco '{BANCO}'...")
        codigo, _, erro = rodar_psql(
            psql, senha, ["-d", "postgres", "-c", f'CREATE DATABASE "{BANCO}";']
        )
        if codigo != 0:
            print("  FALHOU:", erro.strip()[:300])
            return 1
        print("  criado")

    print("\naplicando as migrations...")
    env = {
        **os.environ,
        "DB_ENGINE": "django.db.backends.postgresql",
        "PGDATABASE": BANCO,
        "PGUSER": USUARIO,
        "PGPASSWORD": senha,
        "PGHOST": HOST,
        "PGPORT": PORTA,
        "PYTHONPATH": str(SERVER),
    }
    proc = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        cwd=SERVER, env=env, capture_output=True, text=True, timeout=120,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        print("\nFALHOU na migration")
        return 1

    print("\n" + "=" * 62)
    print("  Pronto. Agora suba o servidor de save:")
    print()
    print(f'  cd "{SERVER}"')
    print(f'  $env:PGPASSWORD = "{senha}"')
    print("  python manage.py runserver 8000")
    print()
    print("  E o jogo, em outro terminal:")
    print(f'  cd "{ROOT}"')
    print("  python run.py")
    print()
    print("  Sem o servidor rodando, o jogo salva em save1.json.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())