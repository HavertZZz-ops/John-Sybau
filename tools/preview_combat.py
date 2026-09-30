"""Preview da cena de combate, em varios momentos da luta.

    python tools/preview_combat.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src import assets  # noqa: E402
from src.combat import Acao  # noqa: E402
from src.config import Config  # noqa: E402
from src.input_map import InputMap  # noqa: E402
from src.main import build_scene_manager  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402

W, H = 1280, 720


def main() -> int:
    pygame.init()
    config = Config(width=W, height=H, sprite_scale=3)
    assets.set_sprite_scale(config.sprite_scale)
    window = pygame.display.set_mode(config.size)
    manager = build_scene_manager(
        SceneManager(window, config, InputMap(config.bindings))
    )
    manager.ui_state.clear()
    manager.switch("combat")
    cena = manager.active

    out = ROOT

    def salvar(nome: str) -> None:
        manager.draw()
        pygame.image.save(window, out / nome)
        print(f"  {nome}")

    dt = 1 / 60

    # 1. a luta comecando: barras ainda vazias
    for _ in range(10):
        manager.update(dt)
    salvar("preview_combate_inicio.png")

    # 2. a vez do heroi: menu aberto, barra cheia
    for _ in range(600):
        manager.update(dt)
        if cena.batalha.turno_heroi:
            break
    print(f"vez do heroi: {cena.batalha.turno_heroi}, menu: {cena.menu_aberto}")
    salvar("preview_combate_menu.png")

    # 3. no meio de um golpe
    cena._escolher(Acao.ATACAR)
    for _ in range(4):
        manager.update(dt)
    salvar("preview_combate_golpe.png")

    # 4. depois de apanhar
    for _ in range(240):
        manager.update(dt)
    salvar("preview_combate_dano.png")

    # 5. o fim
    for _ in range(9000):
        manager.update(dt)
        if cena.batalha.turno_heroi and not cena.batalha.concluida:
            cena._escolher(Acao.ATACAR)
        if cena.batalha.concluida:
            break
    salvar("preview_combate_fim.png")
    print(
        f"fim: concluida={cena.batalha.concluida} "
        f"vencida={cena.batalha.vencida} heroi={cena.batalha.heroi.vida}"
    )

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())