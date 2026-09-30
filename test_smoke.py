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
import pathlib
import random
import subprocess
import sys
import tempfile
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
SCENES = ("title", "options", "game", "dungeon")


def _manager():
    """SceneManager pronto para os testes, com a janela ja criada."""
    from src.scene_manager import SceneManager

    pygame.init()
    config = Config()
    window = create_window(config)
    manager = build_scene_manager(SceneManager(window, config))
    manager.ui_state.clear()
    return manager
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


def check_fullscreen_cycle() -> None:
    """Alternar tela cheia e janela nao pode corromper o filtro.

    Este e o bug do "a resolucao buga quando meço tela cheia":

    - a moldura da janela so existe em modo janela. Em tela cheia a
      diferenca entre o retangulo da janela e a superficie de desenho
      e o espaco da ESCALA, nao a borda (num 1280x720 em tela cheia
      num desktop de 1536x960 dava 256x240).
    - esse numero falso era guardado no cache e usado pelo filtro de
      resolucao como se fosse borda. O limite caia para 1280x720, as
      resolucoes maiores sumiam do menu, e ao voltar para janela o
      cache continuava corrompido e rebaixava a resolucao escolhida.
    """
    import pygame

    from src.config import usable_window_size
    from src.main import measure_window_frame, set_window_frame

    config = Config()
    antes = config.available_resolutions()

    # em tela cheia a moldura medida e (0,0): nada de borda
    assert measure_window_frame(fullscreen=True) == (0, 0), "moldura em tela cheia"

    # um numero absurdo de moldura (o espaco da escala) e descartado,
    # para nao entrar no filtro como se fosse borda
    set_window_frame((256, 240))
    limite = usable_window_size()
    config = Config()
    maior = max(config.available_resolutions())
    assert maior[0] <= limite[0] and maior[1] <= limite[1], (
        f"moldura absurda entrou no filtro: maior {maior}, limite {limite}"
    )
    print("[ok] moldura absurda e descartada")

    # e o ciclo completo nao pode mudar a lista de resolucoes
    set_window_frame((16, 39))
    config = Config()
    janela = config.available_resolutions()

    config.fullscreen = True
    cheia = config.available_resolutions()

    config.fullscreen = False
    volta = config.available_resolutions()

    assert janela == volta, (
        f"voltar de tela cheia mudou a lista: {janela} -> {volta}"
    )
    assert len(cheia) >= len(janela), (
        f"tela cheia oferece menos que janela: {cheia} vs {janela}"
    )
    print(
        f"[ok] ciclo tela cheia mantem resolucoes "
        f"(janela={len(janela)} tela_cheia={len(cheia)})"
    )


def check_dynamic_resolution_persists() -> None:
    """A maior resolucao que cabe precisa sobreviver ao config.

    Ela nunca esta em RESOLUTION_CHOICES: entra em tempo de execucao,
    conforme a tela da maquina. Se o clamp exigir pertencer a lista
    estatica, o config salvo com ela volta a 1280x720 na abertura, e o
    jogador nunca ve a escolha pegar. Era esse o bug de persistencia.
    """
    path = ROOT / "_test_config_res.json"
    limit = usable_window_size_for_test()
    if not limit:
        print("[aviso] tela desconhecida; pulando persistencia de resolucao")
        return

    config = Config(width=limit[0], height=limit[1])
    assert config.size in config.available_resolutions(), (
        f"a maior que cabe {limit} nao esta disponivel"
    )
    config.save(path)
    loaded = Config.load(path)
    assert loaded.size == limit, (
        f"a resolucao maxima nao sobreviveu ao config: "
        f"salvo {limit}, voltou {loaded.size}"
    )
    print(f"[ok] resolucao maxima {limit[0]}x{limit[1]} sobrevive ao config")
    path.unlink()


def usable_window_size_for_test() -> tuple[int, int] | None:
    from src.config import usable_window_size

    return usable_window_size()


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
    heroi estourando o cartao em 3x e 4x. A checagem e na cena de
    jogo, que e onde o heroi e desenhado.
    """
    from src.scene_manager import SceneManager

    for scale in SCALE_CHOICES:
        config = Config(sprite_scale=scale)
        assets.set_sprite_scale(scale)
        window = create_window(config)
        manager = build_scene_manager(SceneManager(window, config, InputMap()))
        manager.switch("game")
        manager.update(1.0 / 60)
        manager.draw()
        scene = manager.active

        if scene.frames:
            got = scene.frames[0].get_size()
            # a escala e sempre multiplo inteiro do quadro original.
            # O tamanho base vem de assets.HERO_BASE, e nao escrito
            # aqui: com o valor duplicado, trocar o sprite do heroi
            # quebrou este teste em vez de so trocar o sprite.
            base_w, base_h = assets.HERO_BASE
            assert got[0] == base_w * scale, f"escala {scale}x: {got} esperado {base_w * scale}"
            assert got[1] == base_h * scale, f"escala {scale}x: {got} esperado {base_h * scale}"
            print(f"[ok] escala {scale}x: heroi {got[0]}x{got[1]}")
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


def check_dungeon_map() -> None:
    """O mapa gerado tem de ser jogavel: o caixao alcanca a saida."""
    from src.dungeon_map import (
        CHAO,
        PAREDE,
        alcancavel,
        gerar_mapa,
        validar,
    )

    mapa = gerar_mapa()
    problemas = validar(mapa)
    assert not problemas, f"mapa com problemas: {problemas}"

    alc = alcancavel(mapa, mapa.caixao)
    assert mapa.saida in alc, "a saida nao e alcancavel a partir do caixao"
    assert len(alc) > (mapa.largura * mapa.altura) // 10, (
        f"so {len(alc)} celulas alcancaveis de {mapa.largura * mapa.altura}"
    )
    # as bordas do mapa sao parede, senao o jogador ve o vazio
    for x in range(mapa.largura):
        assert mapa.em(x, 0) == PAREDE, "borda de cima furada"
        assert mapa.em(x, mapa.altura - 1) == PAREDE, "borda de baixo furada"
    for y in range(mapa.altura):
        assert mapa.em(0, y) == PAREDE, "borda da esquerda furada"
        assert mapa.em(mapa.largura - 1, y) == PAREDE, "borda da direita furada"
    print(
        f"[ok] mapa jogavel: {len(alc)} celulas, saida em {mapa.saida}"
    )


def check_dungeon_intro() -> None:
    """A abertura roda: acorda, abre a tampa e solta o jogador."""
    manager = _manager()
    manager.switch("dungeon")
    cena = manager.active
    assert cena.fase == "acordando", cena.fase

    # A tampa tem de chegar a 1 e a fase a "livre"
    dt = 1 / 30
    for _ in range(int(7.0 / dt)):
        manager.update(dt)

    assert cena.tampa >= 0.99, f"tampa parou em {cena.tampa}"
    assert cena.fase == "livre", f"parou na fase {cena.fase}"

    # o titulo da area foi mostrado e ja terminou
    assert cena._titulo_mostrado, "o titulo da area nunca apareceu"
    assert not cena.titulo.active, "o titulo deveria ter sumido"

    # o jogador saiu do caixao: abaixo do centro dele
    assert cena.posicao.y > cena._centro_caixao()[1], "o heroi nao saiu"
    print(
        f"[ok] abertura das catacumbas: acordou, abriu e saiu "
        f"(fase={cena.fase}, tempo={cena.tempo_jogado:.1f}s)"
    )


def check_dungeon_collision() -> None:
    """A parede segura o jogador, e ele nao atravessa em diagonal."""
    manager = _manager()
    manager.switch("dungeon")
    cena = manager.active
    dt = 1 / 60

    # a abertura tem de acabar antes: durante ela o heroi e movido por
    # script para o sul, e medir a colisao ali testaria a outra coisa
    for _ in range(int(7.0 / dt)):
        manager.update(dt)
    assert cena.fase == "livre", cena.fase

    # anda para cima por muito tempo: tem de parar na parede de cima
    for _ in range(400):
        cena.direction = "norte"
        cena.moving = True
        manager.update(dt)
    assert cena.mapa.em(*cena._celula()) != "#", "dentro da parede"
    y_topo = cena.posicao.y
    # mais um pouco nao pode atravessar
    for _ in range(200):
        manager.update(dt)
    assert cena.posicao.y >= y_topo - 1.0, (
        f"atravessou a parede: {y_topo} -> {cena.posicao.y}"
    )
    print(f"[ok] colisao segura na parede (y={cena.posicao.y:.0f})")

    # e o jogador consegue andar de volta: sem isso, preso na parede,
    # o jogo vira um beco sem saida
    for _ in range(200):
        cena.direction = "sul"
        manager.update(dt)
    assert cena.posicao.y > y_topo + 10, "nao saiu andando para o sul"
    print(f"[ok] anda de volta (y={cena.posicao.y:.0f})")


def check_save_roundtrip() -> None:
    """Grava e le um save em arquivo, sem depender de servidor."""
    import tempfile

    from src import saves

    with tempfile.TemporaryDirectory() as pasta:
        caminho = pathlib.Path(pasta) / "save1.json"
        store = saves.ArquivoSaveStore(caminho)

        assert not store.existe(), "save novo nao deveria existir"
        assert store.carregar() is None, "carregar vazio devolve None"

        original = saves.Save(
            area="catacumbas", x=123.5, y=456.25, direcao="leste",
            tempo_jogado=3725.0,
        )
        assert store.salvar(original), "falhou ao salvar"
        assert store.existe(), "save nao apareceu no disco"

        lido = store.carregar()
        assert lido is not None, "save sumiu"
        assert lido.area == "catacumbas", lido.area
        assert abs(lido.x - 123.5) < 0.01, lido.x
        assert abs(lido.y - 456.25) < 0.01, lido.y
        assert lido.direcao == "leste", lido.direcao
        assert abs(lido.tempo_jogado - 3725.0) < 0.01, lido.tempo_jogado
        print("[ok] save em arquivo grava e le de volta")

        # um arquivo nao tem que derrubar o jogo: precisa ser ignorado
        caminho.write_text("{ isso nao e json", encoding="utf-8")
        assert store.carregar() is None, "json quebrado deveria dar None"
        caminho.write_text('{"x": "lado", "area": null}', encoding="utf-8")
        tolerante = store.carregar()
        assert tolerante is not None, "campo invalido nao deveria sumir"
        assert tolerante.x == 0.0, tolerante.x
        assert tolerante.area == "catacumbas", tolerante.area
        print("[ok] save corrompido nao derruba o jogo")

        assert store.apagar(), "falhou ao apagar"
        assert not store.existe(), "save nao sumiu do disco"
        print("[ok] save apagado")


def check_store_fallback() -> None:
    """Servidor fora do ar precisa cair no arquivo, nao travar."""
    from src import saves

    # URL que nao responde, com timeout curtissimo
    remoto = saves.DjangoSaveStore("http://127.0.0.1:9/api/saves", timeout=0.2)
    assert not remoto.existe(), "servidor inexistente respondeu"
    assert remoto.salvar(saves.Save(x=1.0)) is False, "salvar remoto nao devia"
    assert remoto.carregar() is None, "carregar remoto nao devia devolver"
    assert remoto.apagar() is False, "apagar remoto nao devia"
    print("[ok] servidor fora do ar falha sem derrubar o jogo")

    store = saves.escolher_store(procurar_servidor=False)
    assert isinstance(store, saves.ArquivoSaveStore), type(store)
    assert "save1.json" in store.descricao, store.descricao
    print(f"[ok] sem servidor, o save vai para {store.descricao}")


def check_menu_items() -> None:
    """O menu esconde 'Continuar' quando nao ha save."""
    manager = _manager()
    manager.switch("title")
    titulo = manager.active

    from src.title_screen import ITEM_CONTINUAR, ITEM_NOVO

    assert ITEM_NOVO in titulo._visiveis, "Novo jogo sempre visivel"
    if titulo.tem_save:
        assert ITEM_CONTINUAR in titulo._visiveis, (
            "tem save mas Continuar sumiu"
        )
    else:
        assert ITEM_CONTINUAR not in titulo._visiveis, (
            "sem save, Continuar nao devia aparecer"
        )
    assert len(titulo._visiveis) >= 3, titulo._visiveis
    print(f"[ok] menu: {titulo._visiveis}")


def check_dungeon_save_cycle() -> None:
    """Continuar devolve o jogador para onde ele parou."""
    from src import saves

    manager = _manager()
    manager.switch("dungeon")
    cena = manager.active
    for _ in range(int(7.0 * 30)):
        manager.update(1 / 30)

    # anda um pouco e grava
    cena.direction = "leste"
    cena.moving = True
    for _ in range(40):
        manager.update(1 / 60)
    cena.moving = False
    onde = cena.posicao.copy()
    tempo = cena.tempo_jogado

    with tempfile.TemporaryDirectory() as pasta:
        manager.ui_state["store"] = saves.ArquivoSaveStore(
            pathlib.Path(pasta) / "save1.json"
        )
        assert manager.salvar_progresso(), "nao salvou"

        # um jogo novo, com o save carregado
        manager2 = _manager()
        manager2.iniciar_novo_jogo(saves.Save(
            x=onde.x, y=onde.y, direcao="leste", tempo_jogado=tempo
        ))
        cena2 = manager2.active
        assert cena2.fase == "livre", "continuar nao pode repetir a abertura"
        assert abs(cena2.posicao.x - onde.x) < 2.0, (
            f"x nao voltou: {cena2.posicao.x} != {onde.x}"
        )
        assert abs(cena2.posicao.y - onde.y) < 2.0, (
            f"y nao voltou: {cena2.posicao.y} != {onde.y}"
        )
        assert cena2.direction == "leste", cena2.direction
        print(f"[ok] continuar devolve a posicao ({onde.x:.0f}, {onde.y:.0f})")




def check_combat_bases() -> None:
    """As regras do medidor de tempo, sem pygame."""
    from src import combat

    # a barra enche e transborda: quem encheu age e volta ao zero
    barra = combat.Barra(velocidade=10.0, limite=100.0)
    for _ in range(100):
        barra.avancar(0.1)  # 10s * 10/s = 100 -> transborda
    assert barra.valor < 1.0, f"a barra deveria ter virado, esta em {barra.valor}"
    print("[ok] a barra enche, transborda e volta ao zero")

    # gastar nunca deixa a barra negativa
    barra.gastar(500.0)
    assert barra.valor == 0.0, barra.valor
    print("[ok] o custo da acao nunca deixa a barra negativa")

    # o heroi e mais rapido que o esqueleto: e o que faz a batalha
    # avancar em direcao a ele em vez de virar uma fila
    heroi = combat.novo_heroi()
    esq = combat.novo_esqueleto(0)
    assert heroi.velocidade_barra > esq.velocidade_barra, "heroi devia ser mais rapido"
    print(
        f"[ok] o heroi e mais rapido que o esqueleto "
        f"({heroi.velocidade_barra:.0f} contra {esq.velocidade_barra:.0f})"
    )



def check_combat_batalha() -> None:
    """Uma batalha inteira: ataque, defender, vitoria e derrota."""
    from src import combat

    # --- o heroi age primeiro, porque e o mais rapido ---
    b = combat.Batalha(
        heroi=combat.novo_heroi(), inimigos=[combat.novo_esqueleto(0)],
        sorteio=random.Random(1),
    )
    dt = 1 / 60
    while not b.turno_heroi and not b.concluida:
        b.avancar(dt)
    assert b.turno_heroi, "a vez do heroi nunca chegou"
    assert b.heroi.barra.valor < b.heroi.barra.limite, "a barra deveria ter virado"
    print("[ok] a vez do heroi chega e a barra para, esperando a escolha")

    # --- atacar causa dano e consome barra ---
    esq = b.inimigos[0]
    vida_antes = esq.vida
    b.acao_do_heroi(combat.Acao.ATACAR)
    assert esq.vida < vida_antes, f"atacar nao tirou vida: {vida_antes} -> {esq.vida}"
    assert not b.turno_heroi, "a vez do jogador deveria ter acabado"
    print(f"[ok] atacar tira vida ({vida_antes} -> {esq.vida}) e devolve a vez")

    # --- defender reduz o dano pela metade ---
    heroi = combat.novo_heroi()
    alvo = combat.novo_esqueleto(0)
    sem_defesa = heroi.receber(10)
    heroi.vida = heroi.vida_max
    heroi.defendendo = True
    com_defesa = heroi.receber(10)
    assert com_defesa < sem_defesa, f"defender nao ajudou: {sem_defesa} vs {com_defesa}"
    assert alvo.vida == alvo.vida_max, "o alvo nao devia mudar"
    print(f"[ok] defender reduz o dano ({sem_defesa} -> {com_defesa})")

    # --- vitoria ---
    invencivel = combat.novo_heroi(10 ** 6, forca=999)
    b2 = combat.Batalha(
        heroi=invencivel,
        inimigos=[combat.novo_esqueleto(0)],
        sorteio=random.Random(2),
    )
    for _ in range(6000):
        b2.avancar(dt)
        if b2.turno_heroi:
            b2.acao_do_heroi(combat.Acao.ATACAR)
        if b2.concluida:
            break
    assert b2.concluida, "a batalha nao terminou"
    assert b2.vencida, f"o heroi de vida {b2.heroi.vida} perdeu para {esq.nome}"
    assert not b2.inimigos_vivos(), "sobrou inimigo vivo"
    print("[ok] a batalha termina em vitoria quando o ultimo cai")

    # --- derrota ---
    b3 = combat.Batalha(
        heroi=combat.novo_heroi(vida=5, forca=0),
        inimigos=[combat.novo_esqueleto(2)],
        sorteio=random.Random(3),
    )
    for _ in range(6000):
        b3.avancar(dt)
        if b3.turno_heroi:
            b3.acao_do_heroi(combat.Acao.DEFENDER)
        if b3.concluida:
            break
    assert b3.concluida, "a batalha nao terminou"
    assert not b3.vencida, "o heroi fraco deveria ter perdido"
    print("[ok] a batalha termina em derrota quando o heroi cai")



def check_combat_cena() -> None:
    """A cena de combate desenha e responde as teclas."""
    from src import combat

    manager = _manager()
    manager.switch("combat")
    cena = manager.active

    assert cena.batalha.heroi.vivo, "o heroi comeca vivo"
    assert cena.batalha.inimigos, "a luta precisa de inimigo"

    # desenha alguns quadros
    for _ in range(30):
        manager.update(1 / 60)
        manager.draw()

    # espera a vez do heroi e escolhe atacar
    for _ in range(600):
        manager.update(1 / 60)
        if cena.batalha.turno_heroi:
            break
    assert cena.batalha.turno_heroi, "a cena nunca abriu o menu do heroi"
    assert cena.menu_aberto, "o menu nao abriu na vez do heroi"
    manager.draw()

    vida = cena.batalha.inimigos[0].vida
    cena._escolher(combat.Acao.ATACAR)
    assert cena.batalha.inimigos[0].vida < vida, "atacar pela cena nao tirou vida"
    print("[ok] a cena de combate abre o menu, ataca e desenha")


def main() -> int:
    # gerado por tools/fix_test_main.py: a lista abaixo e a unica
    # fonte de verdade da ordem dos testes
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
    check_fullscreen_cycle()
    print()
    check_dungeon_map()
    print()
    check_dungeon_intro()
    print()
    check_dungeon_collision()
    print()
    check_dungeon_save_cycle()
    print()
    check_save_roundtrip()
    print()
    check_store_fallback()
    print()
    check_menu_items()
    print()
    check_combat_bases()
    print()
    check_combat_batalha()
    print()
    check_combat_cena()
    print()
    check_dynamic_resolution_persists()
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
