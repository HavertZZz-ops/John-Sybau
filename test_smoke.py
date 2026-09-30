"""Teste headless: sobe o jogo com SDL dummy e desenha alguns frames.

Roda sem abrir janela, o que permite validar a tela inicial em CI
ou por linha de comando:

    python test_smoke.py

Faz duas verificacoes:

1. importa o jogo e desenha alguns quadros direto (pega erro de logica)
2. executa `run.py` como processo separado (pega erro no executavel,
   tipo import quebrado, que so aparece de verdade ao rodar o script)

Se algo quebrar, este script falha com o traceback.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# precisa vir antes de importar pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from src import settings  # noqa: E402
from src.main import build_scene_manager  # noqa: E402

FRAMES = 5


def check_scenes() -> None:
    """Desenha alguns quadros e simula teclas."""
    pygame.init()
    window = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))

    manager = build_scene_manager(window)
    manager.switch("title")
    assert manager.active is not None, "nenhuma cena ativa"
    print(f"[ok] cena ativa: {type(manager.active).__name__}")

    for key in (pygame.K_DOWN, pygame.K_DOWN, pygame.K_RETURN, pygame.K_a):
        manager.active.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)
        )
    for _ in range(FRAMES):
        manager.update(1.0 / settings.FPS)
        manager.draw()

    if window.get_at((5, 5))[:3] == settings.COLOR_BACKGROUND:
        print("[ok] fundo renderizado")
    else:
        print("[aviso] pixel do canto diferente do esperado")

    pygame.quit()
    print(f"[ok] {FRAMES} frames desenhados sem erro")


def check_entrypoint() -> None:
    """Executa run.py de verdade, como quem joga."""
    result = subprocess.run(
        [sys.executable, "run.py", "--frames", "3"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        print("[FALHA] run.py nao rodou:")
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(result.returncode)
    print("[ok] run.py executou e saiu com codigo 0")


def main() -> int:
    check_scenes()
    print()
    check_entrypoint()
    print()
    print("tudo certo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
