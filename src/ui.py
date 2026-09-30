"""Funcoes auxiliares de interface (texto, paineis, botoes)."""
from __future__ import annotations

from typing import Tuple

import pygame

from . import settings
from .assets import get_font


def draw_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    position: Tuple[int, int],
    color: Tuple[int, int, int] | None = None,
    center: bool = True,
) -> pygame.Rect:
    """Desenha texto e devolve o retangulo ocupado."""
    font = get_font(size)
    rendered = font.render(text, True, color or settings.COLOR_TEXT)
    rect = rendered.get_rect(center=position) if center else rendered.get_rect(topleft=position)
    surface.blit(rendered, rect)
    return rect


def formatar_tempo(segundos: float) -> str:
    """Tempo em segundos como '1h 23m' (ou so '4m' na primeira hora).

    Vive aqui, e nao em uma cena, porque o menu e o HUD do jogo mostram
    o mesmo numero: deixar a funcao na tela do menu obrigaria a masmorra
    a importar o menu so por causa de um formato de texto.
    """
    total = max(0, int(segundos))
    horas, resto = divmod(total, 3600)
    minutos = resto // 60
    if horas:
        return f"{horas}h {minutos:02d}m"
    return f"{minutos}m"


def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: Tuple[int, int, int] | None = None,
    border_color: Tuple[int, int, int] | None = None,
    border_width: int = 2,
    radius: int = 6,
) -> None:
    """Desenha um painel arredondado."""
    pygame.draw.rect(
        surface, color or settings.COLOR_PANEL, rect, border_radius=radius
    )
    if border_color is not None:
        pygame.draw.rect(
            surface, border_color, rect, width=border_width, border_radius=radius
        )
