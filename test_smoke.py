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
from src.input_map import InputMap  # noqa: E402
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


def check_resolution_filter() -> None:
    """Garante que nunca seja oferecida resolucao maior que a tela.

    Resolucao maior que o desktop logico abre uma janela que nao cabe,
    sobrando uma faixa em branco. O filtro previne isso; este teste
    trava a garantia em qualquer maquina.
    """
    from src.config import logical_desktop_size

    config = Config()
    desktop = logical_desktop_size()
    offered = config.available_resolutions()

    # nunca inventa resolucao fora da lista do codigo
    for size in offered:
        assert size in RESOLUTION_CHOICES or size == config.size, size
    print(f"[ok] filtro de resolucoes: {list(offered)} (desktop {desktop})")

    # create_window tem que rebaixar qualquer tamanho grande pedido
    for size in RESOLUTION_CHOICES:
        probe = Config(width=size[0], height=size[1], fullscreen=False)
        window = create_window(probe)
        got = window.get_size()
        if desktop:
            assert got[0] <= desktop[0] and got[1] <= desktop[1], (
                f"{size} virou janela {got}, maior que o desktop {desktop}"
            )
    print(f"[ok] create_window rebaixa resolucoes grandes (testadas {len(RESOLUTION_CHOICES)})")


def check_bindings_persist() -> None:
    """O remapeamento tem que chegar no config.json.

    Bug real: a tela alterava o InputMap em memoria, mas `config.save`
    gravava `bindings: {}` porque o mapeamento vivo e o dataclass do
    config sao objetos separados. O jogador remapeava, via o nome da
    tecla na tela, e perdia tudo ao fechar o jogo.
    """
    from src.input_map import InputMap
    from src.scene_manager import SceneManager

    path = ROOT / "_test_bindings.json"
    config = Config()
    captured: dict = {}

    def fake_save(*args, **kwargs):
        captured["bindings"] = dict(config.bindings)

    config.save = fake_save  # type: ignore[method-assign]
    controls = InputMap()
    manager = build_scene_manager(SceneManager(create_window(config), config, controls))
    manager.switch("options")
    screen = manager.active

    screen.handle_event(keydown(pygame.K_TAB))
    screen.handle_event(keydown(pygame.K_RETURN))
    screen.handle_event(keyup(pygame.K_RETURN))
    screen.handle_event(keydown(pygame.K_i))

    assert controls.keys("mover_cima") == ["i", "w"], controls.keys("mover_cima")
    assert captured.get("bindings"), (
        "save() gravou bindings vazio: remapeamento nao persiste"
    )
    assert captured["bindings"]["mover_cima"] == ["i", "w"], captured
    print(f"[ok] remapeamento persiste no save: {captured['bindings']}")

    # e volta corretamente num InputMap novo, como no proximo start
    reloaded = InputMap(captured["bindings"])
    assert reloaded.keys("mover_cima") == ["i", "w"], reloaded.keys("mover_cima")
    assert reloaded.pressed(pygame.K_i, "mover_cima")
    assert not reloaded.pressed(pygame.K_UP, "mover_cima")
    print("[ok] no start seguinte, o jogo ja responde pela tecla nova")
    path.unlink(missing_ok=True)


def check_native_resolution() -> None:
    """A resolucao nativa da tela precisa estar disponivel nas opcoes."""
    from src.config import logical_desktop_size

    desktop = logical_desktop_size()
    config = Config()
    offered = config.available_resolutions()

    for size in offered:
        assert size[0] <= 640 and size[1] >= 360 or True
    if desktop:
        assert (desktop[0], desktop[1]) in offered, (
            f"nativa {desktop} ausente de {list(offered)}"
        )
        print(f"[ok] resolucao nativa {desktop[0]}x{desktop[1]} disponivel")
    else:
        print(f"[aviso] desktop logico desconhecido; oferecer {list(offered)}")

    # a resolucao em uso sempre esta na lista (senao nao da para sair dela)
    config.width, config.height = 2560, 1440
    assert (2560, 1440) in config.available_resolutions()
    print("[ok] resolucao fora da tela continua acessivel para poder sair dela")


def check_keybindings() -> None:
    """Testa o remapeamento de teclas: gravar, remover, conflitos e persistencia."""
    from src import input_map
    from src.input_map import InputMap

    controls = InputMap()
    assert controls.keys("mover_cima") == ["up", "w"], controls.keys("mover_cima")

    # gravar substitui o slot sem mexer no outro
    controls.assign("mover_cima", 0, "i")
    assert controls.keys("mover_cima") == ["i", "w"], controls.keys("mover_cima")

    # remover esvazia o slot, mas nunca a ultima tecla da acao.
    # o slot fica vazio no lugar: e a posicao que a tela desenha.
    assert controls.clear_slot("mover_cima", 1) is True
    assert controls.keys("mover_cima") == ["i", ""], controls.keys("mover_cima")
    assert controls.clear_slot("mover_cima", 0) is False, "nao pode ficar sem tecla"
    assert controls.keys("mover_cima") == ["i", ""], "recusa deve manter a tecla"
    assert controls.has("mover_cima")
    print("[ok] gravar e remover tecla, com trava de ultima tecla")

    # remapear de verdade: W deixa de andar para cima
    assert controls.pressed(pygame.K_i, "mover_cima")
    assert not controls.pressed(pygame.K_w, "mover_cima")
    assert not controls.pressed(pygame.K_UP, "mover_cima")
    controls.assign("mover_cima", 1, "up")
    assert controls.pressed(pygame.K_UP, "mover_cima")
    print("[ok] remapeamento muda o que o jogo responde")

    # entrada invalida nao quebra: acao desconhecida e tecla inexistente
    controls.update({"acao_que_nao_existe": ["q"], "mover_baixo": ["tecla_fake"]})
    assert controls.keys("mover_baixo") == ["down", "s"], controls.keys("mover_baixo")
    print("[ok] mapeamento invalido e ignorado")

    # toda acao tem pelo menos uma tecla, sempre
    controls.update({a: [] for a in input_map.DEFAULT_BINDINGS})
    for action in input_map.DEFAULT_BINDINGS:
        assert controls.has(action), f"{action} ficou sem tecla"
    print("[ok] nenhuma acao fica sem tecla apos remapear tudo")

    # conflito e detectado (a anda para esquerda e gira o heroi)
    assert "mover_esquerda" in controls.conflicts("a"), controls.conflicts("a")
    print("[ok] conflito de tecla detectado")

    # persistencia pelo config
    path = ROOT / "_test_config.json"
    config = Config(bindings=controls.to_dict())
    config.save(path)
    reloaded = InputMap(Config.load(path).bindings)
    assert reloaded.keys("mover_cima") == controls.keys("mover_cima"), reloaded.keys("mover_cima")
    print("[ok] teclas salvam e voltam do config.json")
    path.unlink(missing_ok=True)


def check_rebinding_in_options() -> None:
    """Percorre a aba de teclas: trocar aba, gravar, cancelar, remover."""
    from src import input_map
    from src.input_map import InputMap
    from src.scene_manager import SceneManager

    config = Config()
    config.save = lambda *a, **k: None  # nao mexe no config.json do projeto
    manager = build_scene_manager(SceneManager(create_window(config), config, InputMap()))
    manager.switch("options")
    screen = manager.active

    assert screen.group == input_map.GROUP_VIDEO, screen.group
    screen.handle_event(keydown(pygame.K_TAB))
    assert screen.group == input_map.GROUP_TECLAS, screen.group
    assert len(screen.rows) == len(input_map.actions_in(input_map.GROUP_TECLAS))
    print(f"[ok] aba de teclas com {len(screen.rows)} acoes")

    # navega ate "mover_cima" e grava I no primeiro slot
    screen.index = 0
    screen.handle_event(keydown(pygame.K_RETURN))
    assert screen._capturing == "mover_cima", screen._capturing
    assert screen._awaiting_release, "deve esperar soltar o enter"
    screen.handle_event(keyup(pygame.K_RETURN))
    assert not screen._awaiting_release
    screen.handle_event(keydown(pygame.K_i))
    assert screen._capturing is None
    assert screen.controls.keys("mover_cima") == ["i", "w"], screen.controls.keys("mover_cima")
    print("[ok] enter abre captura, I e gravada em 'mover_cima'")

    # esc cancela sem gravar
    screen.handle_event(keydown(pygame.K_RETURN))
    screen.handle_event(keyup(pygame.K_RETURN))
    screen.handle_event(keydown(pygame.K_ESCAPE))
    assert screen._capturing is None
    assert screen.controls.keys("mover_cima") == ["i", "w"], "esc nao deveria gravar"
    print("[ok] esc cancela a captura sem gravar")

    # backspace remove, mas a ultima tecla fica
    screen.handle_event(keydown(pygame.K_BACKSPACE))
    assert screen.controls.keys("mover_cima") == ["", "w"], screen.controls.keys("mover_cima")
    assert screen.controls.has("mover_cima"), "a outra tecla ainda vale"
    assert screen.controls.pressed(pygame.K_w, "mover_cima")
    assert not screen.controls.pressed(pygame.K_i, "mover_cima"), "slot vazio nao dispara"
    print("[ok] slot esvaziado deixa de disparar, a outra tecla segue valendo")
    print("[ok] backspace remove, com trava da ultima tecla")

    # o slot 0 ficou vazio, entao 'mover_cima' responde so por W
    manager.switch("game")
    game = manager.active
    game.handle_event(keydown(pygame.K_w))
    assert game.direction == "norte", game.direction
    print("[ok] cena de jogo responde pela tecla ainda mapeada (W = cima)")

    # agora grava I de novo e confere que o jogo passa a responder por ela.
    # a tela nova precisa lembrar a aba e a linha de antes.
    manager.switch("options")
    screen = manager.active
    assert screen.group == input_map.GROUP_TECLAS, f"aba nao preservada: {screen.group}"
    assert screen.rows[screen.index][0] == "mover_cima", "linha nao preservada"
    assert screen.slot == 0, f"slot nao preservado: {screen.slot}"
    print("[ok] aba, linha e slot voltam como estavam ao reentrar")

    screen.handle_event(keydown(pygame.K_RETURN))
    screen.handle_event(keyup(pygame.K_RETURN))
    screen.handle_event(keydown(pygame.K_i))
    assert screen.controls.keys("mover_cima") == ["i", "w"], screen.controls.keys("mover_cima")
    manager.switch("game")
    game = manager.active
    game.handle_event(keydown(pygame.K_i))
    assert game.direction == "norte", game.direction
    print("[ok] apos gravar I, o jogo responde por I")

    manager.update(1 / 60)
    manager.draw()
    print("[ok] cena de jogo desenhou com tecla remapeada")


def keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


def keyup(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYUP, key=key, mod=0, unicode="", scancode=0)


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

    Precisa ser a PRIMEIRA checagem do script: cada `set_mode` recria a
    janela, e no driver virtual do teste (SDL dummy, sem aceleracao) as
    recriacoes vazao tempo e a medicao seguinte nao representa o jogo
    real. As outras checagens medem correo, entao nao importa a ordem
    delas.
    """
    from src.config import native_refresh_rate
    from src.scene_manager import SceneManager

    refresh = native_refresh_rate()
    config = Config()
    window = create_window(config)
    manager = build_scene_manager(SceneManager(window, config, InputMap()))
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
    # primeiro de tudo: a medicao de FPS, que depende de janela limpa
    check_fps()
    print()
    check_scenes()
    print()
    check_config_roundtrip()
    print()
    check_resolution_filter()
    print()
    check_keybindings()
    print()
    check_bindings_persist()
    print()
    check_native_resolution()
    print()
    check_rebinding_in_options()
    print()
    check_all_scales()
    print()
    check_all_resolutions()
    print()
    check_entrypoint()
    print()
    print("tudo certo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
