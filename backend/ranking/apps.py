"""Configuracao do app `ranking`."""

from __future__ import annotations

from django.apps import AppConfig


class RankingConfig(AppConfig):
    # `default_auto_field` define o tipo da chave primary key. O padrao do
    # Django recente e `BigAutoField` (inteiro de 64 bits). Deixar o
    # padrao antigo (`AutoField`, 32 bits) funciona e e um erro so depois
    # de muito dado — e nao da para trocar a chave de uma tabela que ja
    # tem linha.
    default_auto_field = "django.db.models.BigAutoField"

    # `name` e o nome do app, e tem de bater com o que esta em
    # INSTALLED_APPS. Sem este metodo, o Django procura `ranking.apps`
    # e usa a primeira classe que encontrar la.
    name = "ranking"

    # Rotulo legivel no admin e nas mensagens de erro. Sem isto aparece
    # "Ranking" e "Rankings" (o plural automatico do Django e ruim em
    # portugues).
    verbose_name = "Ranking"