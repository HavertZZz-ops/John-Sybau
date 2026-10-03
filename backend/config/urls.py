"""Rotas da raiz do projeto.

Delega quase tudo para o app `ranking`. As rotas do admin ficam aqui
porque o admin do Django e um app do proprio Django — ele nao pertence
ao app do jogo, e escondê-lo dentro dele seria errado.
"""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def raiz(request):
    """Resposta na raiz: onde a API esta.

    Existe para ninguem abrir `localhost:8000/` e ver um 404 sem
    pista. Um JSON pequeno dizendo o caminho resolve.
    """
    return JsonResponse(
        {
            "jogo": "John Sybau",
            "api": "/api/ranking/",
            "registrar": "/api/ranking/registrar/",
        },
        json_dumps_params={"ensure_ascii": False},
    )


urlpatterns = [
    path("", raiz),
    path("admin/", admin.site.urls),
    path("api/", include("ranking.urls")),
]