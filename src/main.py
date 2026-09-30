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
from .config import Config, native_refresh_rate
from .game_scene import GameScene
from .input_map import InputMap
from .options_screen import OptionsScreen
from .scene_manager import SceneManager
from .title_screen import TitleScreen


def build_scene_manager(manager: SceneManager) -> SceneManager:
    manager.register("title", TitleScreen)
    manager.register("options", OptionsScreen)
    manager.register("game", GameScene)
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
    """
    size = config.size

    # SCALED exige aceleracao. Em driver virtual (teste headless) ela
    # nao existe, e o proprio pygame avisa "no fast renderer available".
    headless = os.environ.get("SDL_VIDEODRIVER") == "dummy"

    if not headless:
        flags = pygame.SCALED
        if config.fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            return pygame.display.set_mode(
                size, flags, vsync=1 if config.vsync else 0
            )
        except pygame.error as exc:
            # SCALED|FULLSCREEN falha em alguns drivers; tenta sem vsync
            try:
                return pygame.display.set_mode(size, flags)
            except pygame.error:
                print(f"[video] SCALED indisponivel ({exc}), usando modo padrao")
    else:
        flags = pygame.FULLSCREEN if config.fullscreen else 0

    return pygame.display.set_mode(size, flags)


def main(frame_limit: int | None = None) -> int:
    pygame.init()

    config = Config.load()
    assets.set_sprite_scale(config.sprite_scale)

    # teclas do jogador; o config pode sobrescrever os padroes
    controls = InputMap(config.bindings)

    window = create_window(config)
    pygame.display.set_caption(settings.GAME_TITLE)

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
            elif manager.active is not None:
                manager.active.handle_event(event)

        manager.update(dt)
        manager.draw()

        if config.show_fps:
            draw_fps(
                manager.window, clock.get_fps(), refresh, config.fps_limit, config
            )

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
    config: Config,
) -> None:
    """Descontra FPS e resolucao no canto da tela.

    Mostrar a resolucao real da superficie responde a duvida mais
    comum nas opcoes: "mudei a resolucao, mas o jogo continua igual?".
    A janela e a superficie podem diferir em modo fullscreen, entao
    o que aparece e o que esta sendo desenhado agora.
    """
    width, height = surface.get_size()
    fps_line = f"{fps:5.1f} fps"
    if refresh:
        fps_line += f"  ({refresh}Hz)"
    if limit:
        fps_line += f"  / {limit}"

    res_line = f"{width} x {height}"
    if config.fullscreen:
        res_line += " (tela cheia)"

    lines = [fps_line, res_line]

    if config.fullscreen:
        lines[1] += " (tela cheia)"

    font = assets.get_font(18)
    height_px = len(lines) * 20 + 6
    box = pygame.Rect(0, 0, 0, 0)
    rendered = [font.render(line, True, settings.COLOR_TEXT_DIM) for line in lines]
    width_px = max(r.get_width() for r in rendered) + 16

    box.size = (width_px, height_px)
    box.topright = (surface.get_width() - 4, 4)
    surface.fill(settings.COLOR_PANEL, box)

    y = box.top + 3
    for item in rendered:
        surface.blit(item, item.get_rect(midleft=(box.left + 8, y + item.get_height() // 2)))
        y += 20


if __name__ == "__main__":
    sys.exit(main())
