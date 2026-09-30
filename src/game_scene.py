"""Cena de jogo: o heroi andando num cenario de teste.

Ainda e um placeholder de gameplay, mas ja e uma cena de verdade:
o heroi anda nas 4 direcoes, a animacao troca junto com o movimento e
o cenario tem limites de tela.
"""
from __future__ import annotations

import pygame

from . import assets, settings
from .scene import Scene
from .ui import draw_text

# direcao -> (animacao do heroi, teclas que ativam)
DIRECTION_KEYS = {
    "sul": (pygame.K_s, pygame.K_DOWN),
    "norte": (pygame.K_w, pygame.K_UP),
    "leste": (pygame.K_d, pygame.K_RIGHT),
    "oeste": (pygame.K_a, pygame.K_LEFT),
}

MOVE_SPEED = 140  # pixels por segundo
MARGIN = 16


class GameScene(Scene):
    """Cena de jogo minima, com o heroi andando pelo cenario."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.direction = "sul"
        self.moving = False
        self.anim_time = 0.0
        self.frames = assets.load_animation(self.direction)
        width, height = self.size
        self.position = pygame.Vector2(width // 2, height // 2)
        self.notice: str | None = None
        self.notice_timer = 0.0

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        """A janela pode ter mudado de tamanho nas opcoes."""
        width, height = self.size
        self.position.x = max(MARGIN, min(width - MARGIN, self.position.x))
        self.position.y = max(MARGIN, min(height - MARGIN, self.position.y))
        self._reload_frames()

    def _reload_frames(self) -> None:
        self.frames = assets.load_animation(self.direction)

    def _clamp(self) -> None:
        width, height = self.size
        self.position.x = max(MARGIN, min(width - MARGIN, self.position.x))
        self.position.y = max(MARGIN, min(height - MARGIN, self.position.y))

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.manager.switch("title")
            return

        if event.type == pygame.KEYUP:
            if event.key in _keyset(self.direction):
                self.moving = False
            return

        if event.type == pygame.KEYDOWN:
            for direction, keys in DIRECTION_KEYS.items():
                if event.key in keys:
                    if direction != self.direction:
                        self.direction = direction
                        self._reload_frames()
                    self.moving = True

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        if self.notice_timer > 0.0:
            self.notice_timer -= dt
            if self.notice_timer <= 0.0:
                self.notice = None

        if not self.moving or not self.frames:
            return

        step = MOVE_SPEED * dt
        if self.direction == "sul":
            self.position.y += step
        elif self.direction == "norte":
            self.position.y -= step
        elif self.direction == "leste":
            self.position.x += step
        elif self.direction == "oeste":
            self.position.x -= step

        self._clamp()
        self.anim_time += dt

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLOR_BACKGROUND)
        self._draw_ground(surface)

        if self.frames:
            index = int(self.anim_time * assets.HERO_FPS) % len(self.frames)
            sprite = self.frames[index]
            rect = sprite.get_rect(center=self.position)
            # sombra no chao, da profundidade
            shadow = pygame.Surface(
                (sprite.get_width() * 3 // 4, max(6, sprite.get_height() // 8)),
                pygame.SRCALPHA,
            )
            pygame.draw.ellipse(
                shadow, (0, 0, 0, 70), shadow.get_rect()
            )
            surface.blit(shadow, shadow.get_rect(centerx=rect.centerx, bottom=rect.bottom))
            surface.blit(sprite, rect)
        else:
            surface.blit(
                assets.make_placeholder((64, 80), "sem sprite"),
                assets.make_placeholder((64, 80), "sem sprite").get_rect(
                    center=self.position
                ),
            )

        self._draw_hud(surface)

    def _draw_ground(self, surface: pygame.Surface) -> None:
        """Faixa de chao e uma grade, para dar referencia de movimento."""
        width, height = self.size
        ground_top = int(height * 0.68)
        pygame.draw.rect(
            surface,
            settings.COLOR_PANEL,
            pygame.Rect(0, ground_top, width, height),
        )
        pygame.draw.line(
            surface,
            settings.COLOR_PANEL_LIGHT,
            (0, ground_top),
            (width, ground_top),
            2,
        )
        step = settings.TILE_SIZE * 2
        for x in range(0, width, step):
            pygame.draw.line(surface, (38, 34, 50), (x, 0), (x, height), 1)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        width, height = self.size
        center_x = width // 2
        draw_text(
            surface,
            "CENA DE JOGO",
            44,
            (center_x, 56),
            settings.COLOR_ACCENT,
        )
        draw_text(
            surface,
            f"direcao: {self.direction}    posicao: "
            f"{int(self.position.x)}, {int(self.position.y)}",
            20,
            (center_x, 92),
            settings.COLOR_TEXT_DIM,
        )
        if self.moving:
            draw_text(
                surface,
                "andando",
                20,
                (center_x, 120),
                settings.COLOR_TEXT,
            )
        draw_text(
            surface,
            "WASD ou setas  andar      esc  voltar",
            18,
            (center_x, height - 30),
            settings.COLOR_TEXT_DIM,
        )


def _keyset(direction: str) -> tuple[int, ...]:
    return DIRECTION_KEYS.get(direction, ())
