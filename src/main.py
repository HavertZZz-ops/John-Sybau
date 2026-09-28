"""Ponto de entrada do jogo.

Executa o loop principal: pump de eventos, update com delta time,
desenho e controle de FPS.
"""
from __future__ import annotations

import sys

import pygame

from . import settings
from .scene_manager import SceneManager
from .title_screen import TitleScreen


def build_scene_manager(window: pygame.Surface) -> SceneManager:
    manager = SceneManager(window)
    manager.register("title", TitleScreen)
    return manager


def main() -> int:
    pygame.init()
    pygame.display.set_caption(settings.GAME_TITLE)

    window = pygame.display.set_mode(
        (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
    )
    clock = pygame.time.Clock()

    manager = build_scene_manager(window)
    manager.switch("title")

    running = True
    while running:
        dt = clock.tick(settings.FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif manager.active is not None:
                manager.active.handle_event(event)

        manager.update(dt)
        manager.draw()

        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
