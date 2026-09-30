"""Salvar e carregar o jogo.

O save e um dicionario simples (posicao, area, tempo de jogo) e o
jogo nao sabe onde ele esta guardado: quem sabe e o `SaveStore`.

Ha dois motivos para essa separacao:

1. o jogo precisa funcionar sem servidor nenhum. Um arquivo local
   sempre funciona, entao da para testar e jogar offline.
2. o Postgres e um servico: se ele estiver parado, o jogo continua
   jogando e salvando, so que no arquivo. Perder o progresso nao pode
   depender de um banco estar de pe.

O `SaveStore` do Postgres (via Django) e escolhido automaticamente
quando o servidor responde, e o arquivo e o plano B.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from . import settings

SAVE_PATH = settings.ROOT_DIR / "save1.json"

# versao do formato; se o formato mudar, um save antigo e lido errado
FORMATO = 1

# onde o backend Django escuta
API_PADRAO = "http://127.0.0.1:8000/api/saves"
# quanto esperar pelo servidor, em segundos. Curto de proposito: um
# jogo nao pode travar 5 segundos por causa de um banco parado.
TIMEOUT_API = 1.5


@dataclass
class Save:
    """Um ponto de continuacao."""

    area: str = "catacumbas"
    x: float = 0.0
    y: float = 0.0
    direcao: str = "sul"
    tempo_jogado: float = 0.0
    criado_em: str = ""
    versao: int = FORMATO
    extra: dict[str, Any] = field(default_factory=dict)

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Save":
        """Le um save, ignorando campos desconhecidos ou invalidos.

        Um arquivo de save vem do disco e pode ter sido editado na mao.
        Levantar excecao aqui derrubaria o jogo no menu, que e o pior
        lugar possivel para um erro de dados.
        """
        known = {f for f in cls.__dataclass_fields__}
        limpo = {k: v for k, v in dados.items() if k in known}
        for campo, padrao in (
            ("x", 0.0), ("y", 0.0), ("tempo_jogado", 0.0),
        ):
            try:
                limpo[campo] = float(limpo.get(campo, padrao))
            except (TypeError, ValueError):
                limpo[campo] = padrao
        if limpo.get("area") is None:
            limpo["area"] = "catacumbas"
        if not isinstance(limpo.get("extra"), dict):
            limpo["extra"] = {}
        return cls(**limpo)


class SaveStore(Protocol):
    """O que o jogo precisa de um lugar de save."""

    def salvar(self, save: Save) -> bool: ...
    def carregar(self) -> Save | None: ...
    def existe(self) -> bool: ...
    def apagar(self) -> bool: ...
    @property
    def descricao(self) -> str: ...


class ArquivoSaveStore:
    """Save em JSON no disco. Funciona sempre, sem servidor."""

    def __init__(self, caminho: Path = SAVE_PATH) -> None:
        self.caminho = caminho

    @property
    def descricao(self) -> str:
        return f"arquivo {self.caminho.name}"

    def existe(self) -> bool:
        return self.caminho.is_file()

    def salvar(self, save: Save) -> bool:
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            # grava em temporario e troca: um save pela metade, de um
            # disco cheio ou de um Ctrl+C, apagaria o save bom
            temporario = self.caminho.with_suffix(".tmp")
            temporario.write_text(
                json.dumps(save.para_dict(), indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporario, self.caminho)
            return True
        except OSError as exc:
            print(f"[save] nao foi possivel salvar: {exc}")
            return False

    def carregar(self) -> Save | None:
        if not self.caminho.is_file():
            return None
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[save] arquivo ilegivel, ignorando: {exc}")
            return None
        if not isinstance(dados, dict):
            return None
        return Save.de_dict(dados)

    def apagar(self) -> bool:
        try:
            self.caminho.unlink(missing_ok=True)
            return True
        except OSError:
            return False


class DjangoSaveStore:
    """Save no Postgres, atraves da API do Django.

    Usa so a biblioteca padrao (urllib): nao vale puxar `requests`
    para o jogo por causa de uma chamada de rede.
    """

    def __init__(self, url: str = API_PADRAO, timeout: float = TIMEOUT_API) -> None:
        self.url = url
        self.timeout = timeout

    @property
    def descricao(self) -> str:
        return f"postgres {self.url}"

    def _pedir(self, metodo: str, corpo: dict | None = None) -> Any:
        import urllib.error
        import urllib.request

        dados = None
        headers = {"Accept": "application/json"}
        if corpo is not None:
            dados = json.dumps(corpo).encode("utf-8")
            headers["Content-Type"] = "application/json"

        pedido = urllib.request.Request(
            self.url, data=dados, headers=headers, method=metodo
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout) as resp:
                bruto = resp.read().decode("utf-8")
            return json.loads(bruto) if bruto else None
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            # servidor fora, banco parado, timeout: o jogo continua no
            # arquivo, entao isto nao e erro fatal e nao sobe nada
            return None

    def existe(self) -> bool:
        """True se o servidor respondeu e ha save guardado.

        O GET responde `{"existe": bool, "save": {...}}`. Olhar so se a
        resposta veio nao serve: depois de um DELETE a resposta e
        `{"existe": false}` e o jogo acharia que ainda tem save.
        """
        dados = self._pedir("GET")
        if not isinstance(dados, dict):
            return False
        return bool(dados.get("existe"))

    def salvar(self, save: Save) -> bool:
        return self._pedir("PUT", save.para_dict()) is not None

    def carregar(self) -> Save | None:
        dados = self._pedir("GET")
        if not isinstance(dados, dict):
            return None
        if not dados.get("existe"):
            return None
        # o save vem dentro de "save", nao no nivel de cima. Passando a
        # resposta inteira para o Save, os campos "existe" e "save"
        # seriam descartados como desconhecidos e viraria um save com
        # posicao 0,0: o jogo voltava ao comeco sem reclamar de nada.
        interno = dados.get("save")
        if not isinstance(interno, dict):
            return None
        return Save.de_dict(interno)

    def apagar(self) -> bool:
        dados = self._pedir("DELETE")
        if isinstance(dados, dict):
            return not dados.get("existe", False)
        return False


def escolher_store(procurar_servidor: bool = True) -> SaveStore:
    """Postgres se ele responder, senao arquivo.

    A busca e feita uma vez, no inicio do jogo, e custa no maximo
    TIMEOUT_API. Se o Postgres subir depois, o proximo start usa ele.
    """
    if procurar_servidor:
        remoto = DjangoSaveStore()
        if remoto.existe():
            return remoto
    return ArquivoSaveStore()