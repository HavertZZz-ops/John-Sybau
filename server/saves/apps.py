"""Configuracao do app Django."""
from __future__ import annotations

from django.apps import AppConfig


class SavesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "saves"
    verbose_name = "Saves do jogo"