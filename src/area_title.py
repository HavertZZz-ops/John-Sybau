"""Titulo de area, no jeito em que o Dark Souls anuncia um lugar.

Ao entrar num cenario novo, o nome aparece no alto, com o tracking
aberto e a cor palida, segura um instante e some. E o aviso de "voce
chegou aqui" sem tomar a tela inteira.

O componente e independente de qualquer cenario: a cena cria um
`AreaTitle`, chama `show("Catacumbas")` e ele cuida do resto ate sumir.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from . import theme

# tempos da animacao, em segundos
FADE_IN = 0.9
HOLD = 2.4
FADE_OUT = 1.3


@dataclass
class AreaTitle:
    """Nome da area aparecendo e sumindo no alto da tela."""

    surface: str = ""
    subtitle: str = ""
    elapsed: float = 0.0
    active: bool = False

    @property
    def duration(self) -> float:
        return FADE_IN + HOLD + FADE_OUT

    @property
    def finished(self) -> bool:
        """True quando o titulo ja sumiu e pode ser liberado."""
        return not self.active

    def show(self, name: str, subtitle: str = "") -> None:
        """Comeca a exibir `name`."""
        self.surface = name
        self.subtitle = subtitle
        self.elapsed = 0.0
        self.active = True

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.active = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active or not self.surface:
            return

        alpha = self._alpha()
        if alpha <= 0:
            return

        width, height = surface.get_size()
        # sobe um pouco enquanto entra, como a camera de cinema
        deslocamento = self._rise()
        y = int(height * 0.16) + deslocamento
        x = width // 2

        cor = theme.lerp(theme.TEXT_DIM, theme.TEXT_BRIGHT, alpha / 255)
        theme.text_tracked_at(
            surface, self.surface.upper(), 40, (x, y), cor, alpha=alpha
        )

        if self.subtitle:
            sub = theme.lerp(theme.BACKGROUND, theme.TEXT_DIM, alpha / 255)
            theme.text_tracked_at(
                surface, self.subtitle.upper(), 17, (x, y + 52), sub,
                alpha=alpha,
            )

        # filete fino sob o nome, que acende junto
        if FADE_IN < self.elapsed < self.duration - FADE_OUT:
            linha = theme.lerp(theme.HAIRLINE, theme.GOLD, alpha / 255)
            meio = width // 2
            meio_linha = int(width * 0.06)
            theme.hairline(
                surface,
                meio - meio_linha,
                y + 34,
                meio + meio_linha,
                linha,
            )

    # interno -------------------------------------------------------
    def _alpha(self) -> int:
        """255 na entrada, some devagar."""
        if self.elapsed < FADE_IN:
            return int(255 * (self.elapsed / FADE_IN))
        if self.elapsed < FADE_IN + HOLD:
            return 255
        restante = self.duration - self.elapsed
        if restante <= 0:
            return 0
        return int(255 * (restante / FADE_OUT))

    def _rise(self) -> int:
        """Deslocamento em pixels: o texto sobe durante a entrada."""
        if self.elapsed >= FADE_IN:
            return 0
        return int(10 * (1.0 - self.elapsed / FADE_IN))