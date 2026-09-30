"""Os cenarios do jogo.

Cada cenario e um par de tileset Wang gerado pelo PixelLab mais o nome
que aparece na tela. Os cenarios sao dados, nao codigo: adicionar um
cenario novo e colocar uma entrada em `CENARIOS`, sem tocar na cena.

O tileset e um Wang de 4x4, e o tile de cada celula sai dos quatro
VERTICES que ela toca. Por isso todo cenario tem o mesmo tileset no
formato 4x4, e a autotilagem e a mesma para todos.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cenario:
    """Um lugar para o jogador andar."""

    nome: str
    subtitulo: str
    tileset: str          # nome do par .png/.json em assets/tiles
    tem_caixao: bool      # o cenario comeca com o jogador no caixao
    semente: int          # semente do mapa, para cada cenario sair diferente

    @property
    def png(self) -> str:
        return f"{self.tileset}.png"

    @property
    def json(self) -> str:
        return f"{self.tileset}.json"


# A ordem aqui e a ordem do jogo: a saida de um cenario leva ao
# seguinte, e o ultimo devolve para o primeiro.
CENARIOS: tuple[Cenario, ...] = (
    Cenario(
        "Catacumbas",
        "onde os ossos descansam",
        "catacumbas_wang",
        tem_caixao=True,
        semente=7,
    ),
    Cenario(
        "Cemiterio",
        "a grama cresce sobre a terra",
        "cemiterio_wang",
        tem_caixao=False,
        semente=23,
    ),
    Cenario(
        "Aldeia",
        "os moradores locais",
        "aldeia_wang",
        tem_caixao=False,
        semente=31,
    ),
)

POR_NOME = {c.nome.lower(): c for c in CENARIOS}


def primeiro() -> Cenario:
    return CENARIOS[0]


def seguinte(nome: str) -> Cenario:
    """Proximo cenario depois de `nome`, fechando o ciclo."""
    nomes = [c.nome.lower() for c in CENARIOS]
    if nome.lower() not in nomes:
        return CENARIOS[0]
    i = nomes.index(nome.lower())
    return CENARIOS[(i + 1) % len(CENARIOS)]