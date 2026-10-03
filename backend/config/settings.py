"""Configuracao do projeto Django (backend do John Sybau).

Este arquivo e a unica fonte de verdade do backend. Ele responde a tres
perguntas: onde esta o banco, quais apps estao instalados, e o que pode
ser acessado de fora.

Sobre o banco
-------------
SQLite, e o padrao do Django. O arquivo do banco fica DENTRO do projeto
(`db.sqlite3`), e nao em um caminho absoluto, para que o projeto inteiro
pode ser copiado para outra maquina e funcionar sem editar nada.

SQLite tem uma limitacao que importa para este caso: ele aceita UMA
escrita por vez, em serie. Isso e perfeito para o uso real aqui — o
jogo Pygame roda na maquina do jogador e grava uma linha quando a
partida termina, algumas vezes por hora. Nao e o caso de uso para o
qual o SQLite e ruim.

Sobre o DEBUG
-------------
`DEBUG = True` so enquanto developing. Com DEBUG ligado, qualquer
erro mostra a pagina inteira com o codigo-fonte e as variaveis de
ambiente — inclusive uma senha de banco, se houver. Ligar DEBUG num
ambiente de producao e vazamento de informacao, nao um detalhe.
"""
from __future__ import annotations

from pathlib import Path

# `BASE_DIR` e a pasta deste arquivo — a raiz do projeto Django, onde o
# `manage.py` mora. Tudo que o backend precisa enderecar sai daqui.
BASE_DIR = Path(__file__).resolve().parent.parent


# --- seguranca -----------------------------------------------------------

# DEBUG desligado por padrao. Quem desenvolve liga com
# `python manage.py runserver`, que ja liga o DEBUG sozinho se este
# valor estiver em False.
DEBUG = False

# `ALLOWED_HOSTS` e a lista de nomes que podem servir este backend.
#
# `"localhost"` e `"127.0.0.1"` porque o cliente e o jogo Pygame rodando
# na MESMA maquina. Asterisco nao entra: ele aceitaria qualquer
# cabecalho `Host` e permitiria checagem de cache envenenado.
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Chave secreta usada para assinar cookies e tokens de sessao.
#
# O valor de exemplo serve para desenvolvimento local e NAO serve para
# producao. Num ambiente real isto vem de uma variavel de ambiente, e
# nunca fica escrito no codigo — quem le o codigo no Git le a chave junto.
SECRET_KEY = "chave-de-desenvolvimento-nao-use-em-producao"


# --- aplicacoes ----------------------------------------------------------

INSTALLED_APPS = [
    # O admin do Django: uma interface web pronta para inspecionar e
    # editar as linhas do banco. Para um projeto academico economiza
    # semanas de tela de administracao.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # O app do jogo. Este nome e o que o comando `migrate` procura para
    # saber quais migracoes aplicar.
    "ranking",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- banco ----------------------------------------------------------------

# O SQLite e um arquivo, nao um servidor: e por isso que o ENGINE aceita
# um caminho de arquivo e nao precisa de host, porta nem usuario.
#
# O nome do arquivo esta montado a partir de BASE_DIR, e nao escrito
# solto. Um caminho relativo aqui (`"db.sqlite3"`) criaria o banco na
# pasta onde o comando foi digitado, e a proxima execucao, em outra
# pasta, nao encontraria o banco.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# --- autenticacao ---------------------------------------------------------

# O cliente e o jogo, e nao uma pessoa: nao ha login, nem usuario, nem
# senha. Isso e uma escolha de escopo, e vale registrar o por que.
#
# Um ranking academico que exige cadastro transforma "terminei a
# partida, quero ver minha posicao" em "crie uma conta, valide um
# e-mail, so entao". O preco e que qualquer um escreve no ranking
# qualquer pontuacao. Para um projeto de faculdade esse preco e aceito;
# em um jogo publicado nao seria, e a correcao seria assinar o envio com
# um token do servidor em vez de confiar no cliente.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation."
             "UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- idioma e hora --------------------------------------------------------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


# --- arquivos estaticos ---------------------------------------------------

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"