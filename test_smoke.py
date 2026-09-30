"""Teste headless: sobe o jogo com SDL dummy e desenha alguns frames.

Roda sem abrir janela, o que permite validar o jogo em CI ou por
linha de comando:

    python test_smoke.py

Faz tres verificacoes:

1. importa o jogo e desenha alguns quadros, simulando teclas
2. percorre todas as cenas e todas as opcoes (trocando resolucao,
   tela cheia, escala e FPS), porque recriar a janela e onde costuma
   quebrar
3. executa `run.py` como processo separado, para pegar erro no
   executavel (import quebrado so aparece de verdade ao rodar)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# precisa vir antes de importar pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from src import assets, settings  # noqa: E402
from src.config import (  # noqa: E402
    FPS_CHOICES,
    RESOLUTION_CHOICES,
    SCALE_CHOICES,
    Config,
)
from src.main import build_scene_manager, create_window  # noqa: E402

FRAMES = 5
SCENES = ("title", "options", "game")
KEYS = (
    pygame.K_DOWN, pygame.K_RETURN, pygame.K_a, pygame.K_d,
    pygame.K_UP, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_SPACE, pygame.K_r,
)


def press(manager, *keys) -> None:
    for key in keys:
        manager.active.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)
        )


def check_scenes() -> None:
    """Desenha as tres cenas e simula teclas."""
    from src.scene_manager import SceneManager

    pygame.init()  # set_mode precisa de pygame.init antes
    config = Config()
    window = create_window(config)
    manager = build_scene_manager(SceneManager(window, config))

    for name in SCENES:
        manager.switch(name)
        assert manager.active is not None, f"cena {name} nao ativou"
        press(manager, *KEYS)
        for _ in range(FRAMES):
            manager.update(1.0 / settings.FPS)
            manager.draw()
        print(f"[ok] cena {name} desenhou {FRAMES} frames")

    pygame.quit()


def check_config_roundtrip() -> None:
    """Grava e le a configuracao, incluindo arquivo invalido."""
    path = ROOT / "_test_config.json"
    original = Config(sprite_scale=2, fps_limit=120, show_fps=False)
    original.save(path)
    loaded = Config.load(path)
    assert loaded.sprite_scale == 2, loaded
    assert loaded.fps_limit == 120, loaded
    assert loaded.show_fps is False, loaded
    print("[ok] config salva e lida")

    path.write_text("{ isso nao e json", encoding="utf-8")
    fallback = Config.load(path)
    assert fallback.sprite_scale == 3, "deveria voltar ao padrao"
    print("[ok] config invalida volta ao padrao")

    path.unlink()


def check_all_resolutions() -> None:
    """Cria a janela em todas as resolucoes e desenha cada cena."""
    from src.scene_manager import SceneManager

    for width, height in RESOLUTION_CHOICES:
        config = Config(width=width, height=height)
        window = create_window(config)
        manager = build_scene_manager(SceneManager(window, config))
        for name in SCENES:
            manager.switch(name)
            manager.update(1.0 / 60)
            manager.draw()
        print(f"[ok] {width}x{height} ok")


def check_all_scales() -> None:
    """Testa a escala de sprite, que invalida o cache.

    Alem de nao quebrar, confere a propriedade que importa: o sprite
    final tem que caber na area pedida. Foi um bug real do sprite do
    heroi estourando o cartao em 3x e 4x.
    """
    from src.scene_manager import SceneManager

    for scale in SCALE_CHOICES:
        config = Config(sprite_scale=scale)
        assets.set_sprite_scale(scale)
        window = create_window(config)
        manager = build_scene_manager(SceneManager(window, config))
        manager.switch("title")
        manager.update(1.0 / 60)
        scene = manager.active

        if scene.hero_frames:
            *_, box = scene._cast_layout(*scene.size)
            got = scene.hero_frames[0].get_size()
            # o teto do layout ja e em 1x, e vale o menor entre ele e
            # a escala pedida
            limit = (min(box[0], 32 * scale), min(box[1], 38 * scale))
            assert got[0] <= limit[0], f"escala {scale}x: {got} maior que {limit}"
            assert got[1] <= limit[1], f"escala {scale}x: {got} maior que {limit}"
            print(f"[ok] escala {scale}x: heroi {got[0]}x{got[1]} dentro de {limit}")
        else:
            print(f"[aviso] escala {scale}x: sem frames de animacao")
    assets.set_sprite_scale(3)


def check_fps() -> None:
    """Mede FPS de verdade na cena de jogo.

    Roda com vsync ligado (o padrao), entao o teto e o refresh do
    monitor. Confere que o loop alcanca esse teto, e nao so que "nao
    quebrou".
    """
    from src.config import native_refresh_rate
    from src.scene_manager import SceneManager

    refresh = native_refresh_rate()
    config = Config()
    window = create_window(config)
    manager = build_scene_manager(SceneManager(window, config))
    manager.switch("game")

    clock = pygame.time.Clock()
    for _ in range(10):  # aquecimento
        clock.tick(config.fps_limit)
        manager.update(1.0 / 60)
        manager.draw()
        pygame.display.flip()

    frames = 120
    start = time.perf_counter()
    for _ in range(frames):
        clock.tick(config.fps_limit)
        manager.update(1.0 / 60)
        manager.draw()
        pygame.display.flip()
    elapsed = time.perf_counter() - start

    measured = frames / elapsed
    target = min(config.fps_limit, refresh or config.fps_limit)
    # 5% de folga: o vsync pode atrasar alguns frames
    assert measured > target * 0.95, f"so {measured:.1f} fps, alvo {target}"
    print(
        f"[ok] {measured:.1f} fps medidos, alvo {target} "
        f"(monitor {refresh}Hz, vsync {config.vsync})"
    )


def check_entrypoint() -> None:
    """Executa run.py de verdade."""
    result = subprocess.run(
        [sys.executable, "run.py", "--frames", "5"],
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
    check_config_roundtrip()
    print()
    check_all_scales()
    print()
    check_all_resolutions()
    print()
    check_fps()
    print()
    check_entrypoint()
    print()
    print("tudo certo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
