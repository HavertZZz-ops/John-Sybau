"""Rotas do servidor: a API de save em /api/saves."""
from __future__ import annotations

from django.urls import path

from saves import views

urlpatterns = [
    path("api/saves", views.save, name="save"),
    path("api/health", views.health, name="health"),
]