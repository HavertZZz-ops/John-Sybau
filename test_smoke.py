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
from src.estado import Estado  # noqa: E402
from src.progresso import Progresso  # noqa: E402

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


def check_heroi_tela() -> None:
    """O heroi na tela tem de ser o do conjunto, do tamanho certo."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_heroi_tela.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] heroi na tela:")
        print(result.stdout[-2500:])
        print(result.stderr[-1500:])
        raise SystemExit(result.returncode)
    print("[ok] heroi na tela")


def check_equipamento() -> None:
    """As armas, os cinco conjuntos e a troca de equipamento."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_equipamento.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] equipamento:")
        print(result.stdout[-2500:])
        print(result.stderr[-1500:])
        raise SystemExit(result.returncode)
    print("[ok] equipamento")


def check_refugio() -> None:
    """Fogueira, taverna e mercador: tem de funcionar junto."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_refugio.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] fogueira, taverna e mercador:")
        print(result.stdout[-2500:])
        print(result.stderr[-1500:])
        raise SystemExit(result.returncode)
    print("[ok] fogueira, taverna e mercador")


def check_cidade() -> None:
    """A fuga da masmorra tem que levar a algum lugar, e esse lugar tem gente."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_cidade.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] moradores:")
        print(result.stdout[-2500:])
        print(result.stderr[-1500:])
        raise SystemExit(result.returncode)
    print("[ok] moradores da aldeia")


def check_persistencia() -> None:
    """A campanha tem de sobreviver ao save e ao arquivo em disco."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_persistencia.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] persistencia:")
        print(result.stdout[-2500:])
        print(result.stderr[-1500:])
        raise SystemExit(result.returncode)
    print("[ok] persistencia da campanha")


def check_itens() -> None:
    """Roda a suite do item na luta e das aulas por sala."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_itens.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] itens e aulas:")
        print(result.stdout[-2500:])
        print(result.stderr[-1500:])
        raise SystemExit(result.returncode)
    print("[ok] itens e aulas por sala")


def check_fuga() -> None:
    """Roda a suite da fuga do chefe: opcao, custo zero e recambio."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_fuga.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] fuga do chefe:")
        print(result.stdout[-2500:])
        print(result.stderr[-1500:])
        raise SystemExit(result.returncode)
    print("[ok] fuga do chefe")


def check_wang() -> None:
    """Roda a suite da autotilagem de Wang e do registro de cenarios.

    Fica em arquivo separado porque testa arte em disco (os tilesets do
    PixelLab tem de estar la) e nao so logica. `GradeWang` escolhe o
    tile pelos quatro vertices, e um canto trocado de lugar nao quebra
    nada: a borda simplesmente fecha do lado errado.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_wang.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        print("[FALHA] autotilagem de Wang:")
        print(result.stdout[-3000:])
        print(result.stderr[-2000:])
        raise SystemExit(result.returncode)
    print("[ok] autotilagem de Wang e cenarios")


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

    # Este teste e de COLISAO. Com o esqueleto nascendo por sala, andar
    # pelo mapa chega perto de um e troca a cena ativa por combate: a
    # cena de colisao deixa de ser a cena do gerenciador e o teste
    # passa a medir outra coisa. A armação do inimigo e desligada
    # aqui de proposito.
    cena._atualizar_esqueleto = lambda dt: None

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
        cena.moving = True
        manager.update(dt)
    assert manager.active is cena, "a cena mudou de lugar durante o teste"
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




def check_orcamento_da_luta() -> None:
    """A luta cabe no quadro de 60 FPS.

    O jogador viu a cena de combate a 9 FPS. A causa era o halo da
    tocha: um laco de pixel em Python, com um `set_at` por pixel, que
    custava 50ms POR TOCHA — sessenta vezes por segundo, com duas
    tochas. O quadro inteiro da cena levava 104ms.

    O halo agora e um disco de circulos concentricos, desenhados em C
    pelo pygame, e esta em cache por tamanho de raio. O quadro caiu
    para menos de 4ms.

    Este teste segura o numero, e nao a sensacao de "esta rapido": um
    quadro de 30ms ainda parece bem numa foto, e a tela fica a 30 FPS
    mesmo assim. E medido no pior caso — tres inimigos e o menu aberto
    — e na config real do jogador, 1008x720.

    O teste tambem segura que nenhuma parte sozinha domine o quadro: se
    o cenario ou os lutadores crescerem, ha folga antes do jogo engasgar.
    """
    import time as _time
    from src import arena as _arena

    manager = _manager()
    manager.ui_state.clear()
    manager.ui_state["inimigos"] = 3
    manager.ui_state["fracos"] = True
    manager.switch("combat")
    cena = manager.active
    cena.on_enter()
    w, h = cena.size
    tela = pygame.Surface((w, h))

    # aquece: a primeira chamada paga fonte, tileset e a montagem da arena
    cena.update(1 / 60)
    cena.draw(tela)
    for _ in range(20):
        cena.update(1 / 60)
        cena.draw(tela)

    def cronometra(funcao, quadros=90):
        inicio = _time.perf_counter()
        for _ in range(quadros):
            funcao()
        return (_time.perf_counter() - inicio) / quadros * 1000

    orcamento = 1000.0 / 60.0
    t_quadro = cronometra(lambda: (cena.update(1 / 60), cena.draw(tela)))

    assert t_quadro < orcamento, (
        f"o quadro leva {t_quadro:.2f} ms e o orcamento e {orcamento:.2f}: "
        f"a luta roda a {1000.0 / t_quadro:.0f} FPS")
    folga = orcamento - t_quadro
    print(f"[ok] o quadro da luta leva {t_quadro:.2f} ms de {orcamento:.2f} "
          f"(folga de {folga:.2f} ms, {1000.0 / t_quadro:.0f} FPS)")

    t_cenario = cronometra(lambda: cena._desenhar_cenario(tela))
    t_gente = cronometra(lambda: (cena._desenhar_inimigos(tela, w, h),
                                  cena._desenhar_heroi(tela, w, h),
                                  cena._desenhar_vez(tela, w, h)))
    for nome, t in (("o cenario", t_cenario), ("os lutadores", t_gente)):
        assert t < orcamento / 3, (
            f"{nome} sozinho leva {t:.2f} ms, mais de um terco do quadro: "
            f"uma parte crescendo ja engasga o jogo")
    print(f"[ok] nenhuma parte domina: cenario {t_cenario:.2f} ms, "
          f"lutadores {t_gente:.2f} ms")

    # o halo do cache e muito mais barato que o halo montado
    _arena.limpar_cache()
    _arena.arena(w, h, cena.cenario_luta_arena, 0.0)
    raio = int(h * _arena.ALCANCE_TOCHA * 0.92)
    t_montar = cronometra(lambda: _arena._halo_cache.pop(raio, None)
                          and _arena._halo(raio) or _arena._halo(raio), 200)
    t_cache = cronometra(lambda: _arena._halo(raio), 200)
    assert t_cache < t_montar / 5, (
        f"o halo do cache ({t_cache * 1000:.1f}us) nao e mais barato "
        f"que montado ({t_montar * 1000:.1f}us)")
    print(f"[ok] o halo do cache e {t_montar / max(t_cache, 1e-9):.0f}x "
          f"mais barato que montado")

    # e o halo continua sendo uma luz, e nao um disco
    fundo = _arena.arena(w, h, cena.cenario_luta_arena, 0.0)
    tx, ty = _arena._tochas(w, h, int(h * _arena.HORIZONTE))[0]
    perto = fundo.get_at((tx + 30, ty))
    longe = fundo.get_at((w // 2, ty))
    assert perto[0] > longe[0], (
        "o halo nao clareia a parede perto da tocha")
    print(f"[ok] o halo ainda clareia a parede "
          f"({tuple(perto[:3])} perto contra {tuple(longe[:3])} longe)")


def check_menu_do_combate() -> None:
    """O menu de combate tem a arte do pacote e icones legiveis.

    A foto do jogador mostrou o menu como um retangulo alaranjado
    chapado com cinco slots de madeira vazios. Duas causas, e as duas
    precisam de prova:

      - **A fita do header e lisa de nascenca.** A arte do CraftPix
        (`action_header`, 88x17) tem UM so tom opaco e o resto
        transparente: nao ha contorno escuro nela para procurar. Esticada
        para 300px e com um nome no meio, ela le como um botao chapado.
        Nao e arte faltando. A sombra, o contorno e o brilho de cima
        sao da cena, e e isso que da profundidade;
      - **Os icones estavam pequenos demais.** A arte de cada icone e
        de 14x14, a grade de um sprite. Ampliado com folga de 12px num
        slot de 45, dava 24px — um terco do slot — e a espada lia como
        um risco azul. Medido no zoom, ocupava 24px de 45.

    E o que o teste segura: a arte entra na tela com a cor dela, a fita
    ganha contorno e sombra da cena, o nome de cada acao cabe no header
    (a conta antiga estimava por caractere e so acertava com cinco
    letras), e o icone ocupa pelo menos 60% do slot — com a selecao
    maior ainda, porque o olho do jogador esta na briga e nao no menu.
    """
    from src import combat as _combat
    from src import combat_scene as _cs
    from src import ui_arte as _ui

    # o icone de cada acao. Vive aqui e nao no modulo porque o mapa e
    # o mesmo para o teste e para a cena: se um deles mudar sozinho, o
    # teste passa a medir outra coisa.
    ICONES = {
        _combat.Acao.ATACAR: "espada",
        _combat.Acao.DEFENDER: "escudo",
        _combat.Acao.HABILIDADE: "rosto",
        _combat.Acao.ITEM: "pocao_azul",
        _combat.Acao.FUGIR: "olho",
    }

    manager = _manager()
    manager.ui_state.clear()
    manager.ui_state["inimigos"] = 2
    manager.ui_state["fracos"] = True
    manager.switch("combat")
    cena = manager.active
    cena.on_enter()
    w, h = cena.size
    tela = pygame.Surface((w, h))
    for _ in range(20):
        cena.update(1 / 60)
        cena.draw(tela)

    # 1. as duas pecas de arte estao no disco
    header_art = _ui.carregar(_ui.PAINEL_ACAO_HEADER)
    bar_art = _ui.carregar(_ui.PAINEL_ACAO_BAR)
    assert header_art is not None, "a arte do header nao esta no disco"
    assert bar_art is not None, "a arte da barra nao esta no disco"
    print(f"[ok] as pecas do menu estao no disco "
          f"({header_art.get_size()} e {bar_art.get_size()})")

    # 2. a fita e lisa de nascenca: nao ha contorno para procurar
    opacos = {(x, y) for y in range(header_art.get_height())
              for x in range(header_art.get_width())
              if header_art.get_at((x, y))[3] > 200}
    tons = {tuple(header_art.get_at((x, y))[:3]) for x, y in opacos}
    assert len(tons) == 1, (
        f"a arte do header tem {len(tons)} tons: a prova de que ela e "
        f"lisa mudou, e o teste precisa ser revisto")
    print(f"[ok] a fita e lisa de nascenca: {len(tons)} tom, "
          f"{len(opacos)} pixels opacos")

    # 3. a cor da arte aparece na tela
    cor_arte = next(iter(tons))
    header = _ui.desenhar(
        tela, _ui.PAINEL_ACAO_HEADER,
        (w // 2, int(h * 0.88) - int(h * 0.05) - 40), int(w * 0.30))
    assert header is not None
    achada = any(
        tuple(tela.get_at((x, y))[:3]) == cor_arte
        for y in range(header.y, header.bottom)
        for x in range(header.x, header.right))
    assert achada, f"a cor da arte {cor_arte} nao esta na tela"
    print(f"[ok] a arte do header entrou na tela ({cor_arte})")

    # 4. a cena acrescenta o contorno: a fita tem de ter uma borda
    # escura na tela, mesmo sem ter na arte
    tem_borda = False
    for x in range(header.left, header.right, 2):
        for y in (header.top, header.bottom - 1):
            cor = tela.get_at((x, y))[:3]
            if sum(cor) < 90:  # bem escuro
                tem_borda = True
                break
    assert tem_borda, (
        "a fita nao tem contorno escuro na tela: e um retangulo chapado")
    print("[ok] a cena acrescenta contorno escuro na fita")

    # 5. o nome de cada acao cabe no header, medido
    opcoes = list(_combat.Acao)
    for i, acao in enumerate(opcoes):
        cena.index = i
        for _ in range(3):
            cena.update(1 / 60)
            cena.draw(tela)
        larg, _alt = cena._largura_do_nome(acao.value.upper())
        assert larg < header.width, (
            f"o nome {acao.value} tem {larg}px e o header tem "
            f"{header.width}px: transborda")
    print(f"[ok] o nome das {len(opcoes)} acoes cabe no header "
          f"de {header.width}px")

    # 6. os slots cabem na barra, sem se invadirem
    art_geo = pygame.Rect(0, 0, bar_art.get_width() * 3, bar_art.get_height() * 3)
    art_geo.center = (w // 2, int(h * 0.88))
    slots = _ui.slots_da_barra(art_geo, len(opcoes))
    for i in range(len(slots) - 1):
        assert slots[i].right <= slots[i + 1].left, (
            f"os slots {i} e {i + 1} se invadem")
    print(f"[ok] os {len(slots)} slots cabem na barra")

    # 7. o icone ocupa pelo menos 60% do slot, e o selecionado mais
    for i, acao in enumerate(opcoes):
        arte = _ui.icone(ICONES.get(acao, ""))
        if arte is None:
            continue
        lado = max(8, min(slots[i].width, slots[i].height) - 6)
        fracao = lado / min(slots[i].width, slots[i].height)
        assert fracao >= 0.60, (
            f"o icone de {acao.value} ocupa {fracao:.0%} do slot "
            f"({lado}px de {min(slots[i].width, slots[i].height)}px): "
            f"e um risco, nao um icone")
    lado_normal = max(8, min(slots[0].width, slots[0].height) - 6)
    lado_selecionado = min(slots[0].width, slots[0].height) - 4
    assert lado_selecionado > lado_normal, (
        "o icone selecionado nao e maior que os outros")
    print(f"[ok] os icones ocupam {lado_normal}px de "
          f"{min(slots[0].width, slots[0].height)}px, "
          f"e o selecionado {lado_selecionado}px")

    # 8. e a barra com a dica cabe na tela
    assert art_geo.bottom + 20 < h, (
        f"a barra chega em {art_geo.bottom} e a tela em {h}")
    print(f"[ok] a barra e a dica cabem na tela")


def check_enfeites_da_luta() -> None:
    """Os enfeites ficam nos cantos, e nunca em cima de um lutador.

    A foto do jogador mostrou os objetos espalhados: um barril grande
    na altura do quadril do boneco, entalado na perna dele, e outros
    pelos cantos sem relacao com a parede nem uns com os outros.

    A causa era usar a posicao do enfeite NO MAPA. A posicao vem de uma
    sala grande vista de cima, com celulas de 48px, e espalhada na tela
    ela punha um pote no meio do chao e um osso a meia tela. Um canto de
    sala e objeto contra a parede, em grupo, e nao em qualquer lugar.

    Aqui o teste mede:

      - ninguem no meio: o canto e medido contra a faixa dos lutadores;
      - todo enfeite encostado numa parede lateral;
      - nenhum enfeite em cima de outro;
      - nenhum enfeite maior que o menor lutador;
      - cada enfeite com sombra, que e o que gruda o objeto no chao;
      - e, pela posicao FINAL que a cena usou, nenhum enfeite cruzando
        o retangulo de um lutador. Quando o canto esta ocupado, o
        objeto recua para tras do horizonte e encolhe.
    """
    from src import cenario as _cenario_mod
    from src import cenarios as _cenarios
    from src import dungeon_map as _dm

    manager = _manager()
    manager.ui_state.clear()
    mapa = _dm.gerar_mapa(largura=24, altura=16, salas=2, semente=31)
    manager.ui_state["cenario_luta"] = {
        "tileset": "catacumbas_wang",
        "sala": 1,
        "enfeites": _cenario_mod.distribuir(mapa, quantos=12, semente=7),
    }
    manager.ui_state["inimigos"] = 3
    manager.switch("combat")
    cena = manager.active
    cena.on_enter()
    w, h = cena.size
    tela = pygame.Surface((w, h))
    for _ in range(20):
        cena.update(1 / 60)
        cena.draw(tela)

    hz = cena._horizonte()
    posto = list(cena._ultimos_enfeites)
    assert posto, "nenhum enfeite foi posto na tela"
    print(f"[ok] {len(posto)} enfeite(s) posto(s) na arena")

    # 1. nenhum no meio: a faixa onde os lutadores ficam
    primeiro = w * 0.28
    ultimo = w * 0.86
    for caixa, lado in posto:
        centro = caixa.centerx
        assert not (primeiro - 60 <= centro <= ultimo + 60), (
            f"o enfeite em x={centro} esta na faixa dos lutadores "
            f"({primeiro:.0f} a {ultimo:.0f})")
    print(f"[ok] nenhum enfeite na faixa dos lutadores "
          f"({primeiro:.0f} a {ultimo:.0f})")

    # 2. todo enfeite encostado numa parede lateral
    for caixa, lado in posto:
        perto = min(caixa.centerx, w - caixa.centerx)
        assert perto < w * 0.20, (
            f"o enfeite em x={caixa.centerx} esta a {perto}px da parede: "
            f"no meio da sala, nao em um canto")
    print("[ok] todos os enfeites estao encostados numa parede lateral")

    # 3. nenhum se sobrepoe a outro
    for i in range(len(posto)):
        for j in range(i + 1, len(posto)):
            a, b = posto[i][0], posto[j][0]
            assert not a.colliderect(b), (
                f"os enfeites {i} e {j} se cruzam: {tuple(a)} e {tuple(b)}")
    print("[ok] nenhum enfeite se sobrepoe a outro")

    # 4. nenhum enfeite e maior que o menor lutador
    alturas = []
    for i, inimigo in enumerate(cena.batalha.inimigos):
        quadros = cena._quadros_inimigo.get(id(inimigo), {})
        lista = quadros.get("walk") or quadros.get("idle")
        if not lista:
            continue
        _tras, encolhe = combat_scene_INIMIGO_ATRAS(i)
        alturas.append(lista[0].get_height() * encolhe)
    menor_lutador = min(alturas)
    maior_enfeite = max(lado for _c, lado in posto)
    assert maior_enfeite < menor_lutador, (
        f"o enfeite ({maior_enfeite}px) e maior que o menor lutador "
        f"({menor_lutador:.0f}px): ia esconder")
    print(f"[ok] o maior enfeite ({maior_enfeite}px) e menor que o "
          f"menor lutador ({menor_lutador:.0f}px)")

    # 5. cada enfeite tem sombra: sem ela o objeto gruda na parede
    for caixa, lado in posto:
        sob = tela.get_at((caixa.centerx, caixa.bottom - 1))
        longe = tela.get_at((w // 2, caixa.bottom - 1))
        assert sob[0] < longe[0], (
            f"o enfeite em x={caixa.centerx} nao tem sombra: "
            f"{tuple(sob[:3])} contra {tuple(longe[:3])} do lado")
    print("[ok] cada enfeite tem sombra: o objeto esta apoiado no chao")

    # 6. e a posicao FINAL nao cruza nenhum lutador
    magicos = cena._retangulos_dos_lutadores()
    for caixa, lado in posto:
        bate = [i for i, m in enumerate(magicos) if caixa.colliderect(m)]
        assert not bate, (
            f"o enfeite em {tuple(caixa)} cruza o lutador {bate}")
    print(f"[ok] nenhum enfeite cruza nenhum dos {len(magicos)} lutadores")


def combat_scene_INIMIGO_ATRAS(indice: int) -> tuple[float, float]:
    """`(quanto sobe, quanto encolhe)` do inimigo na ordem da tela."""
    from src.combat_scene import INIMIGO_ATRAS
    return INIMIGO_ATRAS[indice % len(INIMIGO_ATRAS)]


def check_turnos_regras() -> None:
    """As regras da luta por turnos: fila, ordem e o jogo parado.

    A luta e por FILA: o mais rapido age primeiro, cada um age uma vez, e
    o jogo PARA enquanto o jogador escolhe. O que este teste segura:

      - nao existe medidor de tempo, nem em `combat` nem no combatente;
      - a fila abre no mais rapido, e o heroi e mais rapido que o
        esqueleto da sala 1;
      - dez segundos parados na vez do jogador nao mudam ninguem;
      - o heroi age uma vez e so: uma segunda acao fora da vez nao
        passa;
      - a ordem se repete a cada volta. Com velocidades iguais, quem
        agiu por ultimo vai depois: senao o mesmo grupo bate sempre
        primeiro e a briga fica com resultado travado;
      - um morto sai da fila e nunca vira alvo.
    """
    from src import combat as _combat

    assert not hasattr(_combat, "Barra"), "combat.Barra voltou"
    lutador = _combat.novo_heroi()
    assert not hasattr(lutador, "barra"), "o combatente tem barra de novo"
    assert not hasattr(lutador, "velocidade_barra"), (
        "a velocidade da barra voltou: a luta voltou a ser por tempo")
    assert hasattr(lutador, "velocidade"), "o combatente precisa de iniciativa"
    print("[ok] nao existe mais medidor de tempo no combate")

    heroi = _combat.novo_heroi()
    esq = _combat.novo_esqueleto(0)
    assert heroi.velocidade > esq.velocidade, "o heroi devia ser mais rapido"
    b = _combat.Batalha(heroi=heroi, inimigos=[esq])
    assert b.fila[0] is heroi, f"a fila nao abre no heroi: {b.fila}"
    assert b.de_quem_e_a_vez is heroi
    print(f"[ok] a fila abre no mais rapido "
          f"({heroi.velocidade:.0f} contra {esq.velocidade:.0f})")

    vida = heroi.vida
    for _ in range(600):
        b.avancar(1 / 60)
    assert heroi.vida == vida, (
        f"o heroi levou dano na propria vez: {vida} -> {heroi.vida}")
    print("[ok] dez segundos parado na vez do jogador, e ninguem age")

    vida_esq = esq.vida
    b.acao_do_heroi(_combat.Acao.ATACAR)
    assert esq.vida < vida_esq, "o golpe nao causou dano"
    depois_do_golpe = esq.vida
    b.acao_do_heroi(_combat.Acao.ATACAR)
    assert esq.vida == depois_do_golpe, "o heroi agiu duas vezes"
    print("[ok] o heroi age uma vez, e a segunda acao nao passa")

    mesmos = [
        _combat.Combatente(nome=f"E{i}", vida=10, vida_max=10,
                           velocidade=10.0, forca=1)
        for i in range(3)
    ]
    b5 = _combat.Batalha(heroi=_combat.novo_heroi(), inimigos=list(mesmos))
    primeira = [c.nome for c in b5.fila]
    for _ in range(4):
        if b5.turno_heroi:
            b5.acao_do_heroi(_combat.Acao.ATACAR)
        b5.avancar(1 / 60)
    segunda = [c.nome for c in b5.fila]
    assert primeira[1:] != segunda[1:], (
        f"a fila nao se repete: {primeira} e {segunda}")
    print(f"[ok] a ordem muda a cada volta ({primeira} -> {segunda})")

    b6 = _combat.Batalha(
        heroi=_combat.novo_heroi(),
        inimigos=[_combat.novo_esqueleto(0), _combat.novo_esqueleto(1)],
    )
    morto = b6.inimigos[0]
    morto.estado = _combat.Estado.MORTO
    b6._montar_fila()
    assert morto not in b6.fila, "o morto continua na fila"
    assert b6.alvo_aleatorio() is not morto, "o morto pode ser alvo"
    print("[ok] o morto sai da fila e nunca vira alvo")


def check_turnos_tela() -> None:
    """A tela diz de quem e a vez, e o ATB saiu de verdade.

    A foto do jogador mostrou o ATB como dois riscos dourados no chao,
    com a etiqueta "TEMPO", sem dizer a que se referiam. Aqui o teste
    mede a tela:

      - a luta comeca na vez do heroi, com o menu aberto;
      - as barras de tempo do ATB nao existem mais, e a indicacao de
        "de quem e a vez" existe;
      - a tela MUDA quando a vez muda, senao o jogador nao tem como
        saber que a vez passou;
      - a pausa entre inimigos segura a fila: um nao age durante a
        pausa do outro, e o menu nao abre antes da hora;
      - uma luta inteira roda, com o turno passando varias vezes.
    """
    from src import combat as _combat
    from src import combat_scene as _cs

    manager = _manager()
    manager.ui_state.clear()
    manager.ui_state["inimigos"] = 3
    manager.ui_state["fracos"] = True
    manager.switch("combat")
    cena = manager.active
    cena.on_enter()
    w, h = cena.size
    tela = pygame.Surface((w, h))

    for _ in range(30):
        cena.update(1 / 60)
        cena.draw(tela)

    assert cena.batalha.turno_heroi, "a luta nao comecou na vez do heroi"
    assert cena.menu_aberto, "o menu nao abriu na vez do heroi"
    print("[ok] a luta comeca na vez do heroi, com o menu aberto")

    assert not hasattr(cena, "_barra_de_tempo"), (
        "o medidor de tempo do ATB ainda existe")
    assert not hasattr(cena, "_desenhar_barras"), (
        "as barras de tempo ainda sao desenhadas")
    assert hasattr(cena, "_desenhar_vez"), "a tela nao diz de quem e a vez"
    print("[ok] as barras de tempo do ATB sairam, a vez entrou")

    antes = pygame.image.tostring(tela, "RGB")
    cena._escolher(_combat.Acao.ATACAR)
    cena.update(1 / 60)
    cena.draw(tela)
    depois = pygame.image.tostring(tela, "RGB")
    assert cena.batalha.de_quem_e_a_vez is not cena.batalha.heroi, (
        "a vez nao passou para o inimigo depois do golpe")
    assert antes != depois, "a tela ficou igual quando a vez mudou"
    print("[ok] a tela muda quando a vez muda")

    assert _cs.PAUSA_ENTRE_INIMIGOS > 0.2, (
        f"a pausa de {_cs.PAUSA_ENTRE_INIMIGOS}s e curta demais para ver")
    assert cena._espera_turno > 0, "a pausa nao foi armada depois do golpe"
    vida = cena.batalha.heroi.vida
    cena._espera_turno = _cs.PAUSA_ENTRE_INIMIGOS
    cena.update(1 / 60)
    cena.draw(tela)
    assert cena.batalha.heroi.vida == vida, "um inimigo agiu durante a pausa"
    cena.menu_aberto = False
    cena._espera_turno = 5.0
    cena.update(1 / 60)
    assert not cena.menu_aberto, "o menu abriu durante a espera"
    print(f"[ok] a pausa de {_cs.PAUSA_ENTRE_INIMIGOS}s segura a fila e o menu")

    for passo in range(1200):
        cena.update(1 / 60)
        cena.draw(tela)
        if cena.batalha.concluida:
            break
        if cena.batalha.turno_heroi and cena.menu_aberto:
            if cena.batalha.heroi.fracao_vida < 0.3:
                cena._escolher(_combat.Acao.DEFENDER)
            else:
                cena._escolher(_combat.Acao.ATACAR)
    assert cena.batalha.volta >= 1, "a luta terminou em menos de uma volta"
    print(f"[ok] {passo + 1} quadros de luta, {cena.batalha.volta} voltas, "
          f"concluida: {cena.batalha.concluida}")


def check_combat_bases() -> None:
    """As regras da luta por turnos, sem pygame.

    A luta e por FILA: o mais rapido age primeiro, cada um age uma vez, e
    o jogo para enquanto o jogador escolhe. Nao ha medidor de tempo, e o
    teste tambem nao: `Barra` foi removida de `combat`, entao qualquer
    codigo que ainda procure por ela esta usando a regra antiga.
    """
    from src import combat

    # nao existe mais medidor de tempo
    assert not hasattr(combat, "Barra"), (
        "combat.Barra voltou: a luta voltou a ser por tempo")
    lutador = combat.novo_heroi()
    assert not hasattr(lutador, "barra"), (
        "o combatente tem barra de novo: a luta voltou a ser por tempo")
    assert hasattr(lutador, "velocidade"), "o combatente precisa de iniciativa"
    print("[ok] nao ha mais barra de tempo: a luta e por turnos")

    # a ordem e por iniciativa: o heroi abre a fila
    heroi = combat.novo_heroi()
    esq = combat.novo_esqueleto(0)
    assert heroi.velocidade > esq.velocidade, "heroi devia ser mais rapido"
    b = combat.Batalha(heroi=heroi, inimigos=[esq])
    assert b.fila[0] is heroi, f"a fila nao comeca no heroi: {b.fila}"
    assert b.de_quem_e_a_vez is heroi
    print(
        f"[ok] a fila comeca no mais rapido "
        f"({heroi.velocidade:.0f} contra {esq.velocidade:.0f})"
    )

    # o jogo para enquanto o jogador escolhe
    vida = heroi.vida
    for _ in range(600):  # dez segundos de tempo, sem agirem ninguem
        b.avancar(1 / 60)
    assert heroi.vida == vida, (
        f"o heroi levou dano durante a propria vez: {vida} -> {heroi.vida}")
    print("[ok] ninguem age enquanto o jogador nao escolhe")



def check_combat_batalha() -> None:
    """Uma batalha inteira: ataque, defender, vitoria e derrota."""
    from src import combat

    # --- o heroi age primeiro, porque e o mais rapido ---
    b = combat.Batalha(
        heroi=combat.novo_heroi(), inimigos=[combat.novo_esqueleto(0)],
        sorteio=random.Random(1),
    )
    dt = 1 / 60
    assert b.turno_heroi, "a vez do heroi nunca chegou"
    assert b.de_quem_e_a_vez is b.heroi
    print("[ok] a luta comeca na vez do heroi, esperando a escolha")

    # --- atacar causa dano e devolve a vez ---
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


def check_tutorial() -> None:
    """As aulas avancam, e so fecham no gatilho certo."""
    from src.tutorial import TUTORIAL_CATACUMBAS

    t = TUTORIAL_CATACUMBAS
    t.resetar()
    t.comecar()

    assert t.ativo, "o tutorial nao comecou"
    primeira = t.atual.texto
    print(f"[ok] primeira aula: {primeira!r}")

    # uma aula so informativa expira sozinha
    for _ in range(int(6.0 * 60)):
        t.update(1 / 60)
    assert t.atual is not None and t.atual.texto != primeira, (
        "a aula informativa nao expirou"
    )
    print(f"[ok] a aula informativa expirou: {t.atual.texto!r}")

    # a aula de andar NAO fecha so com o tempo: espera o comando
    aula = t.atual
    assert aula.gatilho == "mover_direita", aula.gatilho
    for _ in range(int(20.0 * 60)):
        t.update(1 / 60)
    assert t.atual.texto == aula.texto, (
        "a aula fechou sozinha, sem o jogador andar"
    )
    print("[ok] a aula nao fecha so com o tempo")

    # agora com a tecla certa
    for _ in range(60):
        t.update(1 / 60, acao_cumprida="mover_direita")
    assert t.atual.texto != aula.texto, "a aula nao fechou com o comando"
    print(f"[ok] fechou com o comando: {t.atual.texto!r}")

    # a acao errada nao fecha
    antes = t.atual.texto
    for _ in range(60):
        t.update(1 / 60, acao_cumprida="confirmar")
    assert t.atual.texto == antes, "a aula fechou com a tecla errada"
    print("[ok] a tecla errada nao fecha a aula")

    # o roteiro tem todas as etapas que o comeco precisa ensinar
    textos = [a.texto for a in TUTORIAL_CATACUMBAS.aulas]
    for esperado in (
        "Voce acordou dentro de um caixao",
        "Use as setas para andar",
        "F5 salva o jogo",
        "Esc volta para o menu",
        "O esqueleto acordou",
        "O medidor enche com o tempo",
        "Escolha Atacar quando a sua vez chegar",
    ):
        assert esperado in textos, f"falta a aula: {esperado!r}"
    print(f"[ok] o roteiro tem as {len(textos)} aulas do comeco")
    t.resetar()


def check_tutorial_na_masmorra() -> None:
    """A masmorra mostra a aula e acorda o esqueleto ao sair do caixao."""
    manager = _manager()
    manager.switch("dungeon")
    cena = manager.active

    # a abertura roda inteira
    dt = 1 / 60
    for _ in range(int(7.0 / dt)):
        manager.update(dt)
    assert cena.fase == "livre", cena.fase
    manager.draw()

    # O esqueleto emerge ASSIM QUE o jogador sai do caixao. Antes
    # ele ficava guardado esperando o jogador andar 14 passos, e a
    # fase "saindo" levava o heroi onze tiles para o sul, para um
    # corredor onde nao nasce esqueleto: o primeiro encontro so
    # acontecia depois de o jogador andar de volta.
    caixao = cena._centro_caixao()
    tiles = abs(cena.posicao.y - caixao[1]) / cena.tile
    assert tiles < 4.0, f"o jogador saiu {tiles:.1f} tiles do caixao"
    sala_caiso = cena.mapa.sala_de(*cena._celula())
    assert sala_caiso == 1, (
        f"o jogador acordou na sala {sala_caiso}, e nao na sala do "
        f"caixao"
    )
    assert cena.esqueleto is not None, "o esqueleto nao emergiu do chao"
    print(f"[ok] o esqueleto emerge a {tiles:.1f} tiles do caixao")

    # o chefe nasce na sala que o progresso aponta, que com a campanha
    # e a ULTIMA e nao a primeira. Andar para o leste dentro da sala do
    # caixao nao chega nele.
    sala_chefe = cena.progresso.onde_esta_o_chefe()
    assert sala_chefe == len(cena.mapa.salas), (
        f"o chefe deveria estar na ultima sala, esta na {sala_chefe} "
        f"de {len(cena.mapa.salas)}"
    )
    centro = cena.mapa.centro_da_sala(sala_chefe)
    casa = cena._casa_do_chefe()
    assert casa is not None, "a casa do chefe nao foi encontrada"
    assert cena.mapa.sala_de(*casa) == sala_chefe, (
        f"o chefe nasceu na sala {cena.mapa.sala_de(*casa)}, "
        f"esperado {sala_chefe}"
    )
    assert casa != tuple(cena.mapa.caixao), "o chefe nasceu em cima do caixao"
    print(f"[ok] o chefe nasce na sala {sala_chefe}, longe do caixao")

    # o esqueleto nasce na sala em que o jogador esta, e o jogador
    # precisa andar antes. Com o modelo por sala, a prova de que ele
    # ESPERA e o corredor: em corredor nao nasce ninguem.
    #
    # Antes, este bloco teleportava o jogador para a sala 1 e esperava
    # a luta nao comecar. Com o modelo novo isso nao prova nada: o
    # esqueleto nasce na sala em que o jogador esta, e a sala 1 era
    # justamente onde o jogador estava.
    em_corredor = None
    for x in range(cena.mapa.largura):
        for y in range(cena.mapa.altura):
            if cena.mapa.sala_de(x, y) == 0 and cena.mapa.andavel(x, y):
                em_corredor = (x, y)
                break
        if em_corredor:
            break
    if em_corredor is not None:
        px, py = cena.mapa.para_pixels(*em_corredor, cena.tile)
        cena.posicao = pygame.Vector2(px, py)
        cena.esqueleto = None
        cena.esqueleto_vivo = False
        cena.passos = 999
        manager.update(dt)
        manager.update(dt)
        assert cena.sala_atual == 0, (
            f"o jogador deveria estar em corredor, sala_atual={cena.sala_atual}"
        )
        assert cena.esqueleto is None, (
            "nasceu esqueleto no corredor: o jogador nao entrou em sala nenhuma"
        )
        print("[ok] em corredor nao nasce esqueleto: ele espera o jogador entrar")

    # na sala do chefe: nasce la, e a luta comeca quando chega perto
    px, py = cena.mapa.para_pixels(*casa, cena.tile)
    cena.posicao = pygame.Vector2(px, py)
    for _ in range(400):
        cena.direction = "leste"
        cena.moving = True
        manager.update(dt)
    assert cena.esqueleto is not None, (
        f"o esqueleto nao acordou depois de {cena.passos} passos"
    )
    # o esqueleto tem de CONTINUAR ali. Ele ja nasceu e sumia no quadro
    # seguinte, e o teste antigo nao pegou porque conferia no mesmo
    # quadro do nascimento
    for _ in range(120):
        manager.update(dt)
    assert cena.esqueleto is not None, "o esqueleto sumiu depois de nascer"
    # Com a campanha o jogador foi posto NA SALA DO CHEFE, entao a luta
    # comecar aqui e o comportamento certo: a prova de que a luta nao
    # dispara sozinha passou a ser o quadro logo depois de teleportar,
    # com o jogador ainda longe o bastante.
    assert manager.active_name == "combat", (
        f"perto do chefe a luta deveria ter comecado, mas a cena e "
        f"{manager.active_name}"
    )
    manager.draw()
    print(f"[ok] o chefe acordou e a luta comecou na sala dele")

    # chega perto: a luta tem de comecar
    cx = cena.mapa.caixao[0] + 3
    cy = cena.mapa.caixao[1]
    cena.posicao = pygame.Vector2(cena.mapa.para_pixels(cx, cy, cena.tile))
    cena.esqueleto = pygame.Vector2(cena.posicao) + pygame.Vector2(10, 0)
    manager.update(dt)
    assert manager.active_name == "combat", (
        f"a luta nao comecou, continua em {manager.active_name}"
    )
    print("[ok] encostar no esqueleto abre o combate")


def check_clamp_por_modo() -> None:
    """O desktop cru vale em tela cheia e NAO vale em janela.

    Este e o bug do video. Em tela cheia a lista oferece o desktop
    inteiro (1536x960 aqui), porque em tela cheia ele e valido. Ao
    desligar a tela cheia esse mesmo numero vira JANELA: 1536 mais a
    moldura de 16 da 1552, numa area de trabalho de 1536. A janela
    ficava 16px para fora e 39px para baixo.

    O clamp so rodava na inicializacao do jogo, entao a troca de modo
    passava direto. E so aparecia DEPOIS de uma ida e volta de tela
    cheia, nunca na primeira vez.
    """
    from src.config import Config, usable_window_size

    desktop = pygame.display.get_desktop_sizes()
    if not desktop:
        print("[aviso] pygame nao inicializado; pulando o clamp por modo")
        pygame.init()
        desktop = pygame.display.get_desktop_sizes()
    if not desktop:
        print("[aviso] sem informacao de tela; pulando o clamp por modo")
        return
    largura, altura = max(desktop)

    # em tela cheia o desktop cru e uma opcao legitima
    cheia = Config(width=largura, height=altura, fullscreen=True).clamp()
    assert cheia.size == (largura, altura), (
        f"em tela cheia o desktop {largura}x{altura} foi barrado: {cheia.size}"
    )
    print(f"[ok] em tela cheia o desktop {largura}x{altura} e aceito")

    # em janela o MESMO tamanho tem de ser rebaixado ate caber
    janela = Config(width=largura, height=altura, fullscreen=False).clamp()
    limite = usable_window_size()
    assert janela.size != (largura, altura), (
        "o desktop cru passou como tamanho de janela; a janela nao cabe"
    )
    assert janela.width <= limite[0] and janela.height <= limite[1], (
        f"rebaixou para {janela.size}, que ainda passa do limite {limite}"
    )
    # e o rebaixado tem de caber COM a moldura, que e o ponto do defeito
    if limite:
        assert janela.width + 16 <= largura and janela.height + 39 <= altura, (
            f"{janela.size} mais a moldura ainda nao cabe em {largura}x{altura}"
        )
    print(
        f"[ok] em janela o desktop vira {janela.size} "
        f"(limite {limite}), e com a moldura cabe"
    )


def check_moldura_zero_nao_apaga_cache() -> None:
    """(0, 0) e o que a medicao devolve em tela cheia.

    Se esse zero entrasse no cache, o limite voltava a ser o desktop
    inteiro e o filtro oferecia um tamanho de janela que nao cabe.
    """
    import src.config as cfg

    original = cfg._FRAME_CACHE
    try:
        cfg.set_window_frame((16, 39))
        assert cfg._FRAME_CACHE == (16, 39), cfg._FRAME_CACHE
        cfg.set_window_frame((0, 0))  # o que tela cheia devolve
        assert cfg._FRAME_CACHE == (16, 39), (
            f"o zero de tela cheia apagou a moldura: {cfg._FRAME_CACHE}"
        )
        print("[ok] a medicao (0,0) de tela cheia nao apaga a moldura")

        # e uma medicao absurda tambem e descartada
        cfg.set_window_frame((256, 240))
        assert cfg._FRAME_CACHE == (16, 39), (
            f"aceitou moldura absurda: {cfg._FRAME_CACHE}"
        )
        print("[ok] medicao absurda e descartada, sem apagar a moldura")
    finally:
        cfg._FRAME_CACHE = original


def check_equipamento_abre_com_r() -> None:
    """Q abre o inventario e R abre o submenu de equipamento.

    O R estava com o teste ANINHADO dentro do do Q nas tres cenas: o
    evento de R nunca satisfazia a condicao do Q, entao o submenu era
    inalcancavel. Este teste e o que impede a volta do aninhamento.
    """
    import pygame as _pg
    manager = _manager()
    for nome in ("dungeon", "road", "city"):
        manager.ui_state.clear()
        manager.ui_state["progresso"] = Progresso()
        manager.ui_state["estado"] = Estado(vida=30, ouro=200)
        manager.switch(nome)
        cena = manager.active
        if hasattr(cena, "on_enter"):
            cena.on_enter()
        # a masmorra e a estrada tem abertura antes de aceitar tecla, e a
        # masmorra ainda tem a aula na tela: as duas engolem o Q e o
        # teste passava a testar a aula, nao o menu
        for _ in range(int(12.0 / (1 / 60))):
            manager.update(1 / 60)
        tuta = getattr(cena, "tutorial", None)
        for _ in range(int(20.0 / (1 / 60))):
            if tuta is None or (tuta.indice < 0 and tuta.tempo <= 0):
                break
            manager.update(1 / 60)

        cena.handle_event(keydown(_pg.K_q))
        assert cena.inventario_aberto, f"{nome}: o Q nao abriu o inventario"

        cena.handle_event(keydown(_pg.K_r))
        assert cena.modo_equip is not None, (
            f"{nome}: o R nao abriu o submenu de equipamento com o "
            "inventario aberto"
        )

        # e o R de novo fecha, para o submenu nao ser uma单向 street
        cena.handle_event(keydown(_pg.K_r))
        assert cena.modo_equip is None, (
            f"{nome}: o R nao fechou o submenu de equipamento"
        )

        # R sem o inventario aberto nao pode abrir nada
        cena.handle_event(keydown(_pg.K_q))
        assert not cena.inventario_aberto, f"{nome}: o Q nao fechou"
        cena.handle_event(keydown(_pg.K_r))
        assert cena.modo_equip is None, (
            f"{nome}: o R abriu equipamento com o inventario fechado"
        )
    print("[ok] Q e R abrem e fecham os menus nas tres cenas")

    # o desenho do submenu nao pode estourar: antes ele era definido e
    # nunca chamado, e agora e chamado dentro do desenho do inventario
    manager.ui_state.clear()
    manager.ui_state["progresso"] = Progresso()
    manager.ui_state["estado"] = Estado(vida=30, ouro=200)
    manager.switch("city")
    cena = manager.active
    cena.handle_event(keydown(_pg.K_q))
    cena.handle_event(keydown(_pg.K_r))
    manager.draw()
    assert cena.modo_equip == 0, cena.modo_equip
    print("[ok] o submenu de equipamento e desenhado")


def check_primeiro_inimigo_fraco() -> None:
    """O esqueleto da sala 1 e mais fraco que o das outras salas.

    O campo `fracos` existia no progresso desde o comeco e ninguem lia:
    a primeira luta montava o mesmo esqueleto das outras, so que com a
    placa de "aqui voce aprende".
    """
    from src import combat as _combat

    fraco = _combat.novo_esqueleto(0, fraco=True)
    normal = _combat.novo_esqueleto(0)

    assert fraco.vida_max < normal.vida_max, (fraco.vida_max, normal.vida_max)
    assert fraco.forca < normal.forca, (fraco.forca, normal.forca)
    assert fraco.defesa <= normal.defesa, (fraco.defesa, normal.defesa)
    # a iniciativa: o esqueleto da sala 1 e mais lento, o que da a vez
    # ao jogador antes de levar o contra-ataque. Era a barra que enchia
    # devagar; na luta por turnos e a ordem da fila.
    assert fraco.velocidade < normal.velocidade, (
        fraco.velocidade, normal.velocidade
    )
    # e ele nao e o primeiro da fila: o jogador age antes
    b = _combat.Batalha(heroi=_combat.novo_heroi(), inimigos=[fraco])
    assert b.de_quem_e_a_vez is b.heroi, (
        "o esqueleto fraco abriu a fila contra o heroi")
    print(f"[ok] sala 1: vida {fraco.vida_max} forca {fraco.forca} "
          f"(normal: {normal.vida_max}/{normal.forca}), "
          f"e o jogador age primeiro")
    print(f"[ok] sala 1: vida {fraco.vida_max} forca {fraco.forca} "
          f"(normal: {normal.vida_max}/{normal.forca})")

    # e so a sala 1 que e fraca
    p = Progresso()
    for numero in range(1, len(cena_salas()) + 1):
        p.sala = numero
        esperado = numero == 1
        assert p.sala_atual().fracos is esperado, (
            f"a sala {numero} marcou fracos={p.sala_atual().fracos}, "
            f"esperado {esperado}"
        )
    print("[ok] so a sala 1 monta o esqueleto fraco")


def cena_salas():
    from src.progresso import SALAS
    return SALAS


def check_menu_de_combate_da_arte() -> None:
    """O menu de combate usa os slots da arte, e o inventario e a arte.

    Sem isto o jogo volta para a lista de texto em qualquer maquina que
    nao tenha os arquivos de UI, e o defeito some do teste.
    """
    from src import ui_arte

    import pygame as _pg
    _pg.init()
    _pg.display.set_mode((1, 1))

    for nome in (ui_arte.PAINEL_INVENTARIO, ui_arte.PAINEL_LOJA,
                 ui_arte.PAINEL_EQUIPAMENTO, ui_arte.PAINEL_ACAO_BAR,
                 ui_arte.PAINEL_ACAO_HEADER):
        img = ui_arte.carregar(nome)
        assert img is not None, f"painel ausente: {nome}"
        assert img.get_width() >= 10 and img.get_height() >= 10, (
            nome, img.get_size()
        )
    print("[ok] os cinco paineis do pacote carregam")

    # os slots tem que cair dentro do miolo: foi o erro da versao
    # anterior, em que as linhas cobriam a moldura
    s = _pg.Surface((400, 400))
    for nome, topo, base in (
        (ui_arte.PAINEL_LOJA, 0.10, 0.94),
        (ui_arte.PAINEL_ACAO_BAR, 0.24, 0.90),
    ):
        miolo = ui_arte.desenhar(s, nome, (200, 200), 300,
                                 topo_rel=topo, base_rel=base)
        assert miolo is not None, nome
        slots = (ui_arte.slots_da_loja(miolo, 6) if nome == ui_arte.PAINEL_LOJA
                 else ui_arte.slots_da_barra(miolo, 5))
        for r in slots:
            assert r.width > 4 and r.height > 4, (nome, r)
            assert miolo.colliderect(r), f"{nome}: o slot {r} saiu do miolo"
    print("[ok] os slots ficam dentro do miolo do painel")


def check_taverna() -> None:
    """A taverna e um lugar de verdade: salao, dono, e a porta de volta.

    O teste pega as tres coisas que quebraram nesta cena: a planta com
    linhas de tamanhos diferentes (o desenho estourava em
    `PLANTA[y + 1][x]`), o balcao desenhado sete vezes em fila (uma
    peca grande e desenhada uma vez so, no canto) e o R que nao
    abria o submenu aqui como nas outras cenas.
    """
    import pygame as _pg
    from src import tavern_scene as ts

    # 1. a planta e retangular, senao o jogador anda para fora
    larguras = {len(l) for l in ts.PLANTA}
    assert larguras == {len(ts.PLANTA[0])}, larguras
    print(f"[ok] a planta e retangular: {len(ts.PLANTA[0])}x{len(ts.PLANTA)}")

    # 2. a planta so usa letras que a tabela conhece, e a tabela so
    #    aponta para pecas que existem no disco
    desconhecidas = set("".join(ts.PLANTA)) - set(ts.PECAS)
    assert not desconhecidas, f"letras sem peca: {sorted(desconhecidas)}"
    ausentes = sorted(
        letra for letra, (nome, _a, _c, _l) in ts.PECAS.items()
        if ts.peca(nome) is None
    )
    assert not ausentes, f"pecas sem arquivo: {ausentes}"
    print(f"[ok] as {len(ts.PECAS)} pecas da planta estao todas no disco")

    # 3. o jogador comeca em chao e a porta e a saida
    manager = _manager()
    manager.ui_state.clear()
    manager.ui_state["progresso"] = Progresso()
    manager.ui_state["estado"] = Estado(vida=30, ouro=400)
    manager.switch("tavern")
    cena = manager.active
    assert ts.amenities(int(cena.posicao.x // ts.TILE),
                         int(cena.posicao.y // ts.TILE)), (
        cena.posicao, "o jogador comecou dentro da parede")
    manager.draw()
    print("[ok] a taverna desenha com o jogador em pe no salao")

    # 4. os menus funcionam aqui como nas outras tres cenas
    cena.handle_event(keydown(_pg.K_q))
    assert cena.inventario_aberto, "o Q nao abriu o inventario"
    cena.handle_event(keydown(_pg.K_r))
    assert cena.modo_equip is not None, "o R nao abriu o equipamento"
    cena.handle_event(keydown(_pg.K_r))
    assert cena.modo_equip is None, "o R nao fechou o equipamento"
    cena.handle_event(keydown(_pg.K_q))
    assert not cena.inventario_aberto, "o Q nao fechou o inventario"
    print("[ok] Q e R funcionam dentro da taverna")

    # 5. dormir e cobrar, e sem moeda nao se dorme
    cena.posicao = pygame_math_copy(cena.tao)
    cena.estado.ouro = 0
    cena.handle_event(keydown(_pg.K_e))
    assert cena.estado.ouro == 0, ("gastou sem moeda", cena.estado.ouro)
    assert "dorme" in cena.avisar, cena.avisar
    cena.estado.ouro = 999
    vida_antes = cena.estado.vida
    cena.handle_event(keydown(_pg.K_e))
    assert cena.estado.ouro < 999, "nao cobrou a taverna"
    assert cena.estado.vida >= vida_antes, (vida_antes, cena.estado.vida)
    print(f"[ok] dormir cobra e cura: {vida_antes} -> {cena.estado.vida}")

    # 6. o E na porta devolve o jogador para a aldeia
    manager.switch("tavern")
    cena = manager.active
    cena.posicao = pygame_math_copy(cena.tao)
    cena.posicao.y = ts.TILE * 9.4
    cena.posicao.x = ts.TILE * 18.0
    cena.handle_event(keydown(_pg.K_e))
    assert manager.active is not cena, "a porta nao led para a aldeia"
    print("[ok] a porta devolve o jogador para a aldeia")


def pygame_math_copy(v):
    import pygame as _pg
    return _pg.Vector2(v)


def check_ciclo_da_masmorra() -> None:
    """Acorda, encontra o esqueleto, luta, ganha e volta — sem perder nada.

    Este e o teste do defeito que o jogador RELATOU: ao matar o
    esqueleto a vida, o ouro e as salas vencidas voltavam ao que estavam
    no arquivo, e o jogador aparecia de novo dentro do caixao.

    As quatro causas, uma por uma:

    - `save_carregado` ficava no estado do gerenciador e era aplicado em
      toda entrada na masmorra, inclusive ao voltar de uma luta;
    - a cena nova comecava em "acordando" e jogava o jogador no caixao;
    - a vitoria marcava a sala onde esta o CHEFE, e nao a onde o
      jogador lutou, pagando a recompensa do chefe;
    - a tecla de dispensar a tela de fim de luta podia chegar antes do
      quadro que da nome ao resultado, e a vitoria se perdia.
    """
    manager = _manager()
    manager.ui_state.clear()
    manager.ui_state["progresso"] = Progresso()
    manager.ui_state["estado"] = Estado(vida=30, ouro=0)

    manager.switch("dungeon")
    cena = manager.active
    cena.on_enter()
    dt = 1 / 60
    for _ in range(int(7.0 / dt)):
        manager.update(dt)
    assert cena.fase == "livre", cena.fase

    for _ in range(30):
        manager.update(dt)
        if cena.esqueleto is not None:
            break
    assert cena.esqueleto is not None, "o esqueleto nao emergiu do chao"

    lugar = cena.esqueleto.copy()
    for _ in range(400):
        if manager.active is not cena:
            break
        cena.posicao = lugar.copy()
        manager.update(dt)
    assert type(manager.active).__name__ == "CombatScene", (
        type(manager.active).__name__
    )
    onde_lutou = (cena.posicao.x, cena.posicao.y)

    combate = manager.active
    for _ in range(9000):
        if manager.active is not combate:
            break
        if combate.batalha.concluida or (
                combate.menu_aberto and combate.modo == "acao"):
            combate.handle_event(keydown(pygame.K_RETURN))
            combate.handle_event(keyup(pygame.K_RETURN))
        manager.update(dt)

    assert manager.active is not combate, "a luta nao terminou"
    cena = manager.active
    assert type(cena).__name__ == "DungeonScene", type(cena).__name__
    manager.update(dt)

    caixao = cena._centro_caixao()
    voltou = max(abs(cena.posicao.x - onde_lutou[0]),
                 abs(cena.posicao.y - onde_lutou[1]))
    assert cena.fase == "livre", (
        f"a volta da luta abriu a abertura de novo: {cena.fase}")
    # o contrato e o jogador voltar ONDE A LUTA COMECOU. Comparar com o
    # caixao nao serve: o esqueleto pode nascer em cima dele, e ai o
    # caixao e a posicao certa.
    assert voltou <= cena.tile, (
        f"o jogador nao voltou onde lutou (dist={voltou:.0f}px)")
    print(f"[ok] a volta da luta nao abre o caixao e devolve o "
          f"jogador ao ponto da luta")

    assert cena.progresso.vencidas == [1], (
        f"a sala vencida e {cena.progresso.vencidas}, e nao a do jogador")
    ouro = manager.ui_state["estado"].ouro
    esperado = Progresso().recompensa_por_vencer(1)
    assert ouro == esperado, f"pagou {ouro}, a sala 1 paga {esperado}"
    print(f"[ok] a vitoria marca a sala do jogador e paga {ouro} de ouro")


def check_save_aplicado_so_na_primeira_entrada() -> None:
    """O save do menu vale para a primeira entrada, e so para ela.

    O `save_carregado` ficava no estado do gerenciador e a masmorra o
    lia com `get`, sem remover. Como a masmorra e recriada ao voltar de
    uma luta, o arquivo era lido de novo e apagava tudo o que a luta
    tinha dado.
    """
    from src.saves import Save

    manager = _manager()
    manager.ui_state.clear()
    manager.ui_state["save_carregado"] = Save(
        area="catacumbas", x=100.0, y=200.0, direcao="norte",
        tempo_jogado=42.0,
    )

    manager.switch("dungeon")
    primeira = manager.active
    assert primeira.fase == "livre", (
        "a primeira entrada depois do Continuar devia pular a abertura")
    assert "save_carregado" not in manager.ui_state, (
        "o save carregado ficou no estado e sera aplicado de novo")

    manager.switch("dungeon")
    segunda = manager.active
    assert segunda.fase == "acordando", (
        f"a segunda entrada nao devia reaplicar o save: {segunda.fase}")
    print("[ok] o save do menu e aplicado uma vez so")


def check_corrida_shift() -> None:
    """Shift e um segundo passo: mais longe, mais rapido, e com poeira.

    Quatro coisas podem quebrar aqui, e nenhuma delas aparece
    quebrada, entao o teste pergunta cada uma:

      - `correndo_agora` ler o Shift do teclado e nao do evento. Com o
        evento, segurar a seta e apertar o Shift depois nao mudaria
        nada, que e justo o que o jogador faz;
      - o passo dobrar de verdade, e nao so a animacao parecer mais
        rapida;
      - a corrida levantar poeira, senao e so o mesmo boneco com o
        tempo trocado;
      - o MEIO do caminho mandar. O passo de corrida vale um tile, e
        testando so o destino o heroi aparecia do outro lado de uma
        parede no meio do aperto.
    """
    import pygame as _pg
    from src import animacao

    # o Shift e lido do teclado, e o teclado so existe depois da tela
    _pg.init()
    _pg.display.set_mode((80, 80))
    _pg.key.set_mods(0)
    assert not animacao.correndo_agora(), "sem Shift nao ha corrida"
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    assert animacao.correndo_agora(), "Shift nao foi lido"
    _pg.key.set_mods(_pg.KMOD_LSHIFT)
    assert animacao.correndo_agora(), "so o Shift esquerdo nao conta"
    _pg.key.set_mods(0)
    print("[ok] Shift e Shift esquerdo sao corrida, sem nenhum nao e")

    # o passo corre mais rapido que o passo normal. O dt e pequeno de
    # proposito: a fase da a volta em 1.0, e um dt grande embrulha os
    # dois lados e a comparacao vira sorte
    devagar = animacao.Passo()
    rapido = animacao.Passo()
    rapido.correndo = True
    devagar.advance(0.05, True)
    rapido.advance(0.05, True)
    assert rapido.fase > devagar.fase, "a corrida nao acelerou o passo"
    assert abs(rapido.fase - devagar.fase * animacao.FATOR_CORRIDA) < 0.001
    print(f"[ok] a corrida acelera o passo: {devagar.fase:.2f} -> {rapido.fase:.2f}")

    # a poeira so aparece quando o passo esta correndo
    passo = animacao.Passo()
    passo.advance(0.1, True)
    limpa = _pg.Surface((80, 80), _pg.SRCALPHA)
    animacao._poeira_de_corrida(limpa, _pg.Rect(30, 40, 20, 40), passo, 32)
    # um Surface nao tem get_bbox nem tobytes nesta versao, e o
    # surfarray exigiria numpy que o jogo nao usa. `pygame.image.tostring`
    # le a tela inteira como bytes, e compara-la com uma tela vazia diz
    # se algo foi pintado, sem dependencia nenhuma
    from pygame import image as _img
    vazia = _pg.Surface((80, 80), _pg.SRCALPHA)
    assert _img.tostring(limpa, "RGBA") == _img.tostring(vazia, "RGBA"), (
        "andando tem poeira no ar")
    passo.correndo = True
    poeirenta = _pg.Surface((80, 80), _pg.SRCALPHA)
    animacao._poeira_de_corrida(poeirenta, _pg.Rect(30, 40, 20, 40), passo, 32)
    assert _img.tostring(poeirenta, "RGBA") != _img.tostring(vazia, "RGBA"), (
        "correndo nao levantou poeira")
    print("[ok] a poeira so levanta na corrida")

    manager = _manager()
    manager.ui_state.clear()

    # a aldeia: meio tile andando, um tile com Shift
    manager.switch("city")
    cidade = manager.active
    cidade.perto = None
    cidade.avisar_tempo = 0.0
    cidade._livre = lambda ponto: True
    _pg.key.set_mods(0)
    antes = cidade.posicao.copy()
    press(manager, _pg.K_RIGHT)
    andando = abs(cidade.posicao.x - antes.x)
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    antes = cidade.posicao.copy()
    press(manager, _pg.K_RIGHT)
    correndo = abs(cidade.posicao.x - antes.x)
    assert abs(andando - cidade.tile * animacao.PASSO_ANDAR) < 0.01, andando
    assert abs(correndo - cidade.tile * animacao.PASSO_CORRIDA) < 0.01, correndo
    assert cidade.andamento.correndo, "a cena nao guardou a corrida"
    print(f"[ok] na aldeia o aperto vale {andando}px andando e {correndo}px correndo")

    # parede no meio do caminho derruba a corrida para o passo normal
    respostas = []

    def livre_ate_depois(ponto):
        respostas.append(ponto)
        return len(respostas) > 1

    cidade._livre = livre_ate_depois
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    antes = cidade.posicao.copy()
    press(manager, _pg.K_RIGHT)
    cutado = abs(cidade.posicao.x - antes.x)
    assert abs(cutado - cidade.tile * animacao.PASSO_ANDAR) < 0.01, (
        f"passou a parede com o meio ocupado: {cutado}px")
    print("[ok] parede no meio do caminho corta a corrida para meio tile")

    # a estrada e a taverna usam a mesma regra, com metodo proprio
    manager.switch("road")
    estrada = manager.active
    estrada._livre = lambda ponto: True
    _pg.key.set_mods(0)
    antes = estrada.posicao.copy()
    estrada._andar(1, 0)
    passo_estrada = abs(estrada.posicao.x - antes.x)
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    antes = estrada.posicao.copy()
    estrada._andar(1, 0)
    corrida_estrada = abs(estrada.posicao.x - antes.x)
    assert corrida_estrada > passo_estrada, (passo_estrada, corrida_estrada)
    print(f"[ok] na estrada: {passo_estrada}px andando, {corrida_estrada}px correndo")

    # e a estrada tambem recua para meio tile com o meio do caminho
    # ocupado. A condicao aqui ja foi escrita ao contrario uma vez, e
    # o teste e o que impede que ela volte
    respostas = []

    def livre_ate_depois(ponto):
        respostas.append(ponto)
        return len(respostas) > 1

    estrada._livre = livre_ate_depois
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    antes = estrada.posicao.copy()
    estrada._andar(1, 0)
    cutado = abs(estrada.posicao.x - antes.x)
    assert abs(cutado - estrada.tile * animacao.PASSO_ANDAR) < 0.01, (
        f"a estrada passou a parede com o meio ocupado: {cutado}px")
    print("[ok] a estrada tambem para no meio quando o meio esta ocupado")

    manager.switch("tavern")
    sala = manager.active
    # o chao livre e Patchado: o teste mede o tamanho do passo, e nao
    # a planta da taverna
    from src import tavern_scene as ts
    # `amenities` quer dizer "a celula esta livre", entao e True que abre
    # caminho, e nao False
    ts.amenities = lambda x, y: True
    _pg.key.set_mods(0)
    antes = sala.posicao.copy()
    sala._andar(1, 0)
    passo_sala = abs(sala.posicao.x - antes.x)
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    antes = sala.posicao.copy()
    sala._andar(1, 0)
    corrida_sala = abs(sala.posicao.x - antes.x)
    assert abs(passo_sala - ts.TILE * animacao.PASSO_ANDAR) < 0.01, passo_sala
    assert abs(corrida_sala - ts.TILE * animacao.PASSO_CORRIDA) < 0.01, corrida_sala
    assert sala.andamento.correndo, "a taverna nao guardou a corrida"
    print(f"[ok] na taverna: {passo_sala}px andando, {corrida_sala}px correndo")

    # o mesmo meio ocupado, na taverna. `all()` para na primeira celula
    # fechada, entao so a PRIMEIRA leitura e negada: e o meio do caminho
    # que fecha, e o destino fica livre
    leituras = []

    def livre_no_destino_so(x, y):
        leituras.append((x, y))
        return len(leituras) > 1

    ts.amenities = livre_no_destino_so
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    antes = sala.posicao.copy()
    sala._andar(1, 0)
    cutado = abs(sala.posicao.x - antes.x)
    assert abs(cutado - ts.TILE * animacao.PASSO_ANDAR) < 0.01, (
        f"a taverna atravessou o movel com o meio ocupado: {cutado}px")
    print("[ok] a taverna para no meio quando o caminho do meio esta ocupado")

    # a masmorra e continua: la o que dobra e a velocidade, nao o passo
    manager.switch("dungeon")
    masmorra = manager.active
    masmorra.andamento.correndo = False
    lento = masmorra._passo(0.1).length()
    masmorra.andamento.correndo = True
    rapido = masmorra._passo(0.1).length()
    assert abs(rapido - lento * animacao.FATOR_PASSO) < 0.01, (lento, rapido)
    print(f"[ok] na masmorra o passo do heroi vai de {lento:.1f} para {rapido:.1f}")

    # e o Shift e lido a cada quadro, e nao no aperto da seta
    masmorra.fase = "livre"
    _pg.key.set_mods(_pg.KMOD_SHIFT)
    masmorra.andamento.correndo = False
    masmorra.update(0.016)
    assert masmorra.andamento.correndo, "a masmorra nao leu o Shift no quadro"
    _pg.key.set_mods(0)
    masmorra.andamento.correndo = True
    masmorra.update(0.016)
    assert not masmorra.andamento.correndo, "o Shift largado nao parou a corrida"
    print("[ok] a masmorra le o Shift a cada quadro, e solta quando ele larga")

    _pg.key.set_mods(0)
    print("[ok] a corrida com Shift funciona nas quatro cenas do mundo")


def check_corte_de_texto() -> None:
    """O texto cortado cabe na largura, medido com a fonte do jogo.

    O nome do item na loja saia pela borda do slot. A correcao truncou a
    string por numero de caracteres e continuou saindo: o slot tem 57px,
    cada caractere tem uma largura e `theme` desenha letra por letra com
    espacamento. Doze caracteres ainda nao cabiam.

    O teste anda pela propriedade, e nao por lista de casos: para
    qualquer texto e qualquer largura, o que `caber_texto` devolve tem
    de caber, e tem de ser prefixo do original. Cortar nao pode inventar
    nem reordenar nada.
    """
    from src import theme as _theme
    from src import ui_arte as _ui

    pygame.init()
    pygame.display.set_mode((64, 64))

    def largura_real(texto: str, size: int, tracking: int = 2) -> int:
        glifos = _theme._render_glyphs(texto, size, _theme.TEXT, 255)
        if not glifos:
            return 0
        return (sum(g.get_width() for g in glifos)
                + tracking * (len(glifos) - 1))

    nomes = (
        "Pocao", "de cura", "de cura maior",
        "Espada de ferro muito longo", "Maca / Escudo", "X", "",
        "Umafraseabsurdamentelongaquesemaisumponto",
    )
    for largura in (20, 49, 80, 160):
        for nome in nomes:
            for size in (10, 12, 13):
                cortado = _ui.caber_texto(nome, largura, size)
                medido = largura_real(cortado, size)
                assert medido <= largura, (
                    f"o corte {cortado!r} mede {medido}px e o limite e "
                    f"{largura}px")
                assert nome.startswith(cortado), (
                    f"{cortado!r} nao e prefixo de {nome!r}")
    print("[ok] nenhum corte vaza em nenhuma largura, e todos sao prefixo")

    # o limite minimo e a largura de um glifo: abaixo dela nao existe
    # corte que caiba, e o certo e devolver vazio. Uma versao deste
    # teste pedia vazio com 12px de largura e falhou; a medicao mostrou
    # que o glifo tem 6px, entao em 12px cabe "U" e o pedido estava
    # errado, e nao a funcao
    glifo = _theme._render_glyphs("U", 12, _theme.TEXT, 255)[0]
    minimo = glifo.get_width()
    assert _ui.caber_texto("U", minimo - 1, 12) == "", (
        f"abaixo de {minimo}px nenhum glifo cabe")
    assert _ui.caber_texto("U", minimo, 12) == "U"
    assert _ui.caber_texto("Uma frase comprida", minimo, 12) == "U"
    print(f"[ok] o limite minimo e {minimo}px, a largura de um glifo")

    # e o nome da loja cabe no slot de verdade, com o painel medido
    manager = _manager()
    manager.ui_state.clear()
    manager.switch("title")
    tela = pygame.Surface(manager.active.size)
    w, h = tela.get_size()
    painel = _ui.desenhar(
        tela, _ui.PAINEL_LOJA, (w // 2, h // 2), int(w * 0.34),
        topo_rel=0.10, base_rel=0.94)
    assert painel is not None, "o painel da loja nao carregou"
    slots = _ui.slots_da_loja(painel, 6)
    util = slots[0].width - 8
    from src import itens as _itens
    for item in _itens.a_venda()[:len(slots)]:
        palavras = item.nome.split()
        for pedaco, size in ((palavras[0], 12),
                             (" ".join(palavras[1:]), 10)):
            if not pedaco:
                continue
            cortado = _ui.caber_texto(pedaco, util, size)
            assert largura_real(cortado, size) <= util, (
                f"{item.nome}: {cortado!r} mede mais que {util}px")
    print(f"[ok] os nomes dos itens cabem no slot de {slots[0].width}px")


def check_lista_de_conjuntos() -> None:
    """A lista de conjuntos cabe na linha, nas quatro cenas do mundo.

    O painel EQUIPMENT tem seis conjuntos, cada um com o boneco daquele
    conjunto. A conta antiga era `miolo.height // 6` para o passo, e o
    boneco era blitado com a altura inteira, 64px, dentro de uma linha
    de 18px: ele transbordava 46px para cima e a primeira linha
    invadia a barra de titulo. Nas quatro copias da lista.

    Alem disso, o miolo do painel traz uma barra de slots VAZIA na
    direita, que e onde a arte original previa os icones. A lista e
    desenhada na esquerda dessa barra, entao a area dela e metade do
    miolo.

    O boneco e estreito e alto, entao o limite do encolhimento e a
    ALTURA da linha, e nao a largura: aos 26% da largura ele saia com
    35px e ainda transbordava.
    """
    from src import assets as _assets
    from src import equipamento as _equip
    from src import ui_arte

    manager = _manager()
    manager.ui_state.clear()
    # a cena so existe depois do primeiro switch, e e dela que vem o
    # tamanho da tela: o `manager.active` comeca nulo
    manager.switch("title")
    tela = pygame.Surface(manager.active.size)
    w, h = tela.get_size()
    conjuntos = _equip.todos_os_conjuntos()

    assert len(conjuntos) == ui_arte._EQUIP_LINHAS, (
        f"a lista desenha {ui_arte._EQUIP_LINHAS} linhas e o jogo tem "
        f"{len(conjuntos)} conjuntos")

    for nome in ("city", "road", "dungeon", "tavern"):
        manager.switch(nome)
        painel = ui_arte.desenhar(
            tela, ui_arte.PAINEL_EQUIPAMENTO,
            (w // 2, h // 2), int(w * 0.34))
        assert painel is not None, f"{nome}: o painel nao carregou"

        linhas, passo = ui_arte.linhas_do_equipamento(painel)
        lado = ui_arte.lado_do_desenho(linhas[0])
        assert lado <= linhas[0].height, (
            f"{nome}: o boneco cabe em {lado}px e a linha tem "
            f"{linhas[0].height}px")

        # o boneco de cada conjunto cabe na linha, medido no desenho real
        for i, c in enumerate(conjuntos):
            arte = _assets.carregar_equipado(c.chave, escala=1)
            if arte is None:
                continue
            pequeno = ui_arte._caber_pequeno(arte, lado)
            assert pequeno.get_height() <= linhas[i].height, (
                f"{nome} conjunto {i} ({c.rotulo}): desenho de "
                f"{pequeno.get_height()}px numa linha de "
                f"{linhas[i].height}px")

        # as seis linhas cabem no miolo
        assert linhas[-1].bottom <= painel.bottom, (
            f"{nome}: a ultima linha sai em {linhas[-1].bottom}, "
            f"o miolo termina em {painel.bottom}")

        # a lista fica na esquerda, sem invadir a barra de slots da arte
        assert linhas[0].right <= painel.centerx, (
            f"{nome}: a lista chega em {linhas[0].right}, o meio e "
            f"{painel.centerx}")

        # o texto comeca depois do boneco
        for i, c in enumerate(conjuntos):
            arte = _assets.carregar_equipado(c.chave, escala=1)
            if arte is None:
                continue
            pequeno = ui_arte._caber_pequeno(arte, lado)
            texto_x = linhas[i].x + pequeno.get_width() + 8
            assert texto_x < painel.right, (
                f"{nome} conjunto {i}: o texto em {texto_x} sai do painel")

        print(f"[ok] {nome}: {len(conjuntos)} conjuntos em linhas de "
              f"{passo}px, boneco de {lado}px, lista em {linhas[0].right}")


def check_rodape_do_inventario() -> None:
    """O rodape do inventario: cada coisa no seu lugar, e nada sobre nada.

    As quatro cenas do mundo tinham cada uma uma copia deste desenho, e
    nas quatro a conta estava errada: a grade usava o miolo inteiro, a
    ultima fileira ficava embaixo do desenho do conjunto, o rotulo caia
    em cima do boneco, e o contador caia em cima da linha de dica, as
    vezes fora do painel.

    Layout nao se prova olhando a foto. Aqui cada peca do rodape ganha um
    retangulo, e o defeito testado e a sobreposicao: dois retangulos que
    se cruzam, mesmo que o resultado final pareca bom.
    """
    from src import ui_arte

    manager = _manager()
    manager.ui_state.clear()
    manager.switch("city")
    tela = pygame.Surface(manager.active.size)
    painel = ui_arte.desenhar(
        tela, ui_arte.PAINEL_INVENTARIO,
        (tela.get_width() // 2, tela.get_height() // 2),
        int(tela.get_width() * 0.42))
    assert painel is not None, "o painel de inventario nao carregou"

    grade, rodape = ui_arte._cabe(painel)

    # a grade para antes do rodape: era a ultima fileira em cima do boneco
    COLUNAS, fileiras = 5, 4
    cw = grade.width // COLUNAS
    ch = grade.height // fileiras
    ultima = pygame.Rect(grade.x, grade.y + 3 * ch, grade.width, ch)
    assert grade.bottom <= rodape.top, "a grade invade o rodape"
    assert ultima.bottom <= rodape.top, f"a ultima fileira invade: {ultima}"
    print(f"[ok] a grade para em {ultima.bottom} e o rodape comeca "
          f"em {rodape.top}")

    # as colunas cabem dentro do painel: as fichas saiam pela esquerda
    for i in range(COLUNAS):
        coluna = pygame.Rect(grade.x + i * cw, grade.y, cw, ch)
        assert coluna.left >= painel.left, f"a coluna {i} sai a esquerda"
        assert coluna.right <= painel.right, f"a coluna {i} sai a direita"
    print(f"[ok] as {COLUNAS} colunas cabem entre {painel.left} e {painel.right}")

    # o rotulo, o contador e o conjunto nao se cruzam
    rotulo = pygame.Rect(rodape.x + 8, rodape.centery - 7, 150, 13)
    contador = pygame.Rect(
        rodape.x + int(rodape.width * ui_arte._INVENTARIO_CONTADOR_X),
        rodape.y + int(rodape.height * ui_arte._INVENTARIO_CONTADOR_TOPO),
        60, 14)
    assert not rotulo.colliderect(contador), f"{rotulo} e {contador} se cruzam"
    reservada = int(rodape.width * ui_arte._INVENTARIO_CONJUNTO_LADO)
    conjunto = pygame.Rect(
        rodape.right - max(reservada, 40) + 4, rodape.y,
        max(reservada, 40), rodape.height - ui_arte._INVENTARIO_CONJUNTO_FOLGA)
    assert conjunto.left >= rotulo.right, f"o conjunto cobre o rotulo: {conjunto}"
    print("[ok] rotulo, contador e conjunto nao se cruzam")

    # o contador fica dentro do painel e acima da linha de dica
    dica = pygame.Rect(painel.left, painel.bottom + 8, 260, 13)
    assert contador.bottom <= painel.bottom, (
        f"o contador saiu do painel: {contador.bottom} > {painel.bottom}")
    assert contador.bottom <= dica.top, (
        f"o contador caiu na dica: {contador.bottom} > {dica.top}")
    print(f"[ok] o contador para em {contador.bottom}, a dica em {dica.top}")

    # e sobra altura para o desenho do conjunto caber na faixa
    altura = rodape.height - ui_arte._INVENTARIO_CONJUNTO_FOLGA
    assert altura >= 24, f"o rodape e curto demais para o boneco: {altura}px"
    print(f"[ok] sobra {altura}px de altura para o desenho do conjunto")

    # a loja usa o mesmo contador, entao a conta tem de servir la tambem.
    # A loja e desenhada de verdade, com o painel SHOP, e o numero tem
    # de cair em cima do desenho da moeda que vem na arte
    from src.city_scene import CityScene
    manager.switch("city")
    cidade = manager.active
    cidade.on_enter()
    cidade.perto = next(
        (m for m in cidade.moradores if m.nome == "O Estranho"), None)
    press(manager, pygame.K_e)
    manager.update(1 / 60)
    assert cidade.loja is not None, "a loja nao abriu para o teste do contador"
    # o miolo da loja: a cena o desenha e devolve, e aqui o teste redesenha
    # o mesmo painel para ter o retangulo em maos
    painel_loja = ui_arte.desenhar(
        pygame.Surface(cidade.size), ui_arte.PAINEL_LOJA,
        (cidade.size[0] // 2, cidade.size[1] // 2),
        int(cidade.size[0] * 0.34), topo_rel=0.10, base_rel=0.94)
    assert painel_loja is not None, "a loja nao desenhou o painel SHOP"
    _, rodape_loja = ui_arte._cabe(painel_loja)
    numero = pygame.Rect(
        rodape_loja.x + int(rodape_loja.width * ui_arte._INVENTARIO_CONTADOR_X),
        rodape_loja.y + int(rodape_loja.height * ui_arte._INVENTARIO_CONTADOR_TOPO),
        60, 14)
    assert numero.bottom <= painel_loja.bottom, (
        f"o numero da loja saiu do painel: {numero.bottom} > {painel_loja.bottom}")
    print(f"[ok] o numero da loja para em {numero.bottom}, "
          f"o painel em {painel_loja.bottom}")


def check_parede_solida() -> None:
    """A parede do mapa e solida, e nao a cor do fundo.

    A grade de tiles desenha so o chao andavel, entao toda celula de
    `PAREDE` ficava com a cor do fundo, `(10, 9, 8)`. A aldeia aparecia
    como um retangulo de pedra dentro de um buraco negro, e o preto era
    tao parecido com arte faltando que o defeito se lia como bug.

    O teste pergunta as tres coisas que a pedra precisa cumprir:

      - ela e mais clara que o fundo, senao continua sendo buraco;
      - ela e chapada. Ja houve tres versoes com textura: degrade por
        tile (listras horizontais a cada 48 pixels), grao de hash
        (hachura diagonal) e uma fissura por variante (marca d'agua).
        Nenhuma sobreviveu a olhar a imagem;
      - ela nao muda de tom de uma celula para a outra. Com tres tons
        separados por tres canais, os vizinhos viravam faixas de uma
        tonalidade so, e num mapa escuro, onde os tons vivem entre 24 e
        33, seis canais de diferenca sao 20% de mudanca: bem visivel.
    """
    from pygame import image as _img
    from src import rocha, theme

    pygame.init()
    pygame.display.set_mode((64, 64))

    LADO = 48
    pedra = rocha.tile(LADO)
    tons_dentro = {tuple(pedra.get_at((x, y)))
                   for x in range(LADO) for y in range(LADO)}
    tons_parede = {tuple(rocha.celula(LADO, x, y).get_at((3, 3)))
                   for x in range(20) for y in range(10)}

    assert len(tons_dentro) == 1, f"a pedra ganhou textura: {sorted(tons_dentro)}"
    assert len(tons_parede) == 1, f"a parede ganhou faixas: {sorted(tons_parede)}"
    assert rocha.BASE[0] > theme.BACKGROUND[0], (
        f"a pedra {rocha.BASE} nao se distingue do fundo {theme.BACKGROUND}")
    print(f"[ok] a parede e solida e chapada: {rocha.BASE} contra {theme.BACKGROUND}")

    # e a cena usa a pedra: um pixel da janela, no meio da parede da
    # aldeia, tem de ser a pedra e nao o fundo. Um teste so da cor nao
    # pegaria a parede se a cena voltasse a pular a celula
    manager = _manager()
    manager.ui_state.clear()
    manager.switch("city")
    cidade = manager.active
    tela = pygame.Surface(cidade.size)
    for _ in range(20):
        cidade.update(1 / 60)
        cidade.draw(tela)
    encontrada = False
    for y in range(0, tela.get_height(), 4):
        for x in range(0, tela.get_width(), 4):
            if tuple(tela.get_at((x, y))[:3]) == tuple(rocha.BASE[:3]):
                encontrada = True
                break
        if encontrada:
            break
    assert encontrada, "a pedra existe mas a aldeia nao esta desenhando"
    print("[ok] a aldeia esta desenhando a pedra na tela")

    # a estrada tambem, que e a outra cena com a mesma grade
    manager.switch("road")
    estrada = manager.active
    for _ in range(20):
        estrada.update(1 / 60)
        estrada.draw(tela)
    encontrada = False
    for y in range(0, tela.get_height(), 4):
        for x in range(0, tela.get_width(), 4):
            if tuple(tela.get_at((x, y))[:3]) == tuple(rocha.BASE[:3]):
                encontrada = True
                break
        if encontrada:
            break
    assert encontrada, "a estrada continua desenhando o fundo na parede"
    print("[ok] a estrada tambem desenha a pedra")


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
    check_clamp_por_modo()
    print()
    check_moldura_zero_nao_apaga_cache()
    print()
    check_dungeon_map()
    print()
    check_wang()
    print()
    check_fuga()
    print()
    check_itens()
    print()
    check_cidade()
    print()
    check_refugio()
    print()
    check_equipamento()
    print()
    check_heroi_tela()
    print()
    check_persistencia()
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
    check_menu_do_combate()
    print()
    check_enfeites_da_luta()
    print()
    check_turnos_regras()
    print()
    check_turnos_tela()
    print()
    check_combat_bases()
    print()
    check_combat_batalha()
    print()
    check_combat_cena()
    print()
    check_tutorial()
    print()
    check_tutorial_na_masmorra()
    print()
    check_equipamento_abre_com_r()
    print()
    check_primeiro_inimigo_fraco()
    print()
    check_menu_de_combate_da_arte()
    print()
    check_taverna()
    print()
    check_corrida_shift()
    print()
    check_corte_de_texto()
    print()
    check_lista_de_conjuntos()
    print()
    check_rodape_do_inventario()
    print()
    check_parede_solida()
    print()
    check_ciclo_da_masmorra()
    print()
    check_save_aplicado_so_na_primeira_entrada()
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


