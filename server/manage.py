#!/usr/bin/env python
"""Utilitario do Django."""
from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Django nao encontrado. Instale com: pip install django psycopg"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()