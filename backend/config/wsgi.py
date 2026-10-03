"""Ponto de entrada WSGI.

WSGI e a interface entre o Django e um servidor web sincrono. O
`runserver` do Django usa este arquivo por baixo, entao e o que roda
quando voce roda `python manage.py runserver`.

`application` precisa existir com esse nome: e o que o servidor procura
depois de importar este arquivo. Renomear a variavel faz o servidor
nao encontrar nada e falhar com um erro que nao fala o nome do arquivo.
"""
from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()