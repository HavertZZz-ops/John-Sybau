"""Gerenciador de cenas: mantém a cena ativa e faz a troca entre elas."""
from __future__ import annotations

from typing import Callable, Dict, Type

import pygame

from .scene import Scene


class SceneManager:
    """Pilha simples de cenas com troca instantanea."""

    def __init__(self, window: pygame.Surface) -> None:
        self.window = window
        self._scenes: Dict[str, Type[Scene]] = {}
        self._active: Scene | None = None
        self._active_name: str | None = None

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
