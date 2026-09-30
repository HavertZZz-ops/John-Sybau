"""Roda a abertura das Catacumbas e salva quadros em PNG.

Serve para ver a sequencia sem jogar: o caixao range, a tampa desliza,
o heroi sai e o nome do lugar aparece. Cada quadro e um PNG.

    python tools/preview_dungeon.py [segundos]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from src import assets
from src.config import Config
from src.input_map import InputMap
from src.main import build_scene_manager
from src.scene_manager import SceneManager

TOTAL = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
PASSO = 1 / 30


def main() -> int:
    pygame.init()
    config = Config(width=1280, height=720, sprite_scale=3)
    assets.set_sprite_scale(config.sprite_scale)

    window = pygame.display.set_mode(config.size)
    manager = SceneManager(window, config, InputMap(config.bindings))
    build_scene_manager(manager)
    manager.switch("dungeon")
    scene = manager.active

    out = ROOT / "assets" / "tiles"
    out.mkdir(parents=True, exist_ok=True)

    print("fases da abertura:")
    anterior = scene.fase
    gravados = 0
    # um quadro por segundo e mais os momentos chave da tampa
    for passo in range(int(TOTAL / PASSO)):
        manager.update(PASSO)
        manager.draw()

        if scene.fase != anterior:
            pygame.image.save(
                window, out / f"_abertura_{scene.fase}.png"
            )
            print(f"  {anterior} -> {scene.fase}")
            anterior = scene.fase
            gravados += 1

    # sempre salva um quadro em cada metade da abertura
    manager.update(PASSO)
    manager.draw()
    pygame.image.save(window, out / "_abertura_fim.png")
    print(f"  fim: fase={scene.fase} tampa={scene.tampa:.2f} "
          f"titulo_ativo={scene.titulo.active}")
    print("salvo em", out)
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())