"""Ponto de entrada de linha de comando do Django.

Este arquivo NAO se mexe. Ele e o mesmo em qualquer projeto Django: a
sua existencia e o que faz `python manage.py ...` funcionar.

Ele faz duas coisas e so duas:

  1. diz ao Django qual arquivo de configuracao usar (`config.settings`);
  2. repassa os argumentos da linha de comando para o Django.

Por que ele precisa existir em vez de um script proprio: o Django
procura o settings pelo nome do modulo em `sys.path`, e o `manage.py`
mora na raiz — uma pasta acima do pacote `config`. E ele quem coloca
essa pasta no caminho de importacao. Sem ele, todo comando precisaria
de `PYTHONPATH` configurado na mao.
"""
from __future__ import annotations

import os
import sys


def principal() -> None:
    """Executa o comando que veio na linha de comando."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as erro:
        # Mensagem util em vez de um traceback cru: a causa quase sempre
        # e o Django nao estar instalado, e dizer isso e mais barato do
        # que deixar o usuario descobrir sozinho.
        raise ImportError(
            "Nao foi possivel importar o Django. Ele esta instalado na "
            "versao certa? Tente: pip install django"
        ) from erro

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    principal()