"""Tela inicial minimalista, no estilo Dark Souls.

Sem paineis, sem bordas, sem icones: texto sobre o escuro. O item
selecionado respira em dourado, com um losango pequeno a esquerda. A
transicao entre cenas e um fade, como nos jogos de referencia.

O elenco (personagens) fica escondido atras de uma tecla, para nao
poluir o menu principal.
"""
from __future__ import annotations

from typing import List, Tuple

import pygame

from . import assets, saves, settings, theme
from .ui import formatar_tempo
from .scene import Scene

# "Continuar" so aparece quando existe save para continuar. A lista
# completa e esta; `_visiveis` filtra de acordo com o que ha gravado.
MENU_ITEMS: Tuple[str, ...] = (
    "Continuar",
    "Novo jogo",
    "Opcoes",
    "Sair",
)

# rotulo -> acao. Continuar e Novo jogo levam para a masmorra, mudando
# so o que ja vem carregado.
ITEM_CONTINUAR = "Continuar"
ITEM_NOVO = "Novo jogo"
ITEM_OPCOES = "Opcoes"
ITEM_SAIR = "Sair"

# atalhos de teclado para as cenas, vindos do mapa do jogador
SCENE_SHORTCUTS: Tuple[Tuple[str, str, str], ...] = (
    ("Iniciar jogo", "game", "comecar"),
    ("Opcoes", "options", "opcoes"),
    ("Sair", "title", "sair"),
)


class TitleScreen(Scene):
    """Menu principal, so texto sobre o fundo escuro."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.index = 0
        self.time = 0.0
        self.notice: str | None = None
        self.notice_timer = 0.0
        # fade ao entrar: comeca escuro e clareia
        self.fade = 1.0
        # o lugar de save e escolhido uma vez, no primeiro menu que
        # aparece: Postgres se responder, arquivo senao
        self.store = saves.escolher_store()
        self.save = self.store.carregar()
        self._visiveis = self._filtrar()
        self._layout()
        self._sync()

    @property
    def tem_save(self) -> bool:
        return self.save is not None

    def _filtrar(self) -> Tuple[str, ...]:
        """Itens visiveis: sem save, "Continuar" nao faz sentido."""
        if self.save is None:
            return tuple(i for i in MENU_ITEMS if i != ITEM_CONTINUAR)
        return MENU_ITEMS

    def _reload_save(self) -> None:
        """Relê o save e refaz a lista, para o menu refletir o disco."""
        self.save = self.store.carregar()
        self._visiveis = self._filtrar()
        if self.index >= len(self._visiveis):
            self.index = 0
        self._layout()

    def _notice(self, texto: str) -> None:
        self.notice = texto
        self.notice_timer = 2.6

    # layout --------------------------------------------------------
    def _layout(self) -> None:
        w, h = self.size
        center_x = w // 2
        # itens no terco inferior, com espacamento vertical calmo
        base_y = int(h * 0.54)
        step = max(40, int(h * 0.085))
        self._positions = [
            (center_x, base_y + i * step) for i in range(len(self._visiveis))
        ]
        self.title_pos = (center_x, int(h * 0.20))
        self.hint_y = int(h * 0.94)

    def on_enter(self) -> None:
        self.index = 0
        self.fade = 1.0
        self._reload_save()
        self._sync()

    def _sync(self) -> None:
        return  # nada de estado por item; o desenho calcula direto

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
            return
        if event.type != pygame.KEYDOWN:
            return

        if self.key(event, "mover_cima"):
            self.index = (self.index - 1) % len(self._visiveis)
        elif self.key(event, "mover_baixo"):
            self.index = (self.index + 1) % len(self._visiveis)
        elif self.key(event, "confirmar"):
            self._activate()
        elif self.key(event, "voltar"):
            self.manager.quit()

    def _click(self, pos: Tuple[int, int]) -> None:
        font = theme.Fonts.get(int(self.size[1] * 0.038))
        for i, center in enumerate(self._positions):
            rect = font.render(self._visiveis[i], True, theme.TEXT)
            rect = rect.get_rect(center=center)
            # um pouco de folga, para o clique nao ser surgical
            rect.inflate_ip(40, 12)
            if rect.collidepoint(pos):
                self.index = i
                self._activate()
                return

    def _activate(self) -> None:
        if not self._visiveis:
            return
        label = self._visiveis[self.index]

        if label == ITEM_CONTINUAR:
            if self.save is None:
                self._notice("Nenhum save para continuar")
                return
            self.manager.iniciar_novo_jogo(self.save)
        elif label == ITEM_NOVO:
            # Novo jogo apaga o progresso anterior e comeca do caixao
            if self.tem_save:
                self.store.apagar()
            self.manager.iniciar_novo_jogo(None)
        elif label == ITEM_OPCOES:
            self.manager.switch("options")
        else:
            self.manager.quit()

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        if self.fade > 0.0:
            self.fade = max(0.0, self.fade - dt * 1.6)
        if self.notice_timer > 0.0:
            self.notice_timer -= dt
            if self.notice_timer <= 0.0:
                self.notice = None

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        w, h = self.size

        # um vinheta sutil, para o olho ir pro centro
        self._draw_vignette(surface, w, h)

        # titulo, espacado, bem alto
        theme.text_tracked(
            surface, "JOHN SYBAU", int(h * 0.075), self.title_pos,
            theme.TEXT_BRIGHT, tracking=6,
        )
        theme.hairline(surface, w // 2 - int(w * 0.08), int(h * 0.28),
                       w // 2 + int(w * 0.08))

# itens
        breath = theme.pulse(self.time, 1.2)
        font_size = int(h * 0.042)
        for i, center in enumerate(self._positions):
            selected = i == self.index
            if selected:
                color = theme.lerp(theme.GOLD, theme.GOLD_BRIGHT, breath)
            else:
                color = theme.TEXT_DIM
            box = theme.text_tracked(
                surface, self._visiveis[i], font_size, center, color, tracking=4,
            )
            # losango logo ao lado do item selecionado
            if selected:
                d = 4 + int(breath * 2)
                cx = box.left - 28
                cy = center[1]
                pygame.draw.polygon(
                    surface, color,
                    [(cx - d, cy), (cx, cy - d), (cx + d, cy), (cx, cy + d)],
                )

        self._draw_save_info(surface, w, h)
        self._draw_hint(surface, w, h)

        # fade de entrada
        if self.fade > 0.0:
            theme.fade_surface(surface, int(self.fade * 255))

    def _draw_save_info(self, surface: pygame.Surface, w: int, h: int) -> None:
        """Linha do save: area, tempo jogado e onde esta guardado.

        Mostrar de onde o save veio evita a duvida classica de quem joga
        offline: "eu salvei, mas onde?".
        """
        y = int(h * 0.855)
        tamanho = int(h * 0.020)

        if self.save is None:
            theme.text_tracked_at(
                surface, "NENHUM SAVE", tamanho, (int(w * 0.06), y),
                theme.HAIRLINE, tracking=2,
            )
        else:
            linha = (
                f"{self.save.area.upper()}    "
                f"{formatar_tempo(self.save.tempo_jogado)} jogados"
            )
            theme.text_tracked_at(
                surface, linha, tamanho, (int(w * 0.06), y),
                theme.TEXT_DIM, tracking=2,
            )
            # o local do save ancorado na direita
            theme.text_tracked_right(
                surface, self.store.descricao, tamanho, w - int(w * 0.06), y,
                theme.HAIRLINE, tracking=2,
            )

    def _draw_vignette(self, surface: pygame.Surface, w: int, h: int) -> None:
        """Escurece as bordas, como a luz de uma vela no centro.

        Aneis concentricos, do maior para o menor, cada um com um
        pouco de preto translucido. Precisa de uma superficie SRCALPHA:
        desenhar alpha direto no display nao sobrepoe nada.
        """
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        max_r = int((w * w + h * h) ** 0.5) // 2
        rings = 20
        for i in range(rings, 0, -1):
            r_out = max_r * i // rings
            alpha = 3 if i < rings // 2 else 6
            pygame.draw.ellipse(
                veil, (0, 0, 0, alpha),
                pygame.Rect(cx - r_out, cy - r_out, r_out * 2, r_out * 2),
                width=max(2, max_r // rings + 1),
            )
        surface.blit(veil, (0, 0))

    def _draw_hint(self, surface: pygame.Surface, w: int, h: int) -> None:
        up = "/".join(self.controls.labels("mover_cima"))
        down = "/".join(self.controls.labels("mover_baixo"))
        ok = "/".join(self.controls.labels("confirmar"))
        hint = f"{up or 'seta'} {down or 'seta'} navegar    {ok or 'enter'} confirmar"
        theme.text_tracked_at(
            surface, hint, int(h * 0.022), (int(w * 0.06), self.hint_y),
            theme.HAIRLINE, tracking=1,
        )
        if self.notice:
            theme.text_tracked(
                surface, self.notice, int(h * 0.028),
                (w // 2, int(h * 0.70)), theme.GOLD, tracking=2,
            )
