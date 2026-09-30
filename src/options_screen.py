"""Tela de configuracoes: video (resolucao, tela cheia, vsync, escala, FPS)
e teclas.

Duas decisoes importantes:

1. A navegacao desta tela NAO usa o mapa de teclas do jogador. Setas,
   WASD, enter e esc sao sempre as mesmas coisas aqui. Se a navegacao
   usasse as teclas remapeadas, trocar a tecla de "voltar" deixaria o
   jogador preso nesta tela sem como sair.

2. Tudo funciona com o mouse tambem. Setar opcoes e um trabalho de
   cliques, e ficar so no teclado atrapalha.

As mudancas de video entram em vigor na hora. Para gravar uma tecla, o
jogo espera a tecla de confirmacao ser solta antes de aceitar a nova,
senao o proprio enter que abriu a captura viraria a tecla gravada.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import pygame

from . import assets, input_map, settings
from .config import RESOLUTION_CHOICES, Config, logical_desktop_size, native_refresh_rate
from .input_map import InputMap
from .scene import Scene
from .ui import draw_panel, draw_text

# teclas fixas desta tela: nao vem do mapa do jogador, para nunca ficar
# sem como navegar
NAV_UP = (pygame.K_UP, pygame.K_w)
NAV_DOWN = (pygame.K_DOWN, pygame.K_s)
NAV_LEFT = (pygame.K_LEFT, pygame.K_a)
NAV_RIGHT = (pygame.K_RIGHT, pygame.K_d)
NAV_CONFIRM = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
NAV_BACK = (pygame.K_ESCAPE,)
NAV_CLEAR = (pygame.K_BACKSPACE, pygame.K_DELETE)
NAV_RESET = (pygame.K_r,)

SLOTS_PER_ACTION = 3
MIN_PANEL_W = 520
ROW_GAP = 6


def _fps_label(value: int) -> str:
    return "sem limite" if value == 0 else str(value)


class Option:
    """Linha de opcao: rotulo, valor atual, e como alterar."""

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
        self.controls: InputMap = manager.controls
        self.group = input_map.GROUP_VIDEO
        self.index = 0
        self.slot = 0

        self.notice: str | None = None
        self.notice_timer = 0.0
        self._needs_rebuild = False

        self._capturing: Optional[str] = None
        self._awaiting_release = False

        self.options: List[Option] = self._build_video()
        self.rows: List[Tuple[str, str, list[str]]] = []
        # caixas desenhadas no ultimo frame, para o clique acertar
        self._hit_video: List[pygame.Rect] = []
        self._hit_tabs: List[Tuple[pygame.Rect, str]] = []
        self._hit_slots: List[pygame.Rect] = []

    # --- construcao das linhas -------------------------------------
    def _resolution_hint(self) -> str:
        desktop = logical_desktop_size()
        if not desktop:
            return "esquerda/direita"
        offered = len(self.config.available_resolutions())
        if offered >= len(RESOLUTION_CHOICES):
            return "esquerda/direita"
        return (
            f"sua tela e {desktop[0]}x{desktop[1]}; "
            f"resolucoes maiores ficariam cortadas"
        )

    def _build_video(self) -> List[Option]:
        config = self.config
        refresh = native_refresh_rate()

        def set_resolution(delta: int) -> bool:
            config.cycle_resolution(delta)
            return True

        def set_scale(delta: int) -> bool:
            config.cycle_scale(delta)
            assets.set_sprite_scale(config.sprite_scale)
            return False

        def set_fps(delta: int) -> bool:
            config.cycle_fps(delta)
            return False

        def toggle(name: str) -> Callable[[int], bool]:
            def inner(delta: int) -> bool:
                config.toggle(name)
                return name == "fullscreen"

            return inner

        vsync_hint = "liga o travamento com o monitor; evita rasgo"
        if refresh:
            vsync_hint += f" (seu monitor: {refresh}Hz)"

        return [
            Option(
                "resolucao", "Resolucao",
                lambda: f"{config.width} x {config.height}",
                set_resolution, hint=self._resolution_hint(),
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
            Option(
                "fullscreen", "Tela cheia",
                lambda: "sim" if config.fullscreen else "nao",
                toggle("fullscreen"), hint="enter para alternar",
            ),
            Option(
                "vsync", "Vsync",
                lambda: "sim" if config.vsync else "nao",
                toggle("vsync"), hint=vsync_hint,
            ),
        ]

    def _build_keys(self) -> None:
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
        self.slot = min(self.slot, SLOTS_PER_ACTION - 1)
        self._capturing = None
        self._awaiting_release = False

    # --- layout ----------------------------------------------------
    def _layout(self) -> dict:
        """Medidas do painel, derivadas do tamanho da janela."""
        w, h = self.size
        count = max(1, self._current_count())

        # o painel e sempre centralizado e nunca mais largo que a tela
        max_w = int(w * 0.92)
        min_w = min(MIN_PANEL_W, max_w)
        if self.group == input_map.GROUP_TECLAS:
            # 3 slots + rotulo: precisa de mais espaco que a aba de video
            ideal = int(w * 0.62)
        else:
            ideal = int(w * 0.42)
        panel_w = max(min_w, min(ideal, max_w))

        top = int(h * 0.20)
        bottom_reserved = int(h * 0.16)
        available = max(120, h - top - bottom_reserved)
        row_h = max(24, min(44, (available - 40) // count))
        panel_h = row_h * count + 40

        # o painel e centralizado no espaco entre as abas e o rodape,
        # para nao ficar colado no titulo com a tela toda vazia embaixo
        space_top = int(h * 0.18)
        space_bottom = int(h * 0.18)
        center_y = (space_top + (h - space_bottom)) // 2

        panel = pygame.Rect(0, center_y - panel_h // 2, panel_w, panel_h)
        panel.centerx = w // 2

        return {"panel": panel, "row_h": row_h, "row_top": panel.top + 14}

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP and self._awaiting_release:
            self._awaiting_release = False
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
            return

        if event.type != pygame.KEYDOWN:
            return

        if self._capturing is not None:
            self._handle_capture(event)
            return

        key = event.key
        if key in NAV_CONFIRM:
            self._activate()
        elif key in NAV_UP:
            self._move(-1)
        elif key in NAV_DOWN:
            self._move(1)
        elif key in NAV_LEFT:
            self._left()
        elif key in NAV_RIGHT:
            self._right()
        elif key in NAV_CLEAR:
            if self.group == input_map.GROUP_TECLAS:
                self._clear_slot()
        elif key in NAV_RESET:
            if self.group == input_map.GROUP_TECLAS:
                self._reset_action()
            else:
                self._reset_all()
        elif key in NAV_BACK:
            self._apply()
            self.manager.switch("title")
        elif key == pygame.K_TAB:
            self._switch_tab()

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

    def _left(self) -> None:
        if self.group == input_map.GROUP_TECLAS:
            self.slot = max(0, self.slot - 1)
        else:
            self._adjust(-1)

    def _right(self) -> None:
        if self.group == input_map.GROUP_TECLAS:
            self.slot = min(SLOTS_PER_ACTION - 1, self.slot + 1)
        else:
            self._adjust(1)

    def _click(self, pos: Tuple[int, int]) -> None:
        for rect, group in self._hit_tabs:
            if rect.collidepoint(pos):
                if group != self.group:
                    self._switch_tab()
                return

        if self.group == input_map.GROUP_VIDEO:
            for i, rect in enumerate(self._hit_video):
                if rect.collidepoint(pos):
                    if i == self.index:
                        self._adjust(1)
                    else:
                        self.index = i
                    return
            return

        for i, rect in enumerate(self._hit_slots):
            if not rect.collidepoint(pos):
                continue
            row, slot = divmod(i, SLOTS_PER_ACTION)
            if row != self.index or slot != self.slot:
                self.index, self.slot = row, slot
                return
            self._activate()
            return

        # clique na linha, fora das caixas: so move a selecao
        for i, rect in enumerate(self._hit_video):
            if rect.collidepoint(pos):
                self.index = i
                return

    def _activate(self) -> None:
        if self.group == input_map.GROUP_VIDEO:
            self._adjust(1)
        else:
            self._start_capture()

    # --- aba de video ----------------------------------------------
    def _adjust(self, delta: int) -> None:
        if not self.options:
            return
        option = self.options[self.index]
        if option.adjust(delta):
            self._needs_rebuild = True
            self._apply(silent=True)
        else:
            self._apply(silent=True)
        self._show(f"{option.label}: {option.read()}")

    def _reset_all(self) -> None:
        fresh = Config().clamp()
        self.config.copy_from(fresh)
        self.controls.reset()
        self._build_keys()
        assets.set_sprite_scale(self.config.sprite_scale)
        self._needs_rebuild = True
        self.options = self._build_video()
        self.index = 0
        self._apply()
        self._show("tudo restaurado para o padrao")

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
        # espera soltar a tecla: sem isso, o enter que abriu a captura
        # seria gravado como a tecla nova
        self._awaiting_release = True

    def _handle_capture(self, event: pygame.event.Event) -> None:
        if self._awaiting_release:
            return

        action = self._capturing
        self._capturing = None
        if action is None:
            return

        if event.key in NAV_BACK:
            self._show("captura cancelada")
            return
        if event.key in (pygame.K_TAB, pygame.K_LALT, pygame.K_RALT):
            self._show("essa tecla e reservada para navegar nesta tela")
            return
        if not input_map.is_bindable(event.key):
            self._show("essa tecla nao pode ser usada")
            return

        name = pygame.key.name(event.key)
        shared = [a for a in self.controls.conflicts(name) if a != action]
        self.controls.assign(action, self.slot, name)
        self._build_keys()
        self._apply(silent=True)

        label = input_map.ACTION_LABELS.get(action, action)
        if shared:
            nomes = ", ".join(input_map.ACTION_LABELS.get(a, a) for a in shared)
            self._show(f"{label}: '{name}'  (tambem em {nomes})")
        else:
            self._show(f"{label}: '{name}' gravada")

    def _clear_slot(self) -> None:
        action = self._current_action()
        if action is None:
            return
        label = input_map.ACTION_LABELS.get(action, action)
        if self.controls.clear_slot(action, self.slot):
            self._build_keys()
            self._apply(silent=True)
            self._show(f"{label}: slot {self.slot + 1} vazado")
        else:
            self._show("cada acao precisa de ao menos uma tecla")

    def _reset_action(self) -> None:
        action = self._current_action()
        if action is None:
            return
        self.controls.reset_action(action)
        self._build_keys()
        self._apply(silent=True)
        self._show(f"{input_map.ACTION_LABELS[action]} restaurada")

    # --- aplicacao -------------------------------------------------
    def _apply(self, silent: bool = False) -> None:
        """Salva e, se preciso, recria a janela.

        O `InputMap` vivo e o `config.bindings` sao coisas separadas: o
        remapeamento acontece no mapa, e o arquivo guarda o dicionario.
        Sem copiar um no outro aqui, a tela mostra a tecla nova mas o
        config.json continua vazio e o remapeamento se perde ao fechar.
        """
        self.config.sync_from_input_map(self.controls)
        self.config.save()
        self.manager.apply_config(rebuild=self._needs_rebuild)
        self._needs_rebuild = False
        if not silent:
            self._show("configuracoes salvas")

    def _show(self, message: str) -> None:
        self.notice = message or None
        self.notice_timer = 3.0

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

        draw_text(
            surface, "CONFIGURACOES", max(26, int(h * 0.055)),
            (center_x, int(h * 0.075)), settings.COLOR_ACCENT,
        )
        self._draw_tabs(surface, center_x)
        if self.group == input_map.GROUP_VIDEO:
            self._draw_video_rows(surface)
        else:
            self._draw_key_rows(surface)
        self._draw_footer(surface, center_x, h)

    def _draw_tabs(self, surface: pygame.Surface, center_x: int) -> None:
        tabs = (("Video", input_map.GROUP_VIDEO), ("Teclas", input_map.GROUP_TECLAS))
        width = 170
        height = max(26, int(self.size[1] * 0.042))
        x = center_x - width
        self._hit_tabs = []
        for label, group in tabs:
            rect = pygame.Rect(x, int(self.size[1] * 0.12), width - 10, height)
            active = group == self.group
            draw_panel(
                surface, rect,
                color=settings.COLOR_PANEL_LIGHT if active else settings.COLOR_PANEL,
                border_color=settings.COLOR_ACCENT if active else settings.COLOR_PANEL_LIGHT,
                border_width=2,
            )
            draw_text(
                surface, label, max(16, int(height * 0.5)), rect.center,
                settings.COLOR_ACCENT if active else settings.COLOR_TEXT_DIM,
            )
            self._hit_tabs.append((rect, group))
            x += width

    def _draw_video_rows(self, surface: pygame.Surface) -> None:
        rows = self.options
        lay = self._layout()
        panel = lay["panel"]
        row_h = lay["row_h"]
        font = max(16, int(row_h * 0.52))

        draw_panel(
            surface, panel, color=settings.COLOR_PANEL,
            border_color=settings.COLOR_PANEL_LIGHT,
        )

        y = lay["row_top"]
        self._hit_video = []
        for i, option in enumerate(rows):
            rect = pygame.Rect(panel.left + 10, y, panel.width - 20, row_h)
            self._hit_video.append(rect)
            selected = i == self.index
            if selected:
                draw_panel(surface, rect, color=settings.COLOR_PANEL_LIGHT, radius=4)

            color = settings.COLOR_ACCENT if selected else settings.COLOR_TEXT
            value = option.read()
            draw_text(surface, option.label, font, (rect.left + 12, rect.centery), color, center=False)
            draw_text(
                surface, f"< {value} >" if selected else value, font,
                (rect.right - 12, rect.centery), color, center=False,
            )
            y += row_h

    def _draw_key_rows(self, surface: pygame.Surface) -> None:
        rows = self.rows
        lay = self._layout()
        panel = lay["panel"]
        row_h = lay["row_h"]
        font = max(15, int(row_h * 0.5))
        slot_w = min(96, panel.width // 6)

        draw_panel(
            surface, panel, color=settings.COLOR_PANEL,
            border_color=settings.COLOR_PANEL_LIGHT,
        )

        y = lay["row_top"]
        self._hit_slots = []
        self._hit_video = []
        for i, (action, label, keys) in enumerate(rows):
            row_rect = pygame.Rect(panel.left + 10, y, panel.width - 20, row_h)
            self._hit_video.append(row_rect)
            selected = i == self.index
            if selected:
                draw_panel(surface, row_rect, color=settings.COLOR_PANEL_LIGHT, radius=4)

            color = settings.COLOR_ACCENT if selected else settings.COLOR_TEXT
            # o rotulo comeca depois do recuo, e nao colado na borda
            label_x = row_rect.left + 12
            draw_text(surface, label, font, (label_x, row_rect.centery), color, center=False)

            for slot in range(SLOTS_PER_ACTION):
                cell = pygame.Rect(
                    panel.right - 34 - (SLOTS_PER_ACTION - 1 - slot) * slot_w,
                    y + 3, slot_w - 8, row_h - 6,
                )
                self._hit_slots.append(cell)
                active = selected and slot == self.slot
                capturing = active and self._capturing is not None
                draw_panel(
                    surface, cell,
                    color=settings.COLOR_BACKGROUND if active else settings.COLOR_PANEL,
                    border_color=settings.COLOR_ACCENT if active else settings.COLOR_PANEL_LIGHT,
                    border_width=2, radius=4,
                )
                name = keys[slot] if slot < len(keys) else ""
                if capturing:
                    texto = "aperte" if not self._awaiting_release else "solte"
                elif name:
                    texto = input_map.key_name(code) if (code := input_map.key_code(name)) else name
                else:
                    texto = "--"
                draw_text(
                    surface, texto, max(13, font - 3), cell.center,
                    color if name or capturing else settings.COLOR_TEXT_DIM,
                )
            y += row_h

    def _draw_footer(self, surface: pygame.Surface, center_x: int, height: int) -> None:
        lay = self._layout()
        y = lay["panel"].bottom

        if self.group == input_map.GROUP_VIDEO:
            hint = "setas trocam o valor      enter  salvar      R  padroes      esc  voltar"
        else:
            hint = (
                "enter  gravar      backspace  limpar slot      "
                "R  restaurar acao      esc  voltar"
            )
        draw_text(surface, hint, max(13, int(height * 0.024)), (center_x, y + 22), settings.COLOR_TEXT_DIM)

        if self._capturing is not None:
            label = input_map.ACTION_LABELS.get(self._capturing, self._capturing)
            msg = (
                f"{label}: solte a tecla atual"
                if self._awaiting_release
                else f"{label}: aperte a tecla nova    (esc cancela)"
            )
            draw_text(surface, msg, max(18, int(height * 0.032)), (center_x, y + 52), settings.COLOR_ACCENT)
        elif self.notice:
            draw_text(surface, self.notice, max(15, int(height * 0.028)), (center_x, y + 52), settings.COLOR_ACCENT)

        draw_text(
            surface, "TAB  troca de aba      o mouse tambem funciona",
            max(12, int(height * 0.022)), (center_x, y + 80), (104, 98, 120),
        )
