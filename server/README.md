# Servidor de save (Django + PostgreSQL)

Guarda o save do jogo num PostgreSQL, em vez de um arquivo no disco.
O jogo fala com ele por HTTP em `127.0.0.1:8000`.

## Por que um servidor, e nao so o psycopg direto

Um banco relacional para estado de jogo da para consultar, migrar e
reusar quando o jogo ganhar conta de usuario ou multiplayer. O preco e
um processo a mais rodando. Por isso o jogo **nao depende** deste
servidor: sem ele, o save vai para `save1.json` e tudo funciona. Ver
`src/saves.py`.

## Preparar (uma vez)

O banco `john_sybau` e as tabelas sao criados por:

```powershell
python tools/setup_postgres.py
```

Ele pede a senha do usuario `postgres`, cria o banco se faltar e roda a
migration. Pode repetir sem efeito colateral.

## Rodar

```powershell
cd server
$env:PGPASSWORD = "sua senha"
python manage.py runserver 8000
```

Para o Postgres nao pedir a senha toda hora:

```powershell
$env:PGDATABASE = "john_sybau"
$env:PGUSER     = "postgres"
$env:PGPASSWORD = "sua senha"
$env:PGHOST     = "127.0.0.1"
$env:PGPORT     = "5432"
```

Ver se respondeu: <http://127.0.0.1:8000/api/health>

## Testar

```powershell
python tools/test_save_server.py   # a API e o banco, direto
python tools/test_save_client.py   # o jogo falando com o servidor
```

O primeiro roda em SQLite por padrao, para passar em qualquer maquina.
Para testar no Postgres de verdade:

```powershell
$env:DB_ENGINE = "django.db.backends.postgresql"
python tools/test_save_server.py
```

## A API

Uma rota so, `GET /api/saves`:

| Metodo   | O que faz                                   |
|----------|---------------------------------------------|
| `GET`    | le o slot; `{"existe": false}` se vazio     |
| `PUT`    | grava, sobrescrevendo o slot                |
| `DELETE` | apaga o slot                                |
| `GET /api/health` | responde vivo, e se ha save       |

Exemplo de `PUT`:

```json
{
  "area": "catacumbas",
  "x": 1257.67,
  "y": 1286.49,
  "direcao": "oeste",
  "tempo_jogado": 91.5,
  "versao": 1,
  "extra": {}
}
```

Campo fora do esperado devolve `400` e **nao** apaga o save bom.

## Estrutura

```
server/
  manage.py
  server/settings.py     configuracao; le as variaveis PG* do ambiente
  server/urls.py         a rota /api/saves
  saves/models.py        o modelo Slot
  saves/views.py         GET/PUT/DELETE em JSON puro
  saves/migrations/      0001_initial, versionada
```

Nao ha Django REST Framework aqui: a API inteira sao quatro rotas, e
puxar uma framework inteira seria mais uma dependencia para manter.