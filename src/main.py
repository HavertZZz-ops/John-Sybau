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
from .config import Config, logical_desktop_size, native_refresh_rate
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
    """Cria (ou recria) a janela conforme a configuracao.

    Resolucao maior que a tela logica e rebaixada de imediato: abrir
    2560x1440 numa tela de 1536x960 cria uma janela que nao cabe, e
    sobra uma faixa em branco na direita e embaixo. Em tela cheia a
    resolucao escolhida e o que o monitor deve exibir, entao nao se
    mexe.

    SCALED permite resolucoes maiores que a tela, mas depende de
    aceleracao. Onde ela nao existe (driver virtual de teste), o pygame
    reclama e a janela nao abre, entao ha um caminho sem SCALED.
    """
    size = config.size
    desktop = logical_desktop_size()

    if not config.fullscreen and desktop:
        if size[0] > desktop[0] or size[1] > desktop[1]:
            # encolhe mantendo a proporcao, sem passar do desktop
            factor = min(desktop[0] / size[0], desktop[1] / size[1])
            size = (
                max(640, int(size[0] * factor)),
                max(360, int(size[1] * factor)),
            )
            config.width, config.height = size
            print(f"[video] resolucao maior que a tela; usando {size[0]}x{size[1]}")

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
    """Descontra o contador de FPS no canto da tela."""
    text = f"{fps:5.1f} fps"
    if refresh:
        text += f"  ({refresh}Hz)"
    if limit:
        text += f"  / {limit}"

    font = assets.get_font(18)
    rendered = font.render(text, True, settings.COLOR_TEXT_DIM)
    background = rendered.get_rect()
    background.inflate_ip(8, 4)
    background.topright = (surface.get_width() - 4, 4)
    surface.fill(settings.COLOR_PANEL, background)
    surface.blit(rendered, rendered.get_rect(center=background.center))


if __name__ == "__main__":
    sys.exit(main())
