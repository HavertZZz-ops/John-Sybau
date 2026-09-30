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

_HALO_CACHE: dict[tuple[int, int], pygame.Surface] = {}


def _halo(raio: int, forca: int) -> pygame.Surface:
    """Brilho alaranjado, com transparencia. O raio e a forca variam."""
    chave = (raio, forca)
    if chave in _HALO_CACHE:
        return _HALO_CACHE[chave]
    tam = max(4, raio * 2)
    img = pygame.Surface((tam, tam), pygame.SRCALPHA)
    # circulo com alpha caindo para fora: um disco chapado nao parece
    # brilho, parece um adesivo laranja colado no chao
    passos = 8
    for i in range(passos, 0, -1):
        t = i / passos
        pygame.draw.circle(
            img, (232, 138, 58, int(forca * (1.0 - t) + forca * 0.18)),
            (tam // 2, tam // 2), max(1, int(raio * t)), 0,
        )
    _HALO_CACHE[chave] = img
    return img


def desenhar(surface: pygame.Surface, x: int, y: int, lado: int, tempo: float) -> None:
    """Fogueira com a base em (x, y), do tamanho `lado`.

    O desenho e grande de proposito. Na primeira versao a fogueira
    ocupava um terco do lado do tile e ficava perdida no chao ao lado
    dos moradores, que sao sprites de 64px: o lugar seguro do jogo
    parecia um detalhe. A fogueira e o ponto de referencia da tela, e
    precisa parecer.
    """
    pulso = (math.sin(tempo * 2.4) + 1.0) / 2.0
    alcance = lado * 1.15

    # --- brilho no chao, em tres camadas ---------------------------
    for fator, alpha in ((1.0, 34), (0.66, 58), (0.36, 96)):
        raio = max(4, int(alcance * fator * (0.92 + 0.10 * pulso)))
        surface.blit(_halo(raio, alpha), (x - raio, y - raio - lado // 5))

    # --- pedestal de pedra -----------------------------------------
    ped = max(3, lado // 3)
    pygame.draw.ellipse(
        surface, (54, 47, 44),
        pygame.Rect(x - ped, y - ped // 3, ped * 2, ped + ped // 2),
    )
    pygame.draw.ellipse(
        surface, (26, 22, 20),
        pygame.Rect(x - ped, y - ped // 3, ped * 2, ped + ped // 2), 1,
    )

    # --- lenha ------------------------------------------------------
    comp = max(3, lado // 3)
    esp = max(2, lado // 8)
    pygame.draw.line(surface, (104, 80, 60), (x - comp, y - esp), (x + comp, y + esp), 3)
    pygame.draw.line(surface, (78, 60, 47), (x - comp, y + esp), (x + comp, y - esp), 3)
    pygame.draw.line(surface, (122, 96, 72), (x - comp, y - esp), (x + comp, y + esp), 1)

    # --- brasas -----------------------------------------------------
    pygame.draw.circle(surface, (196, 74, 30), (x, y), max(2, lado // 7))
    pygame.draw.circle(surface, (236, 132, 48), (x, y), max(1, lado // 11))
    # a chama: tres pontas de altura diferente, piscando
    for i, (dx, alt) in enumerate(((-0.18, 0.30), (0.0, 0.46), (0.18, 0.26))):
        h = int(lado * alt * (0.72 + 0.38 * ((pulso + i * 0.31) % 1.0)))
        pygame.draw.polygon(
            surface, (244, 196, 96) if i == 1 else (222, 140, 52),
            [
                (x + int(dx * lado), y - h),
                (x + int(dx * lado) - max(1, lado // 14), y),
                (x + int(dx * lado) + max(1, lado // 14), y),
            ],
        )
