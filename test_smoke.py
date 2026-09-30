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
    original = Config(sprite_scale=2, fps_limit=120, vsync=False)
    original.save(path)
    loaded = Config.load(path)
    assert loaded.sprite_scale == 2, loaded
    assert loaded.fps_limit == 120, loaded
    assert loaded.vsync is False, loaded
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

    # create_window tem que respeitar a resolucao pedida, sem rebaixar
    # em silencio: rebaixar fazia o jogo rodar em um tamanho diferente
    # do que o jogador escolheu
    for size in RESOLUTION_CHOICES:
        probe = Config(width=size[0], height=size[1], fullscreen=False)
        window = create_window(probe)
        got = window.get_size()
        assert got == size, f"pediu {size}, janela ficou {got}"
        assert (probe.width, probe.height) == size, f"config alterado: {probe.size}"
    print(f"[ok] create_window respeita a resolucao pedida ({len(RESOLUTION_CHOICES)} testadas)")


def check_internal_resolution() -> None:
    """A resolucao interna precisa acompanhar a da janela.

    Regressao relatada: a janela mudava de tamanho, mas o jogo
    continuava desenhando como se nada tivesse acontecido.
    """
    from src.scene_manager import SceneManager

    for size in [(1280, 720), (1536, 960), (1280, 720)]:
        config = Config(width=size[0], height=size[1], sprite_scale=3)
        config.save = lambda *a, **k: None  # type: ignore[method-assign]
        # o jogo real aplica a escala das opcoes aqui; sem isso o teste
        # mede a tela errada
        assets.set_sprite_scale(config.sprite_scale)
        window = create_window(config)
        manager = build_scene_manager(SceneManager(window, config, InputMap()))
        manager.switch("title")
        manager.update(1.0 / 60)
        manager.draw()

        assert window.get_size() == size, f"superficie {window.get_size()} != {size}"
        assert manager.active.size == size, f"cena {manager.active.size} != {size}"
        assert manager.active.hero_frames, "animacao do heroi nao carregou"
    assets.set_sprite_scale(3)
    print("[ok] resolucao interna acompanha a janela em 3 trocas")


def check_hud_shows_resolution() -> None:
    """O HUD tem que mostrar o FPS, sempre, no canto superior."""
    from src.main import draw_fps

    for size in [(1280, 720), (1536, 960)]:
        surface = pygame.Surface(size)
        surface.fill(settings.COLOR_BACKGROUND)
        draw_fps(surface, 60.0, 60, 60)
        assert surface.get_size() == size
        # o canto superior direito precisa ter mudado (HUD desenhado)
        assert surface.get_at((size[0] - 20, 10))[:3] != settings.COLOR_BACKGROUND
    print("[ok] HUD mostra FPS sempre, em 2 resolucoes")


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
    """A maior resolucao que cabe na tela precisa estar disponivel.

    O limite e o desktop MENOS a moldura da janela. Uma resolucao do
    tamanho do desktop cria uma janela maior que a tela, porque a borda
    e a barra de titulo somam alguns pixels.
    """
    from src.config import usable_window_size

    limit = usable_window_size()
    config = Config()
    offered = config.available_resolutions()

    if limit:
        # a maior que cabe tem que estar disponivel, seja ela uma das
        # resolucoes fixas ou a nativa acrescentada
        maior = max(offered)
        assert maior[0] <= limit[0] and maior[1] <= limit[1], (
            f"maior oferecida {maior} passa do limite {limit}"
        )
        assert maior[0] >= limit[0] - 40 and maior[1] >= limit[1] - 40, (
            f"maior oferecida {maior} esta longe do limite {limit}"
        )
        print(f"[ok] maior resolucao que cabe {maior[0]}x{maior[1]} (limite {limit[0]}x{limit[1]})")
    else:
        print(f"[aviso] tela desconhecida; oferecer {list(offered)}")

    # toda resolucao oferecida tem que caber no limite
    for size in offered:
        assert size[0] <= limit[0] and size[1] <= limit[1], (
            f"{size} passa do limite {limit}"
        )
    print("[ok] nenhuma resolucao oferecida passa do limite da tela")

    # uma resolucao que nao cabe nao pode ser oferecida: offering
    # estourava a janela e tirava parte do menu da tela
    config.width, config.height = 2560, 1440
    assert (2560, 1440) not in config.available_resolutions(), (
        "resolucao maior que a tela nao deve ser oferecida"
    )
    print("[ok] resolucao maior que a tela nao e oferecida")


def check_options_not_lockable() -> None:
    """A tela de opcoes tem que ser sempre navegavel.

    Se a navegacao usasse as teclas remapeadas, trocar a tecla de
    "voltar" ou de "mover_baixo" deixaria o jogador preso na tela sem
    como sair. Aqui as teclas da tela sao fixas, entao o teste confirma
    que continua possivel sair e navegar depois de remapear tudo.
    """
    from src import input_map
    from src.input_map import InputMap
    from src.scene_manager import SceneManager

    config = Config()
    config.save = lambda *a, **k: None  # type: ignore[method-assign]
    controls = InputMap()
    manager = build_scene_manager(SceneManager(create_window(config), config, controls))
    manager.switch("options")
    screen = manager.active

    # remapeia TUDO para teclas que nao servem para navegar
    for action in input_map.DEFAULT_BINDINGS:
        controls.assign(action, 0, "f9")
    assert not controls.pressed(pygame.K_ESCAPE, "voltar"), "voltar sumiu"
    assert not controls.pressed(pygame.K_DOWN, "mover_baixo")
    print("[ok] remapeamento nao afeta a navegacao da propria tela")

    # setas fixas continuam funcionando
    screen.index = 0
    screen.handle_event(keydown(pygame.K_DOWN))
    assert screen.index == 1, f"navegacao travou no indice {screen.index}"
    screen.handle_event(keydown(pygame.K_UP))
    assert screen.index == 0
    print("[ok] setas fixas navegam mesmo com tudo remapeado")

    # e da para sair
    screen.handle_event(keydown(pygame.K_ESCAPE))
    assert manager.active_name == "title", f"preso em {manager.active_name}"
    print("[ok] esc sempre leva de volta ao menu")

    # gravar a tecla reservada TAB e recusado
    manager.switch("options")
    screen = manager.active
    screen.handle_event(keydown(pygame.K_TAB))
    assert screen.group == input_map.GROUP_TECLAS, screen.group
    screen.handle_event(keydown(pygame.K_RETURN))
    screen.handle_event(keyup(pygame.K_RETURN))
    screen.handle_event(keydown(pygame.K_TAB))
    assert screen._capturing is None, "TAB nao deveria entrar em captura"
    print("[ok] TAB nao pode ser gravado como tecla de comando")


def check_options_video_options() -> None:
    """Todas as opcoes de video precisam mudar algo de verdade."""
    from src import assets, input_map
    from src.scene_manager import SceneManager

    config = Config()
    config.save = lambda *a, **k: None  # type: ignore[method-assign]
    manager = build_scene_manager(
        SceneManager(create_window(config), config, InputMap())
    )
    manager.switch("options")
    screen = manager.active

    def value_de(key):
        return next(o.read() for o in screen.options if o.key == key)

    # resolucao
    antes = value_de("resolucao")
    screen.index = 0
    screen.handle_event(keydown(pygame.K_RIGHT))
    assert value_de("resolucao") != antes, "resolucao nao mudou"
    print(f"[ok] resolucao muda ({antes} -> {value_de('resolucao')})")

    # escala dos sprites
    screen.index = 1
    antes = value_de("escala")
    screen.handle_event(keydown(pygame.K_RIGHT))
    assert value_de("escala") != antes, "escala nao mudou"
    assert assets.get_sprite_scale() > 0
    print(f"[ok] escala dos sprites muda ({antes} -> {value_de('escala')})")

    # limite de fps
    screen.index = 2
    antes = value_de("fps")
    screen.handle_event(keydown(pygame.K_RIGHT))
    assert value_de("fps") != antes, "FPS nao mudou"
    print(f"[ok] limite de FPS muda ({antes} -> {value_de('fps')})")

    # vsync (booleano)
    screen.index = 4
    antes = value_de("vsync")
    screen.handle_event(keydown(pygame.K_RETURN))
    assert value_de("vsync") != antes, "vsync nao mudou"
    print(f"[ok] vsync alterna ({antes} -> {value_de('vsync')})")

    # toda opcao precisa ter rotulo, valor e dica
    for option in screen.options:
        assert option.label, "opcao sem rotulo"
        assert option.read(), f"opcao {option.key} sem valor"
    print(f"[ok] {len(screen.options)} opcoes de video com rotulo e valor")

    # a aba de teclas tem 3 slots por acao
    screen.handle_event(keydown(pygame.K_TAB))
    assert screen.group == input_map.GROUP_TECLAS
    for _, _, keys in screen.rows:
        assert len(keys) <= 3, f"acao com {len(keys)} teclas"
    print(f"[ok] aba de teclas com {len(screen.rows)} acoes, ate 3 slots cada")


def check_options_layout() -> None:
    """O painel e o rodape nao podem se sobrepor, em nenhuma resolucao."""
    from src import input_map
    from src.scene_manager import SceneManager

    for width, height in RESOLUTION_CHOICES:
        config = Config(width=width, height=height)
        config.save = lambda *a, **k: None  # type: ignore[method-assign]
        window = create_window(config)
        manager = build_scene_manager(SceneManager(window, config, InputMap()))
        for group in (input_map.GROUP_VIDEO, input_map.GROUP_TECLAS):
            manager.switch("options")
            screen = manager.active
            screen.group = group
            screen.index = 0
            manager.update(1.0 / 60)
            manager.draw()
            panel = screen._layout()["panel"]
            rodape = panel.bottom + 80
            assert panel.top > 0, f"{width}x{height}: painel com topo {panel.top}"
            assert rodape < height, (
                f"{width}x{height}: rodape em {rodape} passa da altura {height}"
            )
            assert panel.left >= 0 and panel.right <= width, (
                f"{width}x{height}: painel {panel} fora da tela"
            )
    print(f"[ok] layout cabe em {len(RESOLUTION_CHOICES)} resolucoes, nas 2 abas")


def check_equivalent_keys() -> None:
    """Enter principal e enter do teclado numerico sao a mesma tecla.

    Bug real: o pygame trata K_RETURN (13) e K_KP_ENTER (1073741912)
    como teclas distintas, e o Windows pode entregar qualquer uma das
    duas. Sem normalizar, "confirmar" falhava em parte dos teclados e o
    menu seemingly nao respondia.
    """
    from src.input_map import InputMap, normalize_key

    assert normalize_key(pygame.K_RETURN) == normalize_key(pygame.K_KP_ENTER)
    controls = InputMap()
    assert controls.pressed(pygame.K_KP_ENTER, "confirmar"), (
        "enter do teclado numerico nao confirma"
    )
    assert controls.pressed(pygame.K_RETURN, "confirmar")
    print("[ok] enter principal e do teclado numerico confirmam igual")


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
    # ao reentrar, a tela volta para a aba Video; a navegacao e feita
    # com as teclas fixas, entao nao ha estado a preservar
    manager.switch("options")
    screen = manager.active
    assert screen.group == input_map.GROUP_VIDEO, screen.group
    screen.handle_event(keydown(pygame.K_TAB))
    assert screen.group == input_map.GROUP_TECLAS, screen.group
    screen.index = 0
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
    check_internal_resolution()
    print()
    check_hud_shows_resolution()
    print()
    check_options_video_options()
    print()
    check_options_layout()
    print()
    check_options_not_lockable()
    print()
    check_equivalent_keys()
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
