"""As fogueiras: o lugar seguro do jogo.

A fogueira faz tres coisas, e as tres importam:
  - salva o jogo
  - descansa: o heroi recupera a vida toda
  - repõe as pocoes de cura, que e o que torna a proxima luta possivel

Onde ela fica e uma regra do jogo, nao um detalhe: nao existe
fogueira na sala do chefe. A ultima sala da masmorra e o lugar onde nao
se descansa, e a regra do recambio do chefe so funciona porque a fogueira
da sala 5 nao queima.

A primeira fogueira do jogo e na aldeia. Entrar na masmorra e sair
correndo leva ate ela, e e o primeiro lugar onde o jogador descobre o
que e descansar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

# quantas pocoes a fogueira repoe. Uma e o suficiente para a sala da
# pocao e para o chefe; mais que isso tornaria a loja da aldeia
# inutil.
POCOES_DO_DESCANSO = 1

# o alcance de interacao com a fogueira, em pixels de 1x
ALCANCE = 44


@dataclass(frozen=True)
class Fogueira:
    """Uma fogueira, num lugar do mundo."""

    cenario: str      # "aldeia" | "catacumbas"
    sala: int         # 0 quando nao esta dentro de uma sala
    nome: str

    @property
    def chave(self) -> str:
        """Identidade estavel, para o save saber qual era a ultima."""
        return f"{self.cenario}:{self.sala}"


# A fogueira da aldeia e a primeira do jogo, entao mora aqui e nao na
# masmorra. As da masmorra ficam nas salas 1 a 4: a 5 e a do chefe.
FOGUEIRAS: tuple[Fogueira, ...] = (
    Fogueira("aldeia", 0, "Fogueira da Aldeia"),
    Fogueira("catacumbas", 1, "Fogueira do Cofre"),
    Fogueira("catacumbas", 2, "Fogueira do Espelho"),
    Fogueira("catacumbas", 3, "Fogueira do Selo"),
    Fogueira("catacumbas", 4, "Fogueira da Panela"),
)

POR_CHAVE = {f.chave: f for f in FOGUEIRAS}


def da_sala(cenario: str, sala: int) -> Fogueira | None:
    """A fogueira de um cenario e uma sala, se existir.

    A sala do chefe nao tem. E de proposito: um lugar seguro na ultima
    sala tornaria a fuga do chefe uma opcao sem risco, e a regra do
    recambio perderia o sentido.
    """
    return POR_CHAVE.get(f"{cenario}:{sala}")


def primeira_do_cenario(cenario: str) -> Fogueira | None:
    for f in FOGUEIRAS:
        if f.cenario == cenario:
            return f
    return None


# --- o desenho -------------------------------------------------------
# A fogueira e desenhada por codigo: sao tres formas (cinza, lenha,
# brasa) e nenhuma delas justifica esperar um arquivo de arte.

_HALO_CACHE: dict[int, pygame.Surface] = {}


def _halo(raio: int) -> pygame.Surface:
    """Brilho alaranjado, com transparencia. O raio muda, a textura nao."""
    if raio in _HALO_CACHE:
        return _HALO_CACHE[raio]
    tam = max(4, raio * 2)
    img = pygame.Surface((tam, tam), pygame.SRCALPHA)
    # circulo com alpha caindo para fora: um disco chapado nao parece
    # brilho, parece um adesivo laranja colado no chao
    passos = 7
    for i in range(passos, 0, -1):
        t = i / passos
        a = int(52 * (1.0 - t) + 10)
        pygame.draw.circle(
            img, (232, 138, 58, a), (tam // 2, tam // 2),
            int(raio * t), 0,
        )
    _HALO_CACHE[raio] = img
    return img


def desenhar(surface: pygame.Surface, x: int, y: int, lado: int, tempo: float) -> None:
    """Fogueira com a base em (x, y), do tamanho `lado`."""
    pulso = (math.sin(tempo * 2.4) + 1.0) / 2.0

    raio = max(3, int(lado * (0.46 + 0.10 * pulso)))
    surface.blit(_halo(raio), (x - raio, y - raio - lado // 3))

    # cinza
    pygame.draw.circle(surface, (52, 45, 42), (x, y), max(2, lado // 4))
    pygame.draw.circle(surface, (28, 24, 22), (x, y), max(2, lado // 4), 1)

    # lenha cruzada
    meia = max(2, lado // 5)
    pygame.draw.line(surface, (98, 76, 58), (x - meia, y - 2),
                     (x + meia, y + 2), 2)
    pygame.draw.line(surface, (74, 57, 46), (x - meia, y + 2),
                     (x + meia, y - 2), 2)

    # brasa, com a chama piscando em tamanho
    pygame.draw.circle(surface, (208, 88, 36), (x, y), max(1, lado // 9))
    pygame.draw.circle(
        surface, (242, 190, 96),
        (x, y - 1), max(1, lado // 14 + int(pulso * 1.6)),
    )
