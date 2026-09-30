"""Mede o FPS real da masmorra, desenhando de verdade.

O contador do jogo roda a 22 fps quando a tela e grande, e nenhum teste
headless pegou isso: em SDL dummy nao existe custo de blit. Aqui a
superficie e real, do mesmo tamanho da janela, e o desenho acontece de
verdade.

    python tools/medir_fps_dungeon.py [largura] [altura]
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# SEM SDL dummy: aqui o custo de blit e real, que e o que medimos
os.environ.pop("SDL_VIDEODRIVER", None)

import pygame  # noqa: E402

from src import assets  # noqa: E402
from src.config import Config  # noqa: E402
from src.input_map import InputMap  # noqa: E402
from src.main import build_scene_manager  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402

W = int(sys.argv[1]) if len(sys.argv) > 1 else 1520
H = int(sys.argv[2]) if len(sys.argv) > 2 else 921
QUADROS = 180


def main() -> int:
    pygame.init()
    config = Config(width=W, height=H, sprite_scale=3)
    assets.set_sprite_scale(config.sprite_scale)

    flags = pygame.SCALED if config.fullscreen else 0
    window = pygame.display.set_mode(config.size, flags)
    manager = build_scene_manager(
        SceneManager(window, config, InputMap(config.bindings))
    )
    manager.ui_state.clear()
    manager.switch("dungeon")
    cena = manager.active

    # pula a abertura, para medir a cena em jogo
    for _ in range(int(6.0 * 30)):
        manager.update(1 / 30)
    cena.fase = "livre"
    cena.tampa = 1.0
    # o esqueleto NA tela: e ele que derrubava o jogo para 22 fps,
    # e o medidor sem ele nao via o problema
    cena.esqueleto = pygame.Vector2(cena.posicao) + pygame.Vector2(90, 0)

    # aquece: a primeira passada paga o cache de tiles
    for _ in range(20):
        manager.update(1 / 60)
        manager.draw()

    dt = 1 / 60
    inicio = time.perf_counter()
    for _ in range(QUADROS):
        manager.update(dt)
        manager.draw()
    pygame.display.flip()
    gasto = time.perf_counter() - inicio

    fps = QUADROS / gasto
    ms = gasto / QUADROS * 1000
    print(f"superficie: {W} x {H}  escala dos sprites: 3")
    print(f"quadros: {QUADROS} em {gasto:.2f}s")
    print(f"FPS: {fps:.1f}   ({ms:.2f} ms por quadro)")
    if fps < 45:
        print("ABAIXO DO ESPERADO: 60 fps precisa de menos de 16.7 ms por quadro")
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())