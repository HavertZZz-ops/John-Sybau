"""Tela de opcoes: video (resolucao, tela cheia, vsync, FPS) e teclas.

A tela tem duas abas. As mudancas de video entram em vigor na hora; as
de tecla pedem que o jogador aperte a tecla nova, e o jogo espera o
`enter` ser solto antes de gravar, senao o proprio `enter` que abriu a
captura viraria a tecla gravada.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import pygame

from . import assets, input_map, settings
from .config import RESOLUTION_CHOICES, Config, logical_desktop_size
from .input_map import InputMap
from .scene import Scene
from .ui import draw_panel, draw_text

PANEL_W = 560
ROW_H = 42
TABS_H = 40
MENU_H = 44

# teclas que cancelam a captura sem gravar
CANCEL_KEY = pygame.K_ESCAPE
# teclas de confirmacao dentro da propria tela de opcoes
SAVE_KEY = pygame.K_RETURN
RESET_KEY = pygame.K_r


def _fps_label(value: int) -> str:
    return "sem limite" if value == 0 else f"{value}"


class Option:
    """Linha de opcao: rotulo, valor atual e como alterar."""

    def __init__(
        self,
        key: str,
        label: str,
        read: Callable[[], str],
        adjust: Callable[[int], bool],
        hint: str = "",
    ) -> None:
        self.key = key
        self.label = label
        self.read = read
        self.adjust = adjust
        self.hint = hint


class OptionsScreen(Scene):
    """Menu de configuracoes, com abas de video e de teclas."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.config: Config = manager.config
        self.controls = manager.controls
        # a aba e a linha escolhidas vivem no manager, nao aqui: esta
        # cena e recriada a cada entrada, e o menu precisa continuar
        # onde o jogador parou
        saved = manager.ui_state.setdefault(
            "options", {"group": input_map.GROUP_VIDEO, "index": 0, "slot": 0}
        )
        self.group = str(saved.get("group", input_map.GROUP_VIDEO))
        self.index = int(saved.get("index", 0))  # type: ignore[arg-type]
        self.slot = int(saved.get("slot", 0))  # type: ignore[arg-type]
        self.notice: str | None = None
        self.notice_timer = 0.0
        self._needs_rebuild = False

        # captura de tecla: enquanto True, o proximo KEYDOWN e gravado
        self._capturing: Optional[str] = None
        self._awaiting_release = False
        self._capture_msg = ""

        self.options: List[Option] = self._build_video()
        self.rows: List[Tuple[str, str, list[str]]] = []

    def _resolution_hint(self) -> str:
        """Explica por que so algumas resolucoes aparecem."""
        desktop = logical_desktop_size()
        if not desktop:
            return "esquerda/direita"
        total = len(RESOLUTION_CHOICES)
        shown = len(self.config.available_resolutions())
        if shown >= total:
            return "esquerda/direita"
        return (
            f"sua tela e {desktop[0]}x{desktop[1]}; "
            f"resolucoes maiores ficariam cortadas"
        )

    # --- construcao das linhas -------------------------------------
    def _build_video(self) -> List[Option]:
        config = self.config

        def set_resolution(delta: int) -> bool:
            config.cycle_resolution(delta)
            return True  # recria a janela

        def set_scale(delta: int) -> bool:
            config.cycle_scale(delta)
            assets.set_sprite_scale(config.sprite_scale)
            return True

        def set_fps(delta: int) -> bool:
            config.cycle_fps(delta)
            return False

        def toggle(name: str) -> Callable[[int], bool]:
            def inner(delta: int) -> bool:
                config.toggle(name)
                return name == "fullscreen"

            return inner

        return [
            Option(
                "resolucao", "Resolucao",
                lambda: f"{config.width} x {config.height}",
                set_resolution,
                hint=self._resolution_hint(),
            ),
            Option(
                "escala", "Escala dos sprites",
                lambda: f"{config.sprite_scale}x",
                set_scale, hint="esquerda/direita",
            ),
            Option(
                "fps", "Limite de FPS",
                lambda: _fps_label(config.fps_limit),
                set_fps, hint="esquerda/direita",
            ),
            Option("fullscreen", "Tela cheia",
                   lambda: "sim" if config.fullscreen else "nao",
                   toggle("fullscreen"), hint="enter para alternar"),
            Option("vsync", "Vsync",
                   lambda: "sim" if config.vsync else "nao",
                   toggle("vsync"),
                   hint="reduz rasgo de imagem; recria a janela"),
            Option("show_fps", "Mostrar FPS",
                   lambda: "sim" if config.show_fps else "nao",
                   toggle("show_fps"), hint="enter para alternar"),
        ]

    def _build_keys(self) -> None:
        """Lista de (acao, rotulo, teclas) da aba de teclas."""
        self.rows = [
            (action, input_map.ACTION_LABELS[action], self.controls.keys(action))
            for action in input_map.actions_in(input_map.GROUP_TECLAS)
        ]

    def _current_count(self) -> int:
        return len(self.options) if self.group == input_map.GROUP_VIDEO else len(self.rows)

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        self.options = self._build_video()
        self._build_keys()
        self.index = min(self.index, max(0, self._current_count() - 1))
        self._capturing = None
        self._awaiting_release = False

    def on_exit(self) -> None:
        self.manager.ui_state["options"] = {
            "group": self.group,
            "index": self.index,
            "slot": self.slot,
        }

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP and self._awaiting_release:
            self._awaiting_release = False
            return

        if event.type != pygame.KEYDOWN:
            return

        # captura tem prioridade sobre tudo
        if self._capturing is not None:
            self._handle_capture(event)
            return

        up = self.controls.pressed(event.key, "mover_cima")
        down = self.controls.pressed(event.key, "mover_baixo")
        left = self.controls.pressed(event.key, "mover_esquerda")
        right = self.controls.pressed(event.key, "mover_direita")
        confirm = self.controls.pressed(event.key, "confirmar")
        back = self.controls.pressed(event.key, "voltar")
        restore = self.controls.pressed(event.key, "restaurar")

        if self.group == input_map.GROUP_TECLAS:
            # TAB troca de aba, sem depender das teclas remapeaveis
            if event.key == pygame.K_TAB:
                self._switch_tab()
                return
            if up:
                self._move(-1)
            elif down:
                self._move(1)
            elif left:
                self.slot = max(0, self.slot - 1)
            elif right:
                self.slot = min(2, self.slot + 1)
            elif confirm:
                self._start_capture()
            elif event.key == pygame.K_BACKSPACE:
                self._clear_slot()
            elif back:
                self._apply()
                self.manager.switch("title")
            elif restore:
                self._reset_keys()
            return

        if event.key == pygame.K_TAB:
            self._switch_tab()
        elif up:
            self._move(-1)
        elif down:
            self._move(1)
        elif left:
            self._adjust(-1)
        elif right:
            self._adjust(1)
        elif confirm:
            self._adjust(1)
        elif restore:
            self._reset()
        elif back:
            self._apply()
            self.manager.switch("title")

    def _switch_tab(self) -> None:
        self.group = (
            input_map.GROUP_TECLAS
            if self.group == input_map.GROUP_VIDEO
            else input_map.GROUP_VIDEO
        )
        self.index = 0
        self.slot = 0

    def _move(self, delta: int) -> None:
        count = self._current_count()
        if count:
            self.index = (self.index + delta) % count

    # --- aba de video ----------------------------------------------
    def _adjust(self, delta: int) -> None:
        if self.group != input_map.GROUP_VIDEO or not self.options:
            return
        option = self.options[self.index]
        if option.adjust(delta):
            self._needs_rebuild = True
            self._apply()

    def _reset(self) -> None:
        fresh = Config().clamp()
        self.config.copy_from(fresh)
        self.controls.reset()
        self._build_keys()
        assets.set_sprite_scale(self.config.sprite_scale)
        self._needs_rebuild = True
        self.options = self._build_video()
        self._apply()  # _apply sincroniza config.bindings a partir do mapa
        self._show("padroes restaurados")

    # --- aba de teclas ---------------------------------------------
    def _current_action(self) -> Optional[str]:
        if self.group != input_map.GROUP_TECLAS or self.index >= len(self.rows):
            return None
        return self.rows[self.index][0]

    def _start_capture(self) -> None:
        action = self._current_action()
        if action is None:
            return
        self._capturing = action
        # espera soltar o enter: se gravasse no KEYDOWN, o proprio
        # enter que abriu a captura viraria a tecla gravada
        self._awaiting_release = True
        self._capture_msg = "solte a tecla para confirmar"

    def _handle_capture(self, event: pygame.event.Event) -> None:
        # ESC cancela em qualquer momento da captura
        if event.key == CANCEL_KEY and not self._awaiting_release:
            action = self._capturing
            self._capturing = None
            self._show("captura cancelada" if action else "")
            return

        if self._awaiting_release:
            return

        action = self._capturing
        self._capturing = None
        if action is None:
            return

        if not input_map.is_bindable(event.key):
            self._show("essa tecla nao pode ser usada")
            return

        name = pygame.key.name(event.key)
        shared = [a for a in self.controls.conflicts(name) if a != action]
        self.controls.assign(action, self.slot, name)
        self._build_keys()
        self._apply()

        if shared:
            nomes = ", ".join(input_map.ACTION_LABELS.get(a, a) for a in shared)
            self._show(f"'{name}' tambem usada em: {nomes}")
        else:
            self._show(f"'{name}' gravada")

    def _clear_slot(self) -> None:
        action = self._current_action()
        if action is None:
            return
        if self.controls.clear_slot(action, self.slot):
            self._build_keys()
            self._apply()
            self._show("tecla removida")
        else:
            self._show("cada acao precisa de ao menos uma tecla")

    def _reset_keys(self) -> None:
        action = self._current_action()
        if action is not None:
            self.controls.reset_action(action)
            self._show(f"{input_map.ACTION_LABELS[action]} restaurada")
        else:
            self.controls.reset()
            self._show("todas as teclas restauradas")
        self._build_keys()
        self._apply()

    # --- aplicacao -------------------------------------------------
    def _apply(self) -> None:
        """Salva e, se preciso, recria a janela.

        O `InputMap` vivo e o `config.bindings` sao coisas separadas: o
        remapeamento acontece no mapa, e o arquivo guarda o dicionario.
        Sem copiar um no outro aqui, a tela mostra a tecla nova mas o
        config.json continua vazio e o remapeamento se perde ao fechar
        o jogo.
        """
        self.config.sync_from_input_map(self.controls)
        self.config.save()
        self.manager.apply_config(rebuild=self._needs_rebuild)
        self._needs_rebuild = False
        if self.manager.window.get_size() != self.size:
            self.options = self._build_video()
        self._show("configuracoes salvas")

    def _show(self, message: str) -> None:
        self.notice = message or None
        self.notice_timer = 2.5

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        if self.notice_timer > 0.0:
            self.notice_timer -= dt
            if self.notice_timer <= 0.0:
                self.notice = None

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLOR_BACKGROUND)
        w, h = self.size
        center_x = w // 2

        draw_text(surface, "OPCOES", 40, (center_x, 44), settings.COLOR_ACCENT)
        self._draw_tabs(surface, center_x)
        self._draw_panel(surface, center_x)
        self._draw_hint(surface, center_x, h)

    def _draw_tabs(self, surface: pygame.Surface, center_x: int) -> None:
        tabs = (("Video", input_map.GROUP_VIDEO), ("Teclas", input_map.GROUP_TECLAS))
        width = 150
        x = center_x - width
        for label, group in tabs:
            rect = pygame.Rect(x, 74, width - 8, TABS_H - 8)
            active = group == self.group
            draw_panel(
                surface,
                rect,
                color=settings.COLOR_PANEL_LIGHT if active else settings.COLOR_PANEL,
                border_color=settings.COLOR_ACCENT if active else settings.COLOR_PANEL_LIGHT,
                border_width=2,
            )
            draw_text(
                surface, label, 22, rect.center,
                settings.COLOR_ACCENT if active else settings.COLOR_TEXT_DIM,
            )
            x += width

    def _draw_panel(self, surface: pygame.Surface, center_x: int) -> None:
        if self.group == input_map.GROUP_VIDEO:
            self._draw_video_rows(surface, center_x)
        else:
            self._draw_key_rows(surface, center_x)

    def _draw_video_rows(self, surface: pygame.Surface, center_x: int) -> None:
        rows = self.options
        panel = self._panel_rect(len(rows))
        draw_panel(
            surface, panel, color=settings.COLOR_PANEL,
            border_color=settings.COLOR_PANEL_LIGHT,
        )

        y = panel.top + 14
        for i, option in enumerate(rows):
            selected = i == self.index
            if selected:
                row_rect = pygame.Rect(panel.left + 8, y - 2, panel.width - 16, ROW_H - 4)
                draw_panel(surface, row_rect, color=settings.COLOR_PANEL_LIGHT, radius=4)

            color = settings.COLOR_ACCENT if selected else settings.COLOR_TEXT
            draw_text(surface, option.label, 22, (panel.left + 34, y + ROW_H // 2 - 2), color, center=False)
            value = option.read()
            draw_text(
                surface, f"< {value} >" if selected else value, 22,
                (panel.right - 34, y + ROW_H // 2 - 2), color, center=False,
            )
            y += ROW_H

        self._draw_menu(surface, panel, "enter  salvar      R  restaurar padroes      esc  voltar")

    def _panel_rect(self, count: int) -> pygame.Rect:
        """Retangulo do painel, dimensionado para caber na janela.

        A altura vem do numero de linhas, mas nao pode passar da faixa
        disponivel: com 9 acoes, um painel alto demais cobria o rodape
        e a dica embaixo dele.
        """
        wanted = count * ROW_H + MENU_H + 28
        w, h = self.size
        available = int(h * 0.62)  # entre o titulo e a dica
        panel = pygame.Rect(0, 124, PANEL_W, min(wanted, available))
        panel.centerx = w // 2
        return panel

    def _draw_key_rows(self, surface: pygame.Surface, center_x: int) -> None:
        rows = self.rows
        slot_w = 92
        panel_w = max(PANEL_W, 420)
        panel = self._panel_rect(len(rows))
        panel.width = panel_w
        draw_panel(
            surface, panel, color=settings.COLOR_PANEL,
            border_color=settings.COLOR_PANEL_LIGHT,
        )

        # com o painel apertado, a linha encolhe para caber
        inner = panel.height - MENU_H - 28
        row_h = max(24, min(ROW_H, inner // max(1, len(rows))))

        y = panel.top + 14
        for i, (action, label, keys) in enumerate(rows):
            selected = i == self.index
            if selected:
                row_rect = pygame.Rect(panel.left + 8, y - 2, panel.width - 16, row_h - 4)
                draw_panel(surface, row_rect, color=settings.COLOR_PANEL_LIGHT, radius=4)

            color = settings.COLOR_ACCENT if selected else settings.COLOR_TEXT
            font_size = 22 if row_h >= 34 else 19
            draw_text(surface, label, font_size, (panel.left + 34, y + row_h // 2 - 2), color, center=False)

            # ate tres slots de tecla por acao
            cell_h = max(14, row_h - 12)
            for slot in range(3):
                sx = panel.right - 40 - (2 - slot) * slot_w
                cell = pygame.Rect(sx - slot_w // 2, y + 6, slot_w - 8, cell_h)
                active = selected and slot == self.slot
                draw_panel(
                    surface, cell,
                    color=settings.COLOR_PANEL if not active else settings.COLOR_BACKGROUND,
                    border_color=settings.COLOR_ACCENT if active else settings.COLOR_PANEL_LIGHT,
                    border_width=2, radius=4,
                )
                name = keys[slot] if slot < len(keys) else ""
                texto = (
                    input_map.key_name(code)
                    if (code := input_map.key_code(name))
                    else "--"
                )
                draw_text(surface, texto, 18, cell.center, color if name else settings.COLOR_TEXT_DIM)
            y += row_h

        self._draw_menu(
            surface, panel,
            "enter  gravar      backspace  remover      R  restaurar      esc  voltar",
        )

    def _draw_menu(self, surface: pygame.Surface, panel: pygame.Rect, text: str) -> None:
        draw_text(surface, text, 17, (panel.centerx, panel.bottom - MENU_H // 2 - 6), settings.COLOR_TEXT_DIM)

    def _draw_hint(self, surface: pygame.Surface, center_x: int, height: int) -> None:
        # a dica fica logo abaixo do painel, nunca numa posicao fixa
        # que o painel pudesse cobrir
        panel_bottom = self._panel_rect(self._current_count()).bottom
        y = panel_bottom + 30

        if self._capturing is not None:
            label = input_map.ACTION_LABELS.get(self._capturing, self._capturing)
            if self._awaiting_release:
                msg = f"{label}: solte a tecla atual"
            else:
                msg = f"{label}: aperte a tecla nova  (esc cancela)"
            draw_text(surface, msg, 24, (center_x, y), settings.COLOR_ACCENT)
        else:
            hint = self._hint_text()
            if hint:
                draw_text(surface, hint, 17, (center_x, y), (110, 104, 126))

        draw_text(
            surface, "TAB  troca de aba", 17,
            (center_x, y + 28), (110, 104, 126),
        )

        if self.notice:
            draw_text(surface, self.notice, 21, (center_x, y + 58), settings.COLOR_ACCENT)

    def _hint_text(self) -> str:
        if self.group == input_map.GROUP_VIDEO:
            if self.options and self.index < len(self.options):
                return self.options[self.index].hint
            return ""

        action = self._current_action()
        if action is None:
            return ""
        keys = self.controls.keys(action)
        if not keys:
            return ""
        name = keys[min(self.slot, len(keys) - 1)] if keys else ""
        shared = [a for a in self.controls.conflicts(name) if a != action] if name else []
        if shared:
            nomes = ", ".join(input_map.ACTION_LABELS.get(a, a) for a in shared)
            return f"esta tecla tambem esta em: {nomes}"
        return "enter grava no slot selecionado; setas trocam o slot"
