"""Teste headless: sobe o jogo com SDL dummy e desenha alguns frames.

Roda sem abrir janela, o que permite validar a tela inicial em CI
ou por linha de comando:

    python test_smoke.py

Se a tela inicial quebrar (erro de sintaxe, atributo faltando,
excecao no desenho), este script falha com o traceback.
"""
from __future__ import annotations

import os
import sys

# precisa vir antes de importar pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from src import settings  # noqa: E402
from src.main import build_scene_manager  # noqa: E402

FRAMES = 5


def main() -> int:
    pygame.init()
    window = pygame.display.set_mode(
        (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
    )

    manager = build_scene_manager(window)
    manager.switch("title")
    assert manager.active is not None, "nenhuma cena ativa"
    print(f"[ok] cena ativa: {type(manager.active).__name__}")

    # simula o jogador apertando baixo duas vezes e enter
    for key in (pygame.K_DOWN, pygame.K_DOWN, pygame.K_RETURN):
        manager.active.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)
        )
    for _ in range(FRAMES):
        manager.update(1.0 / settings.FPS)
        manager.draw()

    surface = window
    if surface.get_at((5, 5))[:3] == settings.COLOR_BACKGROUND:
        print("[ok] fundo renderizado")
    else:
        print("[aviso] pixel do canto diferente do esperado")

    pygame.quit()
    print(f"[ok] {FRAMES} frames desenhados sem erro")
    return 0


if __name__ == "__main__":
    sys.exit(main())
