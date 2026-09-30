"""Gerenciador de cenas: mantém a cena ativa e faz a troca entre elas."""
from __future__ import annotations

from typing import Callable, Dict, Type

import pygame

from .scene import Scene


class SceneManager:
    """Pilha simples de cenas com troca instantanea."""

    def __init__(self, window: pygame.Surface, config=None) -> None:
        self.window = window
        self.config = config
        self._scenes: Dict[str, Type[Scene]] = {}
        self._active: Scene | None = None
        self._active_name: str | None = None
        self._running = True

    def apply_config(self, rebuild: bool = False) -> None:
        """Aplica a configuracao e, se preciso, recria a janela.

        Quando a janela e recriada, a cena ativa e reconstruida para
        nao ficar com referencias da superficie antiga.
        """
        if self.config is None:
            return

        from . import assets
        from .main import create_window

        assets.set_sprite_scale(self.config.sprite_scale)

        if not rebuild:
            return

        self.window = create_window(self.config)
        import pygame

        pygame.display.set_caption("John Sybau")

        if self._active_name is not None:
            name = self._active_name
            self._active = None
            self.switch(name)

    @property
    def running(self) -> bool:
        """False depois que alguma cena pede para encerrar o jogo."""
        return self._running

    def quit(self) -> None:
        """Pede o encerramento do loop principal."""
        self._running = False

    def register(self, name: str, scene_class: Type[Scene]) -> None:
        """Registra uma classe de cena sob um nome."""
        self._scenes[name] = scene_class

    @property
    def active(self) -> Scene | None:
        return self._active

    def switch(self, name: str) -> None:
        """Ativa a cena registrada com o nome informado."""
        if name not in self._scenes:
            raise KeyError(f"cena nao registrada: {name!r}")

        if self._active is not None:
            self._active.on_exit()

        self._active = self._scenes[name](self)
        self._active_name = name
        self._active.on_enter()

    def update(self, dt: float) -> None:
        if self._active is not None:
            self._active.update(dt)

    def draw(self) -> None:
        if self._active is not None:
            self._active.draw(self.window)
