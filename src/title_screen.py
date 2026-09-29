"""Tela inicial do jogo: menu principal com elenco em placeholders.

Nenhum sprite e necessario para esta tela. Os personagens sao
desenhados como retangulos rotulados; quando os PNGs forem colocados
em assets/sprites/, eles passam a aparecer automaticamente.
"""
from __future__ import annotations

from typing import List, Tuple

import pygame

from . import assets, settings
from .scene import Scene
from .ui import draw_panel, draw_text

# (nome do arquivo png, rotulo na tela, texto curto dentro do placeholder)
CHARACTER_LABELS: Tuple[Tuple[str, str, str], ...] = (
    ("protagonista", "Protagonista", "PROTAG"),
    ("estranho", "Estranho", "ESTRANHO"),
    ("mulher_misteriosa", "Mulher misteriosa", "MULHER"),
    ("rei_mago", "Rei mago", "REI MAGO"),
)

# itens do menu principal
MENU_ITEMS: Tuple[str, ...] = ("Iniciar jogo", "Opcoes", "Sair")


class MenuItem:
    """Item de menu com selecao por teclado."""

    def __init__(self, label: str, center: Tuple[int, int]) -> None:
        self.label = label
        self.center = center
        self.selected = False
        self.hovered = False
        self._rect = pygame.Rect(0, 0, 320, 46)
        self._rect.center = center

    @property
    def rect(self) -> pygame.Rect:
        return self._rect


class TitleScreen(Scene):
    """Menu principal com elenco de personagens em placeholders."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.menu_index = 0
        self.time = 0.0
        self.notice: str | None = None
        self.notice_timer = 0.0

        center_x = settings.SCREEN_WIDTH // 2
        base_y = 500
        self.menu: List[MenuItem] = [
            MenuItem(label, (center_x, base_y + i * 56))
            for i, label in enumerate(MENU_ITEMS)
        ]
        self._sync_selection()

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        self.menu_index = 0
        self._sync_selection()

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self._move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self._move(1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._activate()
        elif event.key == pygame.K_ESCAPE:
            self.manager.quit()

    def _move(self, delta: int) -> None:
        self.menu_index = (self.menu_index + delta) % len(self.menu)
        self._sync_selection()

    def _sync_selection(self) -> None:
        for i, item in enumerate(self.menu):
            item.selected = i == self.menu_index

    def _activate(self) -> None:
        label = self.menu[self.menu_index].label
        if label == "Sair":
            self.manager.quit()
            return
        if label == "Iniciar jogo":
            self._show_notice("Cena de jogo ainda nao criada - veia o KANBAN.md")
        else:
            self._show_notice(f"'{label}' ainda nao implementada")

    def _show_notice(self, message: str) -> None:
        self.notice = message
        self.notice_timer = 2.5

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        mouse = pygame.mouse.get_pos()
        for i, item in enumerate(self.menu):
            item.hovered = item.rect.collidepoint(mouse)

        if self.notice_timer > 0.0:
            self.notice_timer -= dt
            if self.notice_timer <= 0.0:
                self.notice = None

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLOR_BACKGROUND)
        self._draw_background(surface)
        self._draw_title(surface)
        self._draw_cast(surface)
        self._draw_menu(surface)
        self._draw_footer(surface)

    def _draw_background(self, surface: pygame.Surface) -> None:
        """Faixa de fundo e um "chao" simples para dar profundidade."""
        panel = pygame.Rect(
            0,
            int(settings.SCREEN_HEIGHT * 0.62),
            settings.SCREEN_WIDTH,
            settings.SCREEN_HEIGHT,
        )
        draw_panel(surface, panel, color=settings.COLOR_PANEL, radius=0)

        line_y = panel.top
        pygame.draw.line(
            surface,
            settings.COLOR_PANEL_LIGHT,
            (0, line_y),
            (settings.SCREEN_WIDTH, line_y),
            2,
        )

    def _draw_title(self, surface: pygame.Surface) -> None:
        center_x = settings.SCREEN_WIDTH // 2
        bounce = int(abs(_pulse(self.time, 1.6)) * 6)
        draw_text(surface, settings.GAME_TITLE, 72, (center_x, 120 - bounce), settings.COLOR_ACCENT)

        total = len(CHARACTER_LABELS)
        ready = self._sprites_ready()
        if ready == total:
            subtitle = "prototipo"
        else:
            subtitle = f"prototipo - {ready}/{total} sprites"
        draw_text(
            surface,
            subtitle,
            22,
            (center_x, 182),
            settings.COLOR_TEXT_DIM,
        )

    @staticmethod
    def _sprites_ready() -> int:
        """Quantos dos personagens ja tem PNG na pasta."""
        return sum(
            1 for sprite_name, _, _ in CHARACTER_LABELS if assets.has_sprite(sprite_name)
        )

    def _draw_cast(self, surface: pygame.Surface) -> None:
        """Elenco em linha, cada um com placeholder ou sprite real."""
        count = len(CHARACTER_LABELS)
        slot_w, slot_h = 150, 190
        gap = 24
        total_w = count * slot_w + (count - 1) * gap
        start_x = (settings.SCREEN_WIDTH - total_w) // 2
        top = 240

        for i, (sprite_name, label, short_label) in enumerate(CHARACTER_LABELS):
            x = start_x + i * (slot_w + gap)
            rect = pygame.Rect(x, top, slot_w, slot_h)

            draw_panel(
                surface,
                rect,
                color=settings.COLOR_PANEL_LIGHT,
                border_color=settings.COLOR_PANEL_LIGHT,
            )

            image_box = (78, 110)
            sprite = assets.load_sprite(
                sprite_name,
                box=image_box,
                label=short_label,
            )
            # a proporcao varia por sprite, entao centraliza na area
            sprite_rect = sprite.get_rect(
                center=(rect.centerx, rect.top + 16 + image_box[1] // 2)
            )
            surface.blit(sprite, sprite_rect)

            draw_text(surface, label, 20, (rect.centerx, rect.bottom - 34), settings.COLOR_TEXT)

            if assets.has_sprite(sprite_name):
                status = "sprite ok"
                status_color = settings.COLOR_ACCENT
            else:
                status = "aguardando sprite"
                status_color = settings.COLOR_TEXT_DIM
            draw_text(surface, status, 16, (rect.centerx, rect.bottom - 14), status_color)

    def _draw_menu(self, surface: pygame.Surface) -> None:
        for item in self.menu:
            color = settings.COLOR_PANEL
            border = None
            if item.selected:
                color = settings.COLOR_PANEL_LIGHT
                border = settings.COLOR_ACCENT
            elif item.hovered:
                color = settings.COLOR_PANEL_LIGHT

            draw_panel(surface, item.rect, color=color, border_color=border, border_width=2)

            text_color = settings.COLOR_TEXT
            if item.selected:
                text_color = settings.COLOR_ACCENT
            draw_text(surface, item.label, 26, item.rect.center, text_color)

            if item.selected:
                marker_w = 8
                mx = item.rect.left - 26
                my = item.rect.centery
                pygame.draw.polygon(
                    surface,
                    settings.COLOR_ACCENT,
                    [(mx, my - marker_w), (mx + marker_w, my), (mx, my + marker_w)],
                )

    def _draw_footer(self, surface: pygame.Surface) -> None:
        center_x = settings.SCREEN_WIDTH // 2
        draw_text(
            surface,
            "setas / W S  navegar      enter  confirmar      esc  sair",
            18,
            (center_x, settings.SCREEN_HEIGHT - 58),
            settings.COLOR_TEXT_DIM,
        )

        # so mostra onde colocar os PNGs enquanto faltar algum
        if self._sprites_ready() < len(CHARACTER_LABELS):
            draw_text(
                surface,
                "coloque os PNGs em assets/sprites/ (protagonista, estranho, "
                "mulher_misteriosa, rei_mago)",
                16,
                (center_x, settings.SCREEN_HEIGHT - 30),
                (110, 104, 126),
            )
        else:
            draw_text(
                surface,
                "python tools/make_pixelart.py  gera os sprites de novo",
                16,
                (center_x, settings.SCREEN_HEIGHT - 30),
                (110, 104, 126),
            )

        if self.notice:
            draw_text(
                surface,
                self.notice,
                22,
                (center_x, settings.SCREEN_HEIGHT - 92),
                settings.COLOR_DANGER,
            )


def _pulse(time: float, period: float) -> float:
    """Valor oscilando entre -1 e 1."""
    import math

    return math.sin(time * 2.0 * 3.14159 / period)
