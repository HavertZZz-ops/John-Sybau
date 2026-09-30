"""Autotiling de Wang: escolhe o tile pelos cantos da celula.

O tileset do PixelLab vem em 4 grades de 16 tiles, e o tile certo de
uma celula depende dos QUATRO VERTICES que ela toca, nao do que tem
dentro dela. Por isso nao vale guardar os tiles numa lista e escolher
"o de parede": a mesma celula de parede usa uma peca diferente no meio
de uma parede, na quina e na ponta.

O metadata do tileset traz, para cada tile, os cantos (NW/NE/SW/SE) e o
retangulo exato na folha. A tabela e montada a partir desse metadata,
sem adivinhar a ordem dos bits do `wang_N`: um palpite na ordem dos
bits colocaria a borda do lado errado e o padrao apareceria invertido.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pygame

# a ordem usada pelo metadata
CANTOS = ("NW", "NE", "SW", "SE")


def carregar_tileset_wang(
    png: Path, metadata: Path
) -> tuple[dict[tuple[bool, bool, bool, bool], pygame.Surface], int]:
    """Le a folha e monta `{cantos: imagem}`.

    Devolve tambem o lado do tile. `True` no canto significa terreno
    alto (parede).
    """
    dados = json.loads(metadata.read_text(encoding="utf-8"))
    folha = pygame.image.load(str(png)).convert_alpha()
    lado = int(dados["tile_size"]["width"])

    tabela: dict[tuple[bool, bool, bool, bool], pygame.Surface] = {}
    for tile in dados["tileset_data"]["tiles"]:
        cantos = tile.get("corners") or {}
        if not cantos:
            continue
        chave = tuple(cantos.get(c) == "upper" for c in CANTOS)
        caixa = tile["bounding_box"]
        tabela[chave] = folha.subsurface(
            pygame.Rect(
                int(caixa["x"]), int(caixa["y"]),
                int(caixa["width"]), int(caixa["height"]),
            )
        ).copy()

    if len(tabela) != 16:
        raise ValueError(
            f"tileset Wang com {len(tabela)} tiles, esperado 16. "
            f"Metadata: {metadata}"
        )
    return tabela, lado


class GradeWang:
    """Grade de parede/chao que sabe escolher o proprio tile."""

    def __init__(
        self,
        celulas: list[list[str]],
        parede: str | Callable[[str], bool] = "#",
        tabela: dict[tuple[bool, bool, bool, bool], pygame.Surface] | None = None,
    ) -> None:
        """`parede` pode ser o caractere da parede ou uma funcao.

        Aceitar as duas coisas e proposital. Com o parametro chamado
        `parede` e o valor padrao sendo a string "#", passar uma funcao
        nao dava nenhum aviso: a comparacao `celula == funcao` e
        sempre falsa, toda grade saia com o mesmo tile e o cenario
        inteiro virava chao sem erro nenhum.
        """
        self.celulas = celulas
        self._e_muro = parede if callable(parede) else (lambda c: c == parede)
        self.tabela = tabela
        self.lado = 16
        if tabela:
            self.lado = next(iter(tabela.values())).get_width()
        self._memo: dict[tuple[int, int], tuple] = {}

    def _e_parede(self, x: int, y: int) -> bool:
        if y < 0 or x < 0 or y >= len(self.celulas):
            return True
        linha = self.celulas[y]
        if x >= len(linha):
            return True
        return bool(self._e_muro(linha[x]))

    def _vertice_parede(self, vx: int, vy: int) -> bool:
        """Um vertice e parede se alguma celula em volta dele e parede."""
        return any(
            self._e_parede(vx + dx, vy + dy)
            for dy in (-1, 0)
            for dx in (-1, 0)
        )

    def tile_e_chave(
        self, x: int, y: int
    ) -> tuple[tuple[bool, bool, bool, bool], pygame.Surface]:
        """Imagem da celula e a chave de cantos que a escolheu.

        A chave volta junto porque e por ela que o desenho caches o
        tile ampliado. Cachear pelo `id()` da imagem nao serve: o id de
        um objeto liberado pelo garbage collector volta a ser usado por
        outro, e o cache passa a devolver a peca errada sem nenhum
        erro.
        """
        if (x, y) in self._memo:
            return self._memo[(x, y)]
        if self.tabela is None:
            raise ValueError("GradeWang sem tabela de tiles")

        chave = (
            self._vertice_parede(x, y),
            self._vertice_parede(x + 1, y),
            self._vertice_parede(x, y + 1),
            self._vertice_parede(x + 1, y + 1),
        )
        imagem = self.tabela.get(chave)
        if imagem is None:
            imagem = self.tabela[(False, False, False, False)]
        self._memo[(x, y)] = (chave, imagem)
        return chave, imagem

    def tile(self, x: int, y: int) -> pygame.Surface:
        """So a imagem da celula, escolhida pelos 4 vertices."""
        return self.tile_e_chave(x, y)[1]