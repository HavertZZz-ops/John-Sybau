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

    Tenta primeiro SCALED, que permite resolucoes maiores que a tela e
    respeita o DPI. Se o driver nao conseguir, cai para o modo comum,
    porque perder SCALED e melhor do que nao abrir janela.
    """
    # SCALED exige aceleracao. Em driver virtual (teste headless) ela
    # nao existe, e o proprio pygame avisa "no fast renderer available".
    headless = os.environ.get("SDL_VIDEODRIVER") == "dummy"

    if not headless:
        flags = pygame.SCALED
        if config.fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            return pygame.display.set_mode(config.size, flags, vsync=1 if config.vsync else 0)
        except pygame.error as exc:
            print(f"[video] SCALED indisponivel ({exc}), usando modo padrao")
    else:
        flags = pygame.FULLSCREEN if config.fullscreen else 0

    return pygame.display.set_mode(config.size, flags)


def main(frame_limit: int | None = None) -> int:
    pygame.init()

    config = Config.load()
    assets.set_sprite_scale(config.sprite_scale)

    window = create_window(config)
    pygame.display.set_caption(settings.GAME_TITLE)

    clock = pygame.time.Clock()
    refresh = native_refresh_rate()

    manager = SceneManager(window, config)
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
