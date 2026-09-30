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
        # mapa de teclas do jogador; cenas usam isto em vez de pygame.K_*
        self.controls = manager.controls

    def key(self, event: pygame.event.Event, action: str) -> bool:
        """True se o evento e a tecla da acao."""
        return self.controls.pressed(event.key, action)

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

    def save_ui_state(self) -> None:
        """Guarda no manager o estado de UI que deve sobreviver.

        Chamado antes de a cena ser recriada por causa de uma troca de
        janela (resolucao ou tela cheia). Sem isso, o jogador ajusta a
        resolucao e a cena volta com o cursor no topo da lista, longe
        da linha que ele acabou de mexer.
        """

    # atualizacao ---------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        """Processa um evento de entrada (teclado, mouse, etc)."""

    def update(self, dt: float) -> None:
        """Atualiza a logica. `dt` esta em segundos."""

    def draw(self, surface: pygame.Surface) -> None:
        """Desenha a cena na superficie informada."""
