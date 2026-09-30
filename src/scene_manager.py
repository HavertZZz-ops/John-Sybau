"""Gerenciador de cenas: mantém a cena ativa e faz a troca entre elas."""
from __future__ import annotations

from typing import Dict, Type

import pygame

from .input_map import InputMap
from .scene import Scene


class SceneManager:
    """Pilha simples de cenas com troca instantanea."""

    def __init__(self, window: pygame.Surface, config=None, controls=None) -> None:
        self.window = window
        self.config = config
        # mapa de teclas compartilhado por todas as cenas
        self.controls: InputMap = controls if controls is not None else InputMap()
        # estado de UI que precisa sobreviver a troca de cena; a cena em si
        # e recriada toda vez que entra
        self.ui_state: Dict[str, object] = {}
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
        from .main import center_window, create_window

        assets.set_sprite_scale(self.config.sprite_scale)

        if not rebuild:
            return

        self.window = create_window(self.config)
        import pygame

        pygame.display.set_caption("John Sybau")
        # centralizar toda vez: sem isso o offset da posicao antiga
        # acumula a cada troca e a janela sai da tela. Em tela cheia
        # nao ha janela para centralizar.
        center_window(self.window, self.config.fullscreen)

        from .main import _log, measure_window_frame, set_window_frame

        # o modo vem junto: medir a moldura em tela cheia leria o espaco
        # da escala em vez da borda e corromperia o filtro de resolucao
        moldura = measure_window_frame(self.config.fullscreen)
        set_window_frame(moldura)
        _log(
            f"janela recriada: {self.window.get_size()} "
            f"moldura={moldura} fullscreen={self.config.fullscreen} "
            f"cena={self._active_name}"
        )

        if self._active_name is not None:
            # o cursor e a aba sobreviveram a recriacao da janela
            self._active.save_ui_state()
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

    @property
    def active_name(self) -> str | None:
        """Nome da cena ativa, util para depurar e testar."""
        return self._active_name

    def switch(self, name: str) -> None:
        """Ativa a cena registrada com o nome informado."""
        if name not in self._scenes:
            raise KeyError(f"cena nao registrada: {name!r}")

        if self._active is not None:
            self._active.on_exit()

        self._active = self._scenes[name](self)
        self._active_name = name
        self._active.on_enter()

    def iniciar_novo_jogo(self, save=None) -> None:
        """Comeca (ou continua) uma partida na masmorra.

        `save` None e um jogo novo: a abertura pelo caixao roda inteira.
        Com um save, a cena entra direto com o jogador onde ele parou,
        sem repetir a introducao. `save` e pego pela assinatura de um
        `saves.Save`, importado aqui para nao criar ciclo no topo.
        """
        self.ui_state["save_carregado"] = save
        self.switch("dungeon")

    def iniciar_combate(self, inimigos: int = 1) -> None:
        """Abre a luta com `inimigos` esqueletos."""
        self.ui_state["inimigos"] = max(1, int(inimigos))
        self.switch("combat")

    def salvar_progresso(self) -> bool:
        """Grava o estado da cena ativa, se ela souber se descrever.

        Quem decide o que entra no save e a propria cena: o gerenciador
        nao sabe o que e "posicao" em cada uma delas.
        """
        from . import saves

        if self._active is None:
            return False
        montar = getattr(self._active, "para_save", None)
        if montar is None:
            return False
        dados = montar()
        if dados is None:
            return False
        store = self.ui_state.get("store") or saves.escolher_store()
        self.ui_state["store"] = store
        return store.salvar(dados)

    def update(self, dt: float) -> None:
        if self._active is not None:
            self._active.update(dt)

    def draw(self) -> None:
        if self._active is not None:
            self._active.draw(self.window)
