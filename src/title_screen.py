"""Tela inicial do jogo: menu com o elenco e entrada nas cenas.

Nada aqui depende de sprites prontos: enquanto um PNG nao existir, o
cartao mostra um retangulo com o nome. O heroi tem animacao de idle
com 4 direcoes, controlada pelas teclas A e D.
"""
from __future__ import annotations

from typing import List, Tuple

import pygame

from . import assets, settings
from .scene import Scene
from .ui import draw_panel, draw_text

# (arquivo png, rotulo, texto curto dentro do placeholder)
CHARACTER_LABELS: Tuple[Tuple[str, str, str], ...] = (
    ("protagonista", "Protagonista", "PROTAG"),
    ("estranho", "Estranho", "ESTRANHO"),
    ("mulher_misteriosa", "Mulher misteriosa", "MULHER"),
    ("rei_mago", "Rei mago", "REI MAGO"),
)

MENU_ITEMS: Tuple[str, ...] = ("Iniciar jogo", "Opcoes", "Sair")

# tamanho do quadro do heroi como esta no disco (32x38), usado para
# descobrir qual escala de sprite cabe no cartao
HERO_BASE = (32, 38)


class MenuItem:
    """Item de menu com selecao por teclado."""

    def __init__(self, label: str, center: Tuple[int, int], width: int = 320) -> None:
        self.label = label
        self.center = center
        self.selected = False
        self.hovered = False
        self._rect = pygame.Rect(0, 0, width, 46)
        self._rect.center = center

    def place(self, center: Tuple[int, int]) -> None:
        """Reposiciona, para acompanhar mudanca de resolucao."""
        self.center = center
        self._rect.center = center

    @property
    def rect(self) -> pygame.Rect:
        return self._rect


class TitleScreen(Scene):
    """Menu principal com elenco de personagens."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.menu_index = 0
        self.time = 0.0
        self.notice: str | None = None
        self.notice_timer = 0.0

        self.hero_dir = "sul"
        self.hero_cycle = assets.HERO_DIRECTIONS
        self.hero_frames: list[pygame.Surface] = []
        self.hero_timer = 0.0
        self._hero_box = (78, 110)
        self._load_hero()

        self.menu: List[MenuItem] = [MenuItem(label, (0, 0)) for label in MENU_ITEMS]
        self._layout()

    # layout --------------------------------------------------------
    def _layout(self) -> None:
        """Posiciona o menu e o elenco conforme o tamanho da janela.

        Tudo e calculado em proporcao da altura, entao funciona nas
    resolucoes diferentes sem valores fixos.
        """
        width, height = self.size
        center_x = width // 2
        base_y = int(height * 0.70)
        for i, item in enumerate(self.menu):
            item.place((center_x, base_y + i * 56))

    def on_enter(self) -> None:
        self.menu_index = 0
        self._layout()
        self._sync_selection()

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
            return

        if event.type == pygame.KEYDOWN:
            if self.key(event, "mover_cima"):
                self._move(-1)
            elif self.key(event, "mover_baixo"):
                self._move(1)
            elif self.key(event, "confirmar"):
                self._activate()
            elif self.key(event, "girar_esquerda"):
                self._cycle_hero(-1)
            elif self.key(event, "girar_direita"):
                self._cycle_hero(1)
            elif self.key(event, "voltar"):
                self.manager.quit()

    def _click(self, pos: Tuple[int, int]) -> None:
        """Permite navegar e ativar com o mouse."""
        for i, item in enumerate(self.menu):
            if item.rect.collidepoint(pos):
                if i == self.menu_index:
                    self._activate()
                else:
                    self.menu_index = i
                    self._sync_selection()
                return

    def _move(self, delta: int) -> None:
        self.menu_index = (self.menu_index + delta) % len(self.menu)
        self._sync_selection()

    def _sync_selection(self) -> None:
        for i, item in enumerate(self.menu):
            item.selected = i == self.menu_index

    def _hero_box_for(self, width: int, height: int) -> tuple[int, int]:
        """Area da imagem do heroi no cartao."""
        _, _, slot_w, slot_h, _, image_box = self._cast_layout(width, height)
        return image_box

    def _current_box(self) -> tuple[int, int]:
        """Area de imagem do heroi, sempre em 1x, pela resolucao atual."""
        *_, image_box = self._cast_layout(*self.size)
        return image_box

    def _load_hero(self) -> None:
        """(Re)carrega a animacao do heroi na area do cartao.

        A area vem sempre do layout, nunca de um valor guardado: assim
        o heroi fica correto mesmo se a cena for desenhada pela
        primeira vez depois de uma mudanca de resolucao.
        """
        self._hero_box = self._current_box()
        # sem `max_scale`: vale a escala global das opcoes. `_hero_box`
        # e o teto em 1x, e o carregador usa o menor entre o teto e a
        # escala pedida. E por isso que 3x e 4x podem ficar iguais:
        # o cartao simplesmente nao tem espaco para crescer mais.
        self.hero_frames = assets.load_animation(self.hero_dir, box=self._hero_box)

    def _cycle_hero(self, delta: int) -> None:
        if not assets.has_animation():
            return
        index = self.hero_cycle.index(self.hero_dir)
        self.hero_dir = self.hero_cycle[(index + delta) % len(self.hero_cycle)]
        self._load_hero()

    def _activate(self) -> None:
        label = self.menu[self.menu_index].label
        if label == "Iniciar jogo":
            self.manager.switch("game")
        elif label == "Opcoes":
            self.manager.switch("options")
        else:
            self.manager.quit()

    def _show_notice(self, message: str) -> None:
        self.notice = message
        self.notice_timer = 2.5

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        self.hero_timer += dt
        mouse = pygame.mouse.get_pos()
        for item in self.menu:
            item.hovered = item.rect.collidepoint(mouse)

        if self.notice_timer > 0.0:
            self.notice_timer -= dt
            if self.notice_timer <= 0.0:
                self.notice = None

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLOR_BACKGROUND)
        width, height = self.size
        center_x = width // 2

        self._draw_background(surface)
        draw_text(
            surface,
            settings.GAME_TITLE,
            self._title_size(),
            (center_x, int(height * 0.13) - _bounce(self.time)),
            settings.COLOR_ACCENT,
        )
        self._draw_subtitle(surface, center_x, height)
        self._draw_cast(surface, width, height)
        self._draw_menu(surface)
        self._draw_footer(surface, center_x, height)

        if self.notice:
            draw_text(
                surface,
                self.notice,
                22,
                (center_x, int(height * 0.90)),
                settings.COLOR_DANGER,
            )

    def _title_size(self) -> int:
        return max(32, int(self.size[1] * 0.085))

    def _draw_background(self, surface: pygame.Surface) -> None:
        width, height = self.size
        panel = pygame.Rect(0, int(height * 0.60), width, height)
        draw_panel(surface, panel, color=settings.COLOR_PANEL, radius=0)
        pygame.draw.line(
            surface,
            settings.COLOR_PANEL_LIGHT,
            (0, panel.top),
            (width, panel.top),
            2,
        )

    def _draw_subtitle(self, surface: pygame.Surface, center_x: int, height: int) -> None:
        total = len(CHARACTER_LABELS)
        ready = self._sprites_ready()
        subtitle = "prototipo" if ready == total else f"prototipo - {ready}/{total} sprites"
        draw_text(
            surface,
            subtitle,
            max(16, int(height * 0.03)),
            (center_x, int(height * 0.22)),
            settings.COLOR_TEXT_DIM,
        )

    @staticmethod
    def _sprites_ready() -> int:
        return sum(
            1 for sprite_name, _, _ in CHARACTER_LABELS if assets.has_sprite(sprite_name)
        )

    def _cast_layout(self, width: int, height: int):
        """Calcula o tamanho dos cartoes proporcional a janela.

        A faixa do elenco e a area entre o subtitulo e o menu. O que
        sobra e dividido entre a imagem e o texto de cada cartao, para
        o cartao nunca invadir o menu.
        """
        count = len(CHARACTER_LABELS)
        gap = max(10, int(width * 0.016))

        # O cartao acompanha a resolucao. Com tamanho fixo, em
        # 1536x960 os personagens ficavam pequenos no meio de um painel
        # enorme, o que parecia "o jogo nao acompanhou a resolucao".
        # A escala das opcoes NAO entra aqui: ela e aplicada so pelo
        # carregador, senao entraria duas vezes.
        base_slot = (int(width * 0.86) - gap * (count - 1)) // count
        slot_w = max(150, min(int(height * 0.42), base_slot))

        top = int(height * 0.26)
        bottom = int(height * 0.60)
        room = max(80, bottom - top)

        text_h = int(height * 0.09)
        image_h = max(48, room - text_h)
        image_box = _fit_sprite_box(int(slot_w * 0.80), int(image_h * 0.94))
        slot_h = min(room, image_h + text_h)

        total_w = count * slot_w + (count - 1) * gap
        start_x = (width - total_w) // 2
        return start_x, top, slot_w, slot_h, gap, image_box

    def _hero_frame(self) -> pygame.Surface | None:
        if not self.hero_frames:
            return None
        index = int(self.hero_timer * assets.HERO_FPS) % len(self.hero_frames)
        return self.hero_frames[index]

    def _draw_cast(self, surface: pygame.Surface, width: int, height: int) -> None:
        """Elenco em linha, cada um com placeholder ou sprite real."""
        start_x, top, slot_w, slot_h, gap, image_box = self._cast_layout(width, height)

        # a area do heroi muda com resolucao e com a escala das opcoes
        if image_box != self._hero_box:
            self._load_hero()

        for i, (sprite_name, label, short_label) in enumerate(CHARACTER_LABELS):
            x = start_x + i * (slot_w + gap)
            rect = pygame.Rect(x, top, slot_w, slot_h)

            draw_panel(
                surface,
                rect,
                color=settings.COLOR_PANEL_LIGHT,
                border_color=settings.COLOR_PANEL_LIGHT,
            )

            if sprite_name == assets.SPRITE_PROTAGONIST and self.hero_frames:
                sprite = self._hero_frame()
            else:
                sprite = assets.load_sprite(
                    sprite_name, box=image_box, label=short_label
                )
            # a imagem fica na metade de cima do cartao, para nao
            # invadir o nome e o status
            image_area = pygame.Rect(
                rect.left, rect.top + 10, rect.width, max(8, rect.height - 74)
            )
            sprite_rect = sprite.get_rect(center=image_area.center)
            surface.blit(sprite, sprite_rect)

            draw_text(
                surface,
                label,
                max(14, int(image_box[1] * 0.13)),
                (rect.centerx, rect.bottom - 40),
                settings.COLOR_TEXT,
            )
            self._draw_status(surface, rect, sprite_name, image_box)

    def _effective_scale(self) -> int:
        """Escala realmente aplicada ao heroi nesta resolucao.

        Pode ser menor que a escolhida nas opcoes, quando o cartao nao
        tem espaco. Mostrar o valor real evita a duvida de "eu pedi 4x
        e apareceu 3x".
        """
        if not self.hero_frames:
            return 1
        base_w, base_h = HERO_BASE
        width = self.hero_frames[0].get_width()
        return max(1, round(width / base_w))

    def _draw_status(
        self, surface: pygame.Surface, rect: pygame.Rect, sprite_name: str, image_box
    ) -> None:
        if sprite_name == assets.SPRITE_PROTAGONIST and self.hero_frames:
            # `labels` devolve uma lista por acao (cada uma pode ter
            # varias teclas), entao achata antes de juntar
            girar = "/".join(
                label
                for action in ("girar_esquerda", "girar_direita")
                for label in self.controls.labels(action)
            )
            status = f"idle {self.hero_dir} - {self._effective_scale()}x ({girar})"
            color = settings.COLOR_ACCENT
        elif assets.has_sprite(sprite_name):
            status = "sprite ok"
            color = settings.COLOR_ACCENT
        else:
            status = "aguardando sprite"
            color = settings.COLOR_TEXT_DIM
        draw_text(
            surface,
            status,
            max(11, int(image_box[1] * 0.11)),
            (rect.centerx, rect.bottom - 18),
            color,
        )

    def _draw_menu(self, surface: pygame.Surface) -> None:
        for item in self.menu:
            color = settings.COLOR_PANEL
            border = None
            if item.selected:
                color = settings.COLOR_PANEL_LIGHT
                border = settings.COLOR_ACCENT
            elif item.hovered:
                color = settings.COLOR_PANEL_LIGHT

            draw_panel(
                surface, item.rect, color=color, border_color=border, border_width=2
            )
            text_color = (
                settings.COLOR_ACCENT if item.selected else settings.COLOR_TEXT
            )
            draw_text(surface, item.label, 26, item.rect.center, text_color)

            if item.selected:
                marker = 8
                mx = item.rect.left - 26
                my = item.rect.centery
                pygame.draw.polygon(
                    surface,
                    settings.COLOR_ACCENT,
                    [(mx, my - marker), (mx + marker, my), (mx, my + marker)],
                )

    def _draw_footer(self, surface: pygame.Surface, center_x: int, height: int) -> None:
        # as teclas vem do mapa do jogador, entao o rodape sempre
        # mostra o que ele realmente configurado
        def joined(*actions: str) -> str:
            # achata: cada acao pode ter varias teclas
            flat = [
                label
                for action in actions
                for label in self.controls.labels(action)
            ]
            return " ou ".join(flat)

        parts = [f"{joined('mover_cima', 'mover_baixo')}  navegar"]
        if assets.has_animation():
            parts.append(f"{joined('girar_esquerda', 'girar_direita')}  girar o heroi")
        parts.append(f"{joined('confirmar')}  confirmar")
        parts.append(f"{joined('voltar')}  sair")
        draw_text(
            surface, "      ".join(parts), 18,
            (center_x, height - 52), settings.COLOR_TEXT_DIM,
        )

        if self._sprites_ready() < len(CHARACTER_LABELS):
            note = "coloque os PNGs em assets/sprites/ (protagonista, estranho, mulher_misteriosa, rei_mago)"
        else:
            note = "python tools/make_hero_sheet.py  regenera os sprites do heroi"
        draw_text(surface, note, 15, (center_x, height - 28), (110, 104, 126))


def _fit_sprite_box(max_w: int, max_h: int) -> tuple[int, int]:
    """Area maxima do sprite, respeitando a proporcao do heroi.

    Sem isso o cartao ganha formas diferentes em resolucoes
    diferentes, e a escala 3x/4x estica a imagem em vez de fazer
    apenas o enlarge.
    """
    ratio = assets.HERO_ASPECT  # largura / altura do quadro
    height = int(max_h)
    width = int(height * ratio)
    if width > max_w:
        width = max_w
        height = int(width / ratio)
    return max(8, width), max(8, height)


def _max_scale_that_fits(box_w: int, box_h: int) -> int:
    """Maior escala inteira de sprite que cabe na area de imagem.

    Serve para mostrar a escala efetiva na tela. O carregador ja
    limita pelo mesmo teto, entao isto e so informacao para o jogador.
    """
    for scale in (4, 3, 2, 1):
        if HERO_BASE[0] * scale <= box_w and HERO_BASE[1] * scale <= box_h:
            return scale
    return 1


def _bounce(time: float) -> int:
    """Deslocamento suave do titulo."""
    import math

    return int(abs(math.sin(time * 3.9)) * 5)



