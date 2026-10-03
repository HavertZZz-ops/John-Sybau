"""As rotas da API.

Tudo da API mora sob `/api/`. O prefixo e uma decisao de organizacao, e
tambem de seguranca: separar o que responde a API do que responde a
paginas web numa mesma rota e a forma mais facil de um `if` no codigo
dizer que a listagem do ranking e publica e a edicao nao. Com o prefixo,
a separacao ja esta feita no roteamento.
"""
from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    # GET  -> o ranking
    # POST -> grava uma partida
    path("", views.listar_ranking, name="ranking"),
    path("ranking/", views.listar_ranking, name="ranking-listar"),
    path("ranking/registrar/", views.registrar_partida,
         name="ranking-registrar"),
]