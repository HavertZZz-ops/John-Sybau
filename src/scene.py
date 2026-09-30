"""Classe base para todas as cenas do jogo.

Uma cena e um "estado" do jogo (menu, jogo pausado, etc). Ela recebe
os eventos, atualiza a logica e desenha na tela. Trocar de cena e
feito pelo SceneManager.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:  # evita import circular em tempo de execucao
    from .scene_manager import SceneManager


class Scene:
    """Estado base do jogo."""

    def __init__(self, manager: "SceneManager") -> None:
        self.manager = manager
        self.window = manager.window

    @property
    def size(self) -> tuple[int, int]:
        """Tamanho atual da janela.

        Consulta a cada uso em vez de usar settings.SCREEN_WIDTH, porque
        a resolucao muda quando o jogador ajusta nas opcoes.
        """
        return self.window.get_size()

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        """Chamado uma vez quando a cena vira a ativa."""

    def on_exit(self) -> None:
        """Chamado uma vez quando a cena deixa de ser a ativa."""

    # atualizacao ---------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        """Processa um evento de entrada (teclado, mouse, etc)."""

    def update(self, dt: float) -> None:
        """Atualiza a logica. `dt` esta em segundos."""

    def draw(self, surface: pygame.Surface) -> None:
        """Desenha a cena na superficie informada."""
