"""Ponto de entrada do jogo.

Executa o loop principal: pump de eventos, update com delta time,
desenho e controle de FPS.

Sobre os 60 FPS: o limite vem de `Config.fps_limit`, e o vsync fica
ligado por padrao. Com vsync ligado o SDL espera o sinal do monitor,
o que evita rasgo de imagem; o limite de FPS continua valendo como
teto. Quem manda no ritmo e o monitor, nao o relogio do Python.
"""
from __future__ import annotations

import os
import sys

import pygame

from . import assets, settings
from .combat_scene import CombatScene
from .config import Config, native_refresh_rate, set_window_frame
from .dungeon_scene import DungeonScene
from .game_scene import GameScene
from .input_map import InputMap
from .options_screen import OptionsScreen
from .scene_manager import SceneManager
from .title_screen import TitleScreen

# Diagnostico de entrada: com TRACE=1, cada tecla recebida e impressa
# junto da cena ativa. Sem isso nao da para saber se o problema e a tecla
# nao chegando, ou a cena ignorando.
_TRACE = os.environ.get("TRACE") == "1"

# Acoes relevantes vao para um arquivo sempre, nao so com TRACE. Se o
# jogo travar numa acao (trocar resolucao, abrir captura), o arquivo
# mostra a ultima coisa que aconteceu antes.
_LOG_PATH = settings.ROOT_DIR / "jogo.log"


def _log(message: str) -> None:
    """Escreve no arquivo de log e, se TRACE, tambem no console."""
    from datetime import datetime

    stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{stamp}] {message}"
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    if _TRACE:
        print(line, flush=True)


def _log_event(manager: SceneManager, event: pygame.event.Event) -> None:
    """Imprime o evento e a cena que deveria tratar."""
    if event.type == pygame.KEYDOWN:
        nome = pygame.key.name(event.key)
        acoes = manager.controls.actions_for(event.key)
        where = manager.active_name
        grupo = getattr(manager.active, "group", "-")
        idx = getattr(manager.active, "index", "-")
        print(
            f"[trace] KEYDOWN {nome!r:14} key={event.key:11} unicode={event.unicode!r:6} "
            f"cena={where} aba={grupo} linha={idx} acoes={acoes}",
            flush=True,
        )
        if acoes:
            _log(f"tecla {nome} -> {acoes} (cena {where}, linha {idx})")
    elif event.type == pygame.MOUSEBUTTONDOWN:
        _log(f"clique em {event.pos}")


def build_scene_manager(manager: SceneManager) -> SceneManager:
    manager.register("title", TitleScreen)
    manager.register("options", OptionsScreen)
    manager.register("game", GameScene)
    manager.register("dungeon", DungeonScene)
    manager.register("combat", CombatScene)
    return manager


def create_window(config: Config) -> pygame.Surface:
    """Cria (ou recria) a janela exatamente na resolucao escolhida.

    Nao rebaixa a resolucao aqui. Quem garante que ela cabe na tela e o
    filtro do menu de opcoes; rebaixar em silencio faria o jogo rodar
    em um tamanho diferente do que o jogador escolheu, sem ele pedir.
    `SCALED` aceita uma janela maior que a tela de proposito, e o
    jogador que pediu 1920x1080 num desktop de 1536x960 viu que a tela
    e pequena e escolheu assim mesmo.

    SCALED depende de aceleracao. Onde ela nao existe (driver virtual
    de teste), o pygame reclama e a janela nao abre, entao ha um
    caminho sem SCALED.

    Sair de tela cheia tem uma peculiaridade do Windows que vale um
    paragrafo: o primeiro `set_mode` depois de deixar o fullscreen NAO
    aplica o tamanho novo. A janela fica com a geometria antiga, maior
    que a tela, e a moldura medida sai dobrada (32x78 em vez de 16x39).
    Medindo isso, o filtro de resolucao passa a oferecer um tamanho
    menor a cada viagem de ida e volta, ate a janela nao caber.

    A segunda chamada no mesmo tamanho assenta a janela, verificado:
    1552x999 -> 1536x960 e a moldura volta a 16x39. Por isso, so quando
    se sai de tela cheia, `set_mode` e chamado duas vezes.
    """
    size = config.size

    # o modo ATUAL, antes de trocar: e dele que se descobre se ha uma
    # transicao de tela cheia para janela
    was_fullscreen = False
    if pygame.display.get_init():
        current = pygame.display.get_surface()
        if current is not None:
            was_fullscreen = bool(current.get_flags() & pygame.FULLSCREEN)

    # SCALED exige aceleracao. Em driver virtual (teste headless) ela
    # nao existe, e o proprio pygame avisa "no fast renderer available".
    headless = os.environ.get("SDL_VIDEODRIVER") == "dummy"

    if not headless:
        flags = pygame.SCALED
        if config.fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            surface = pygame.display.set_mode(
                size, flags, vsync=1 if config.vsync else 0
            )
        except pygame.error as exc:
            # SCALED|FULLSCREEN falha em alguns drivers; tenta sem vsync
            try:
                surface = pygame.display.set_mode(size, flags)
            except pygame.error:
                print(f"[video] SCALED indisponivel ({exc}), usando modo padrao")
                surface = pygame.display.set_mode(size, flags)

        # saindo de tela cheia: a segunda chamada assenta o tamanho
        if was_fullscreen and not config.fullscreen:
            surface = pygame.display.set_mode(
                size, flags, vsync=1 if config.vsync else 0
            )
        return surface
    else:
        flags = pygame.FULLSCREEN if config.fullscreen else 0

    return pygame.display.set_mode(size, flags)


def measure_window_frame(fullscreen: bool = False) -> tuple[int, int]:
    """Quanto a moldura da janela soma em cada dimensao.

    Mede a diferenca entre a janela de fora e a superficie de desenho.
    Chutar esse valor erra: uma janela de 1504x928 vira 1520x967 de
    fora, ou seja 16px de lado e 39px de altura (a barra de titulo).
    Sem descontar isso, a maior resolucao oferecida estourava a tela
    embaixo.

    EM TELA CHEIA ISSO NAO E MEDIDO, E (0, 0). Nao existe moldura: a
    janela ocupa a tela inteira e a diferenca entre o retangulo da
    janela e a superficie de desenho e oEspaco da escala, nao a borda.
    Medir ali dava 256x240 num 1280x720 em tela cheia num desktop de
    1536x960 (1536-1280, 960-720), e esse numero falso entrava no
    filtro de resolucao como se fosse borda. O filtro passava a
    oferecer so 1280x720, ou seja: entrar em tela cheia sumia com as
    resolucoes maiores, e sair de volta deixava um cache corrompido
    que rebaixava a resolucao do jogador na proxima troca.
    """
    if fullscreen:
        return (0, 0)

    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return (16, 39)  # valor tipico, so para o layout do teste

    try:
        import ctypes

        hwnd = pygame.display.get_wm_info().get("window")
        if not hwnd:
            return (16, 39)

        class RECT(ctypes.Structure):
            _fields_ = [
                ("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long),
            ]

        outer = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(outer))
        win_w = outer.r - outer.l
        win_h = outer.b - outer.t
        surf_w, surf_h = pygame.display.get_surface().get_size()
        return (max(0, win_w - surf_w), max(0, win_h - surf_h))
    except Exception:
        return (16, 39)


def center_window(surface: pygame.Surface, fullscreen: bool = False) -> None:
    """Centraliza a janela na area de trabalho.

    O Windows posiciona a janela onde ela estava quando recreate, e o
    offset vai acumulando a cada troca de tamanho. Sem recentralizar, a
    janela sai da tela pela direita e por baixo: a segunda troca
    media endedava em 2090x1360 num desktop de 1920x1200, e parte do
    menu ficava fora do alcance do mouse.

    Em tela cheia nao ha o que centralizar: a janela ja cobre a tela
    toda. Mover ela com SetWindowPos e perda de tempo, e em alguns
    drivers mexe no modo exclusivo.
    """
    if fullscreen:
        return
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return  # teste headless: nao existe janela de verdade

    try:
        import ctypes

        hwnd = pygame.display.get_wm_info().get("window")
        if not hwnd:
            return

        user32 = ctypes.windll.user32
        # area de trabalho, ja descontando a barra de tarefas
        class RECT(ctypes.Structure):
            _fields_ = [
                ("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long),
            ]

        work = RECT()
        if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):
            work = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(work))

        work_w = work.r - work.l
        work_h = work.b - work.t

        # a comparacao e com a janela DE FORA, nao com a superficie:
        # a moldura soma ~16px de lado e ~39px de altura, entao uma
        # superficie que cabe na tela pode virar uma janela estourada
        frame = measure_window_frame()
        outer_w = surface.get_width() + frame[0]
        outer_h = surface.get_height() + frame[1]

        if outer_w >= work_w or outer_h >= work_h:
            # maior que a area util: cola no canto, sem centralizar
            x, y = work.l, work.t
        else:
            x = work.l + (work_w - outer_w) // 2
            y = work.t + (work_h - outer_h) // 2

        # 0x0001 = SWP_NOSIZE, 0x0004 = SWP_NOZORDER, 0x0010 = SWP_NOACTIVATE
        user32.SetWindowPos(
            hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010
        )
    except Exception as exc:  # nunca derruba o jogo por centralizar
        print(f"[video] nao foi possivel centralizar a janela: {exc}")


def main(frame_limit: int | None = None) -> int:
    pygame.init()
    # log limpo a cada inicio: assim ele mostra so a sessao atual
    try:
        _LOG_PATH.unlink(missing_ok=True)
    except OSError:
        pass

    config = Config.load()
    assets.set_sprite_scale(config.sprite_scale)

    # teclas do jogador; o config pode sobrescrever os padroes
    controls = InputMap(config.bindings)

    window = create_window(config)
    pygame.display.set_caption(settings.GAME_TITLE)
    center_window(window, config.fullscreen)
    # medir a moldura depois da janela existir, e o que permite ao
    # filtro de resolucao oferecer o maior tamanho que cabe de verdade.
    # Em tela cheia a medicao devolve (0,0) e nao sobrescreve o cache.
    set_window_frame(measure_window_frame(config.fullscreen))
    # a janela inicial tambem entra no log. Sem isso o arquivo comeca
    # so na primeira troca, e nao da para dizer o que o jogo fez ao
    # abrir: um problema que so acontece na partida recem-inaugurada
    # ficava invisivel.
    _log(
        f"janela recriada: {window.get_size()} "
        f"moldura={measure_window_frame(config.fullscreen)} "
        f"fullscreen={config.fullscreen} cena=inicial"
    )
    # a resolucao pode ter vindo de um config salvo antes da moldura
    # ser conhecida; agora que ela e, revalida e recria se precisa
    if config.clamp().size != (window.get_width(), window.get_height()):
        window = create_window(config)
        center_window(window, config.fullscreen)
        set_window_frame(measure_window_frame(config.fullscreen))
        _log(
            f"janela recriada: {window.get_size()} "
            f"moldura={measure_window_frame(config.fullscreen)} "
            f"fullscreen={config.fullscreen} cena=inicial"
        )

    clock = pygame.time.Clock()
    refresh = native_refresh_rate()

    manager = SceneManager(window, config, controls)
    build_scene_manager(manager)
    manager.switch("title")

    running = True
    frames = 0
    while running:
        # sem limite: so devolve o tempo decorrido
        if config.fps_limit > 0:
            dt = clock.tick(config.fps_limit) / 1000.0
        else:
            dt = clock.tick() / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                if _TRACE:
                    print("[trace] QUIT")
            elif manager.active is not None:
                if _TRACE:
                    _log_event(manager, event)
                manager.active.handle_event(event)

        manager.update(dt)
        manager.draw()

        # o contador fica sempre ligado, sem opcao
        draw_fps(manager.window, clock.get_fps(), refresh, config.fps_limit)

        pygame.display.flip()
        running = manager.running

        frames += 1
        if frame_limit is not None and frames >= frame_limit:
            running = False

    config.save()
    pygame.quit()
    return 0


def draw_fps(
    surface: pygame.Surface,
    fps: float,
    refresh: int | None,
    limit: int,
) -> None:
    """Descontra o FPS no canto superior direito.

    Uma linha so. A resolucao nao entra aqui: o titulo da janela ja
    mostra o tamanho, e repetir na tela so polui. O contador e sempre
    visivel, nao existe opcao de ligar e desligar.
    """
    text = f"{fps:5.1f} fps"
    if refresh:
        text += f"  {refresh}Hz"
    if limit:
        text += f" / {limit}"

    font = assets.get_font(18)
    rendered = font.render(text, True, settings.COLOR_TEXT_DIM)
    box = rendered.get_rect()
    box.inflate_ip(14, 6)
    box.topright = (surface.get_width() - 4, 4)
    surface.fill(settings.COLOR_PANEL, box)
    surface.blit(rendered, rendered.get_rect(center=box.center))


if __name__ == "__main__":
    sys.exit(main())
