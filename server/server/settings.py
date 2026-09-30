"""Configuracao do Django que guarda os saves no PostgreSQL.

Por que um servidor Django para um save de jogo?

Um banco relacional guardando estado de jogo e um formato comum e
util: da para consultar os saves, ver o progresso, migrar entre
versoes, e o mesmo esquema serve quando o jogo ganhar multiplayer ou
conta de usuario. O preco e honesto: precisa de um processo a mais
rodando, e o Postgres precisa estar de pe.

Por isso o jogo tem dois lugares de save (ver `src/saves.py`): se
este servidor nao responder, o save vai para arquivo e o jogo segue
funcionando. Este servidor e o modo completo, nao um requisito para
jogar.

Rodar:
    python manage.py migrate
    python manage.py runserver 8000
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# chave secreta so para desenvolvimento local. Em producao vem do
# ambiente, nunca do codigo.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-local-nao-use-em-producao"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "saves",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "server.urls"
WSGI_APPLICATION = "server.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

# --- banco ---------------------------------------------------------
# Postgres por padrao, como pedido. O `PG*` vem do ambiente para nao
# deixar usuario e senha no codigo; se nao houver nada, cai para
# SQLite, que deixa o servidor funcionando mesmo sem banco instalado
# (util para developing e para os testes do projeto).
_ENGINE = os.environ.get("DB_ENGINE", "django.db.backends.postgresql")

if "sqlite" in _ENGINE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("PGDATABASE", "johnsybau"),
            "USER": os.environ.get("PGUSER", "postgres"),
            "PASSWORD": os.environ.get("PGPASSWORD", ""),
            "HOST": os.environ.get("PGHOST", "127.0.0.1"),
            "PORT": os.environ.get("PGPORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# o jogo fala HTTP com esta porta
PORT = int(os.environ.get("PORT", "8000"))

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"