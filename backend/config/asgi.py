"""Ponto de entrada ASGI.

ASGI e a versao assincrona do WSGI: em vez de um pedido por vez numa
thread, o servidor mantem a conexao aberta e resolve varias corrotinas.
O `runserver` do Django nao usa este arquivo (ele usa o WSGI), mas
servidores de producao como o uvicorn sim.

Para este projeto as duas interfaces servem igual, porque a API nao
faz trabalho lento: uma gravacao no SQLite local leva milissegundos. A
diferenca so aparece se um dia o backend falar com outro servico pela
rede — e nesse dia ASGI e a que nao trava.
"""
from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()