"""Tela inicial minimalista, no estilo Dark Souls.

Sem paineis, sem bordas, sem icones: texto sobre o escuro. O item
selecionado respira em dourado, com um losango pequeno a esquerda. A
transicao entre cenas e um fade, como nos jogos de referencia.

O elenco (personagens) fica escondido atras de uma tecla, para nao
poluir o menu principal.
"""
from __future__ import annotations

from typing import List, Tuple

import pygame

from . import assets, settings, theme
from .scene import Scene

MENU_ITEMS: Tuple[str, ...] = ("Comecar", "Opcoes", "Sair")

# atalhos de teclado para as cenas, vindos do mapa do jogador
SCENE_SHORTCUTS: Tuple[Tuple[str, str, str], ...] = (
    ("Iniciar jogo", "game", "comecar"),
    ("Opcoes", "options", "opcoes"),
    ("Sair", "title", "sair"),
)


class TitleScreen(Scene):
    """Menu principal, so texto sobre o fundo escuro."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.index = 0
        self.time = 0.0
        self.notice: str | None = None
        self.notice_timer = 0.0
        # fade ao entrar: comeca escuro e clareia
        self.fade = 1.0
        self._layout()
        self._sync()

    # layout --------------------------------------------------------
    def _layout(self) -> None:
        w, h = self.size
        center_x = w // 2
        # itens no terco inferior, com espacamento vertical calmo
        base_y = int(h * 0.56)
        step = max(40, int(h * 0.085))
        self._positions = [(center_x, base_y + i * step) for i in range(len(MENU_ITEMS))]
        self.title_pos = (center_x, int(h * 0.20))
        self.hint_y = int(h * 0.94)

    def on_enter(self) -> None:
        self.index = 0
        self.fade = 1.0
        self._layout()
        self._sync()

    def _sync(self) -> None:
        return  # nada de estado por item; o desenho calcula direto

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
            return
        if event.type != pygame.KEYDOWN:
            return

        if self.key(event, "mover_cima"):
            self.index = (self.index - 1) % len(MENU_ITEMS)
        elif self.key(event, "mover_baixo"):
            self.index = (self.index + 1) % len(MENU_ITEMS)
        elif self.key(event, "confirmar"):
            self._activate()
        elif self.key(event, "voltar"):
            self.manager.quit()

    def _click(self, pos: Tuple[int, int]) -> None:
        font = theme.Fonts.get(int(self.size[1] * 0.038))
        for i, center in enumerate(self._positions):
            rect = font.render(MENU_ITEMS[i], True, theme.TEXT)
            rect = rect.get_rect(center=center)
            # um pouco de folga, para o clique nao ser surgical
            rect.inflate_ip(40, 12)
            if rect.collidepoint(pos):
                self.index = i
                self._activate()
                return

    def _activate(self) -> None:
        label = MENU_ITEMS[self.index].lower()
        if label == "comecar":
            self.manager.switch("game")
        elif label == "opcoes":
            self.manager.switch("options")
        else:
            self.manager.quit()

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        if self.fade > 0.0:
            self.fade = max(0.0, self.fade - dt * 1.6)
        if self.notice_timer > 0.0:
            self.notice_timer -= dt
            if self.notice_timer <= 0.0:
                self.notice = None

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        w, h = self.size

        # um vinheta sutil, para o olho ir pro centro
        self._draw_vignette(surface, w, h)

        # titulo, espacado, bem alto
        theme.text_tracked(
            surface, "JOHN SYBAU", int(h * 0.075), self.title_pos,
            theme.TEXT_BRIGHT, tracking=6,
        )
        theme.hairline(surface, w // 2 - int(w * 0.08), int(h * 0.28),
                       w // 2 + int(w * 0.08))

        # itens
        breath = theme.pulse(self.time, 1.2)
        font_size = int(h * 0.042)
        for i, center in enumerate(self._positions):
            selected = i == self.index
            if selected:
                color = theme.lerp(theme.GOLD, theme.GOLD_BRIGHT, breath)
            else:
                color = theme.TEXT_DIM
            box = theme.text_tracked(
                surface, MENU_ITEMS[i], font_size, center, color, tracking=4,
            )
            # losango logo ao lado do item selecionado
            if selected:
                d = 4 + int(breath * 2)
                cx = box.left - 28
                cy = center[1]
                pygame.draw.polygon(
                    surface, color,
                    [(cx - d, cy), (cx, cy - d), (cx + d, cy), (cx, cy + d)],
                )

        # dica embaixo
        self._draw_hint(surface, w, h)

        # fade de entrada
        if self.fade > 0.0:
            theme.fade_surface(surface, int(self.fade * 255))

    def _draw_vignette(self, surface: pygame.Surface, w: int, h: int) -> None:
        """Escurece as bordas, como a luz de uma vela no centro.

        Aneis concentricos, do maior para o menor, cada um com um
        pouco de preto translucido. Precisa de uma superficie SRCALPHA:
        desenhar alpha direto no display nao sobrepoe nada.
        """
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        max_r = int((w * w + h * h) ** 0.5) // 2
        rings = 20
        for i in range(rings, 0, -1):
            r_out = max_r * i // rings
            alpha = 3 if i < rings // 2 else 6
            pygame.draw.ellipse(
                veil, (0, 0, 0, alpha),
                pygame.Rect(cx - r_out, cy - r_out, r_out * 2, r_out * 2),
                width=max(2, max_r // rings + 1),
            )
        surface.blit(veil, (0, 0))

    def _draw_hint(self, surface: pygame.Surface, w: int, h: int) -> None:
        up = "/".join(self.controls.labels("mover_cima"))
        down = "/".join(self.controls.labels("mover_baixo"))
        ok = "/".join(self.controls.labels("confirmar"))
        hint = f"{up or 'seta'} {down or 'seta'} navegar    {ok or 'enter'} confirmar"
        theme.text_tracked_at(
            surface, hint, int(h * 0.022), (int(w * 0.06), self.hint_y),
            theme.HAIRLINE, tracking=1,
        )
        if self.notice:
            theme.text_tracked(
                surface, self.notice, int(h * 0.028),
                (w // 2, int(h * 0.70)), theme.GOLD, tracking=2,
            )
