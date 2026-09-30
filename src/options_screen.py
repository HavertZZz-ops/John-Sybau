"""Tela de opcoes: resolucao, tela cheia, vsync, escala e FPS.

As alteracoes entram em vigor na hora. Mudanca de resolucao ou de
tela cheia recria a janela, entao a cena recarrega os sprites.
"""
from __future__ import annotations

from typing import Callable, List, Tuple

import pygame

from . import assets, settings
from .config import (
    FPS_CHOICES,
    RESOLUTION_CHOICES,
    SCALE_CHOICES,
    Config,
)
from .scene import Scene
from .ui import draw_panel, draw_text

PANEL_W = 520
ROW_H = 44
MENU_H = 46


def _fps_label(value: int) -> str:
    return "sem limite" if value == 0 else f"{value}"


class Option:
    """Linha de opcao: rotulo, valor atual e como alterar."""

    def __init__(
        self,
        key: str,
        label: str,
        read: Callable[[], str],
        adjust: Callable[[int], bool],
        hint: str = "",
    ) -> None:
        self.key = key
        self.label = label
        self.read = read
        self.adjust = adjust
        self.hint = hint


class OptionsScreen(Scene):
    """Menu de configuracoes."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.config: Config = manager.config
        self.index = 0
        self.notice: str | None = None
        self.notice_timer = 0.0
        self.options: List[Option] = self._build_options()
        self._needs_rebuild = False

    def _build_options(self) -> List[Option]:
        config = self.config

        def set_resolution(delta: int) -> bool:
            config.cycle_resolution(delta)
            return True  # recria a janela

        def set_scale(delta: int) -> bool:
            config.cycle_scale(delta)
            assets.set_sprite_scale(config.sprite_scale)
            return True

        def set_fps(delta: int) -> bool:
            config.cycle_fps(delta)
            return True

        def toggle(name: str) -> Callable[[int], bool]:
            def inner(delta: int) -> bool:
                config.toggle(name)
                if name == "fullscreen":
                    return True
                return False

            return inner

        return [
            Option(
                "resolucao",
                "Resolucao",
                lambda: f"{config.width} x {config.height}",
                set_resolution,
                hint="esquerda/direita",
            ),
            Option(
                "escala",
                "Escala dos sprites",
                lambda: f"{config.sprite_scale}x",
                set_scale,
                hint="esquerda/direita",
            ),
            Option(
                "fps",
                "Limite de FPS",
                lambda: _fps_label(config.fps_limit),
                set_fps,
                hint="esquerda/direita",
            ),
            Option(
                "fullscreen",
                "Tela cheia",
                lambda: "sim" if config.fullscreen else "nao",
                toggle("fullscreen"),
            ),
            Option(
                "vsync",
                "Vsync",
                lambda: "sim" if config.vsync else "nao",
                toggle("vsync"),
                hint="requer reiniciar a janela para ter efeito total",
            ),
            Option(
                "show_fps",
                "Mostrar FPS",
                lambda: "sim" if config.show_fps else "nao",
                toggle("show_fps"),
            ),
        ]

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        self.options = self._build_options()

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.index = (self.index - 1) % len(self.options)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.index = (self.index + 1) % len(self.options)
        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            delta = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
            self._adjust(delta)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._apply()
        elif event.key == pygame.K_r:
            self._reset()
        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self._apply()
            self.manager.switch("title")

    def _adjust(self, delta: int) -> None:
        option = self.options[self.index]
        if option.adjust(delta):
            self._needs_rebuild = True
            self._apply()

    def _apply(self) -> None:
        """Salva e, se preciso, recria a janela."""
        self.config.save()
        self.manager.apply_config(rebuild=self._needs_rebuild)
        self._needs_rebuild = False
        if self.manager.window.get_size() != self.size:
            self.on_enter()
        self._show("configuracoes salvas")

    def _reset(self) -> None:
        fresh = Config().clamp()
        self.config.width = fresh.width
        self.config.height = fresh.height
        self.config.fullscreen = fresh.fullscreen
        self.config.vsync = fresh.vsync
        self.config.sprite_scale = fresh.sprite_scale
        self.config.fps_limit = fresh.fps_limit
        self.config.show_fps = fresh.show_fps
        assets.set_sprite_scale(self.config.sprite_scale)
        self._needs_rebuild = True
        self._apply()
        self._show("padroes restaurados")

    def _show(self, message: str) -> None:
        self.notice = message
        self.notice_timer = 2.0

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        if self.notice_timer > 0.0:
            self.notice_timer -= dt
            if self.notice_timer <= 0.0:
                self.notice = None

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLOR_BACKGROUND)
        w, h = self.size
        center_x = w // 2

        draw_text(surface, "OPCOES", 44, (center_x, 56), settings.COLOR_ACCENT)

        rows = len(self.options)
        panel_h = rows * ROW_H + MENU_H + 40
        panel = pygame.Rect(0, 100, PANEL_W, panel_h)
        panel.centerx = center_x
        draw_panel(
            surface, panel, color=settings.COLOR_PANEL, border_color=settings.COLOR_PANEL_LIGHT
        )

        y = panel.top + 16
        for i, option in enumerate(self.options):
            selected = i == self.index
            if selected:
                row = pygame.Rect(panel.left + 8, y - 2, panel.width - 16, ROW_H - 4)
                draw_panel(surface, row, color=settings.COLOR_PANEL_LIGHT, radius=4)

            value = option.read()
            color = settings.COLOR_ACCENT if selected else settings.COLOR_TEXT
            draw_text(
                surface,
                option.label,
                24,
                (panel.left + 40, y + ROW_H // 2 - 2),
                color,
                center=False,
            )
            draw_text(
                surface,
                f"< {value} >" if selected else value,
                24,
                (panel.right - 40, y + ROW_H // 2 - 2),
                color,
                center=False,
            )
            y += ROW_H

        menu_y = panel.bottom - MENU_H // 2 - 8
        draw_text(
            surface,
            "enter  salvar      R  restaurar padroes      esc  voltar",
            18,
            (center_x, menu_y),
            settings.COLOR_TEXT_DIM,
        )

        hint = self.options[self.index].hint
        if hint:
            draw_text(
                surface,
                hint,
                16,
                (center_x, panel.bottom + 26),
                (110, 104, 126),
            )

        if self.notice:
            draw_text(
                surface,
                self.notice,
                20,
                (center_x, panel.bottom + 56),
                settings.COLOR_ACCENT,
            )

        if h < 640:
            draw_text(
                surface,
                "aviso: janela pequena para o painel",
                16,
                (center_x, h - 20),
                settings.COLOR_DANGER,
            )
