"""Carrega o config.json de verdade, e nao um config novo.

Todos os previews deste arquivo foram feitos com `Config()` cru, que
nasce com `sprite_scale=1`. O jogo do jogador roda com 3 e janela de
1008x720. A primeira versao deste script tirou a conclusao errada de
que "os personagens estao minusculos no mapa" — era o preview que
estava errado.

A regra daqui em diante: preview e o jogo tem que usar a mesma config.
"""

from __future__ import annotations

import json
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.json"


def config_real():
    """O `Config` que o jogo abre, lido do arquivo do jogador."""
    from src.config import Config

    if not CONFIG.is_file():
        return Config()
    dados = json.loads(CONFIG.read_text(encoding="utf-8"))
    c = Config()
    for chave in ("width", "height", "fullscreen", "vsync",
                  "sprite_scale", "fps_limit"):
        if chave in dados:
            setattr(c, chave, dados[chave])
    if isinstance(dados.get("bindings"), dict):
        c.bindings = dados["bindings"]
    return c


def abrir():
    """(janela, gerenciador) com a config real e as cenas registradas."""
    import pygame

    from src.assets import set_sprite_scale
    from src.main import build_scene_manager, create_window
    from src.scene_manager import SceneManager

    config = config_real()
    pygame.init()
    janela = create_window(config)
    set_sprite_scale(config.sprite_scale)
    ger = build_scene_manager(SceneManager(janela, config))
    return janela, ger, config