#!/usr/bin/env python
"""Gera as migrations do app de save.

    python tools/make_migrations.py

Para dentro do repositorio, porque uma migration versionada e o que
permite que o banco de outra maquina suba no mesmo esquema. Rodar
`makemigrations` a mao eoguardo e' o que faz o banco do servidor do
jogador divergir do que o jogo espera.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")
    os.environ.setdefault("DB_ENGINE", "django.db.backends.sqlite3")
    sys.path.insert(0, str(SERVER))

    proc = subprocess.run(
        [sys.executable, "manage.py", "makemigrations", "saves", "--no-header"],
        cwd=SERVER,
        env={**os.environ, "PYTHONPATH": str(SERVER)},
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        return proc.returncode

    mig = SERVER / "saves" / "migrations" / "0001_initial.py"
    if mig.is_file():
        print(f"\ncriado: {mig.relative_to(ROOT)}")
    else:
        print("\nnenhuma migration foi gerada (o modelo ja estava em dia?)")
    return 0


if __name__ == "__main__":
    sys.exit(main())