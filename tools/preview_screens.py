"""Gera previews das telas novas: menu com save e a masmorra.

    python tools/preview_screens.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src import assets, saves  # noqa: E402
from src.config import Config  # noqa: E402
from src.input_map import InputMap  # noqa: E402
from src.main import build_scene_manager  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402

W, H = 1280, 720
DT = 1 / 30


def novo_manager():
    pygame.init()
    config = Config(width=W, height=H, sprite_scale=3)
    assets.set_sprite_scale(config.sprite_scale)
    window = pygame.display.set_mode(config.size)
    manager = build_scene_manager(
        SceneManager(window, config, InputMap(config.bindings))
    )
    manager.ui_state.clear()
    return manager, window


def main() -> int:
    manager, window = novo_manager()

    # --- menu sem save: so Novo jogo aparece ---
    manager.ui_state["store"] = saves.ArquivoSaveStore(
        Path(tempfile.gettempdir()) / "preview_save.json"
    )
    manager.ui_state["store"].apagar()
    manager.switch("title")
    cena = manager.active
    cena.fade = 0.0
    for _ in range(6):
        manager.update(DT)
        manager.draw()
    pygame.image.save(window, ROOT / "preview_menu_novo.png")
    print("menu sem save:", cena._visiveis)

    # --- menu com save: Continuar aparece ---
    manager.ui_state["store"].salvar(saves.Save(
        area="catacumbas", x=1180.0, y=640.0, direcao="oeste",
        tempo_jogado=4210.0,
    ))
    manager.switch("title")
    cena = manager.active
    cena.fade = 0.0
    for _ in range(6):
        manager.update(DT)
        manager.draw()
    pygame.image.save(window, ROOT / "preview_menu_continuar.png")
    print("menu com save:", cena._visiveis, "|", cena.store.descricao)

    # --- masmorra, depois da abertura ---
    manager.ui_state.clear()
    manager.ui_state["store"] = saves.ArquivoSaveStore(
        Path(tempfile.gettempdir()) / "preview_save.json"
    )
    manager.switch("dungeon")
    cena = manager.active
    for _ in range(int(3.4 / DT)):
        manager.update(DT)
    manager.draw()
    pygame.image.save(window, ROOT / "preview_dungeon_tampa.png")
    print(f"morrada na fase {cena.fase}, tampa {cena.tampa:.2f}")

    for _ in range(int(2.0 / DT)):
        manager.update(DT)
    manager.draw()
    pygame.image.save(window, ROOT / "preview_dungeon_titulo.png")
    print(f"titulo ativo: {cena.titulo.active}")

    for _ in range(int(3.0 / DT)):
        manager.update(DT)
    manager.draw()
    pygame.image.save(window, ROOT / "preview_dungeon_jogo.png")
    print(f"jogando: fase {cena.fase}, tempo {cena.tempo_jogado:.0f}s")

    # a aula na tela, no meio do cenario
    cena.tutorial.mostrar("Use as setas para andar")
    cena.tutorial.tempo = 1.2
    manager.draw()
    pygame.image.save(window, ROOT / "preview_dungeon_aula.png")
    print("aula na tela:", cena.tutorial.atual.texto)

    # o esqueleto guardado, antes da luta
    cena.passos = 999
    cena.moving = True
    manager.update(DT)
    manager.update(DT)
    manager.draw()
    pygame.image.save(window, ROOT / "preview_dungeon_esqueleto.png")
    print("esqueleto guardado:", cena.esqueleto is not None)

    manager.ui_state["store"].apagar()
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())