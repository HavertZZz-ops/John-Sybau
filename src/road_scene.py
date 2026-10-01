"""A estrada: o mundo de fora da masmorra.

E para onde o jogador chega quando foge do chefe forte da ultima sala.
Por enquanto e o pedaco entre a masmorra e a cidade: um caminho de terra
com grama dos dois lados e a silhueta da masmorra para tras.

A cena existe porque "sair correndo da masmorra" precisa de algum lugar
para onde correr. Sem ela a fuga sobrescreve um estado e o jogador
continua dentro da masmorra sem entender o que aconteceu.
"""
from __future__ import annotations

import random

import pygame

from . import assets, cenarios, settings, theme, wang
from .dungeon_map import CHAO, PAREDE, Mapa, gerar_mapa
from . import equipamento as equip_mod
from . import itens as itens_mod
from .scene import Scene

# o cenario que da o visual de fora. Reaproveita o tileset que ja
# existe em vez de gastar geracao num terceiro.
CENARIO_EXTERIOR = "cemiterio_wang"

TILE_BASE = 16
MOVE_SPEED = 190.0

DIRECOES = {
    "norte": (0, -1),
    "sul": (0, 1),
    "leste": (1, 0),
    "oeste": (-1, 0),
}

_TABELA: dict | None = None
_TILES_ESCALADOS: dict[tuple, pygame.Surface] = {}
_ESCALA = -1


def _tabela() -> dict | None:
    global _TABELA
    if _TABELA is not None:
        return _TABELA
    tileset = next(
        (c for c in cenarios.CENARIOS if c.tileset == CENARIO_EXTERIOR), None
    )
    if tileset is None:
        return None
    png = settings.TILES_DIR / tileset.png
    meta = settings.TILES_DIR / tileset.json
    if not png.is_file() or not meta.is_file():
        return None
    try:
        _TABELA, _ = wang.carregar_tileset_wang(png, meta)
    except (pygame.error, OSError, ValueError, KeyError):
        return None
    return _TABELA


def _tile(chave: tuple, lado: int) -> pygame.Surface:
    global _ESCALA
    if lado != _ESCALA:
        _TILES_ESCALADOS.clear()
        _ESCALA = lado
    pega = _TILES_ESCALADOS.get(chave)
    if pega is not None:
        return pega
    tabela = _tabela() or {}
    origem = tabela.get(chave) or tabela.get((False, False, False, False))
    if origem is None:
        return pygame.Surface((lado, lado), pygame.SRCALPHA)
    if origem.get_width() != lado:
        origem = pygame.transform.scale(origem, (lado, lado))
    _TILES_ESCALADOS[chave] = origem
    return origem


class RoadScene(Scene):
    """O trecho de estrada entre a masmorra e a cidade."""

    inventario_aberto = False

    def __init__(self, manager) -> None:
        super().__init__(manager)
        # um mapa aberto e largo: nao e uma masmorra, e um caminho
        self.mapa: Mapa = gerar_mapa(
            largura=40, altura=24, salas=3, semente=101
        )
        self._wang: wang.GradeWang | None = None
        self.progresso = manager.ui_state.get("progresso")

        self.direction = "sul"
        self.moving = False
        self.anim_time = 0.0
        self.time = 0.0
        self.tile = TILE_BASE * assets.get_sprite_scale()
        self.posicao = pygame.Vector2(self.mapa.para_pixels(*self.mapa.entrada, self.tile))
        self.camera = pygame.Vector2(self.posicao)

        self.walk_frames = assets.load_animation(self.direction, "walk")
        self.idle_frames = assets.load_animation(self.direction, "idle")
        self.avisar = ""
        self.avisar_tempo = 0.0
        self._avisou = False

    # --- ciclo de vida ----------------------------------------------
    def on_enter(self) -> None:
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        if not self._avisou:
            self._avisou = True
            self._avisar("Voce saiu da masmorra. A cidade fica adiante.", 5.0)

    def _avisar(self, texto: str, segundos: float = 3.0) -> None:
        self.avisar = texto
        self.avisar_tempo = segundos

    # --- movimento ---------------------------------------------------
    @property
    def frames(self) -> list[pygame.Surface]:
        return self.walk_frames if self.moving else self.idle_frames

    def _recarregar(self, direcao: str) -> None:
        if direcao == self.direction:
            return
        self.direction = direcao
        self.walk_frames = assets.load_animation(direcao, "walk")
        self.idle_frames = assets.load_animation(direcao, "idle")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        acoes = self.controls.actions_for(event.key)
        if "voltar" in acoes:
            self.manager.salvar_progresso()
            self.manager.switch("title")
            return
        if self.key(event, "inventario"):
            self.inventario_aberto = not self.inventario_aberto
            return

        if "interagir" in acoes:
            # a estrada e o caminho para a aldeia. Sem isso a fuga da
            # masmorra levaria a um lugar sem saida, e a aldeia ficaria
            # inalcancavel.
            if self._avisar_tempo <= 0:
                self.manager.switch("city")
            return
        for direcao, (dx, dy) in DIRECOES.items():
            acao = {"norte": "mover_cima", "sul": "mover_baixo",
                    "leste": "mover_direita", "oeste": "mover_esquerda"}[direcao]
            if acao in acoes:
                self._recarregar(direcao)
                self.moving = True
                self._andar(dx, dy)
                return

    def _andar(self, dx: int, dy: int) -> None:
        passo = self.tile // 2
        alvo = self.posicao + pygame.Vector2(dx * passo, dy * passo)
        if self._livre(alvo):
            self.posicao = alvo
        self._limitar_camera()

    def _livre(self, ponto: pygame.Vector2) -> bool:
        x = int(ponto.x // self.tile)
        y = int(ponto.y // self.tile)
        return self.mapa.andavel(x, y)

    def _limitar_camera(self) -> None:
        self.camera.x = max(0.0, min(
            self.camera.x, self.mapa.largura * self.tile - self.size[0]))
        self.camera.y = max(0.0, min(
            self.camera.y, self.mapa.altura * self.tile - self.size[1]))

    def update(self, dt: float) -> None:
        self.time += dt
        self.anim_time += dt
        if self.avisar_tempo > 0:
            self.avisar_tempo -= dt

    # --- desenho -----------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        tabela = _tabela()
        if tabela is None:
            theme.text_tracked_at(
                surface, f"tileset ausente: {CENARIO_EXTERIOR}.png",
                18, (20, 20), theme.TEXT_DIM)
            return
        if self._wang is None:
            self._wang = wang.GradeWang(self.mapa.celulas, tabela=tabela)

        w, h = self.size
        x_desenho = w // 2 - self.camera.x - self.tile // 2
        y_desenho = h // 2 - self.camera.y - self.tile // 2
        x0 = max(0, int((-x_desenho) // self.tile) - 1)
        y0 = max(0, int((-y_desenho) // self.tile) - 1)
        x1 = min(self.mapa.largura, x0 + w // self.tile + 3)
        y1 = min(self.mapa.altura, y0 + h // self.tile + 3)

        for y in range(y0, y1):
            for x in range(x0, x1):
                # `== PAREDE`, e nao `!= CHAO`. As celulas de enfeite
                # (talha, entulho, laje) sao andaveis mas nao sao
                # CHAO: com o teste antigo elas nao eram desenhadas e
                # apareciam como quadrados PRETOS no meio do chao.
                if self.mapa.em(x, y) == PAREDE:
                    continue
                chave, _img = self._wang.tile_e_chave(x, y)
                surface.blit(
                    _tile(chave, self.tile),
                    (x * self.tile + x_desenho, y * self.tile + y_desenho),
                )

        # heroi
        self._desenhar_heroi_equipado(surface)

        if self.avisar_tempo > 0 and self.avisar:
            theme.text_tracked_at(
                surface, self.avisar, 19,
                (w // 2, 40), theme.GOLD)

        theme.text_tracked_at(
            surface, "ESTRADA", 17, (20, 20), theme.TEXT_DIM)
        self._desenhar_inventario_mundo(surface)
        theme.text_tracked_at(
            surface, "E segue para a aldeia", 15,
            (w // 2 - 90, h - 44), theme.GOLD)
        theme.text_tracked_at(
            surface, "voltar para o menu", 14,
            (w - 190, h - 24), theme.TEXT_DIM)

    def _desenhar_inventario_mundo(self, surface: pygame.Surface) -> None:
        """O inventario andando pelo mapa.

        So desenha. Fora da luta nao da para usar nada: uma pocao
        curada com o jogo pausado nao tem efeito em ninguem, e fingir
        que tem seria pior do que nao ter. Aqui o Q e o QUE, o E e o
        QUE, e a luta e onde a pociao vira vida de verdade.
        """
        if not self.inventario_aberto:
            return
        w, h = self.size
        p = self.manager.ui_state.get("progresso")
        inv = dict(p.itens) if p is not None else {}
        itens_mod.desenhar_inventario(
            surface, inv, (w // 2 - 165, h // 2 - 60),
            rodape="q ou esc fecha",
        )

    def _tecla_equip(self, event) -> None:
        """Trocar o que esta nas maos, com as setas e o enter.

        E um submenu do Q. Uma tela a parte para isso seria demais
        para cinco conjuntos, e o jogador teria de sair do lugar para
        trocar de arma no meio de uma sala.
        """
        conjuntos = equip_mod.todos_os_conjuntos()
        if "voltar" in self.acoes_do_evento(event):
            self.modo_equip = None
            return
        if "mover_cima" in self.acoes_do_evento(event):
            self.index_equip = (self.index_equip - 1) % len(conjuntos)
        elif "mover_baixo" in self.acoes_do_evento(event):
            self.index_equip = (self.index_equip + 1) % len(conjuntos)
        elif "confirmar" in self.acoes_do_evento(event):
            escolhido = conjuntos[self.index_equip]
            p = self.progresso
            p.arma = escolhido.arma or "espada"
            p.escudo = escolhido.escudo
            self.manager.ui_state["progresso"] = p
            self.manager.salvar_progresso()
            self.modo_equip = None

    def _acoes_do_evento(self, event) -> set:
        if hasattr(self, "key"):
            return {a for a in self.acoes if self.key(event, a)}
        return set(self.controls.actions_for(event.key))

    def _desenhar_equipamento(self, surface: pygame.Surface) -> None:
        """A lista de conjuntos, sobre o inventario."""
        if self.modo_equip is None:
            return
        conjuntos = equip_mod.todos_os_conjuntos()
        w, h = self.size
        caixa = pygame.Rect(0, 0, min(420, w - 60), 70 + 34 * len(conjuntos))
        caixa.center = (w // 2, h // 2)
        pygame.draw.rect(surface, theme.BACKGROUND, caixa.inflate(12, 12))
        pygame.draw.rect(surface, theme.HAIRLINE, caixa.inflate(12, 12), 1)
        theme.text_tracked_at(
            surface, "NAS MAOS", 17, (caixa.x, caixa.y - 26), theme.GOLD)
        for i, c in enumerate(conjuntos):
            y = caixa.y + i * 34
            marcado = i == self.index_equip
            cor = theme.GOLD if marcado else theme.TEXT
            pygame.draw.rect(
                surface, theme.BACKGROUND_SOFT,
                pygame.Rect(caixa.x - 4, y - 4, caixa.width + 8, 30))
            if marcado:
                pygame.draw.rect(
                    surface, theme.GOLD,
                    pygame.Rect(caixa.x - 4, y - 4, 3, 30))
            arte = assets.carregar_equipado(c.chave, escala=1)
            if arte is not None:
                surface.blit(arte, arte.get_rect(
                    midleft=(caixa.x + 4, y + 11)))
            theme.text_tracked_at(
                surface, c.rotulo, 15, (caixa.x + 76, y + 8), cor)
        theme.text_tracked_at(
            surface, "enter usa   esc volta", 13,
            (caixa.x, caixa.bottom + 10), theme.TEXT_DIM)

    def _desenhar_heroi_equipado(self, surface: pygame.Surface) -> None:
        """O heroi no mapa, com o que esta nas maos.

        A animacao de caminhada vem sempre do espadachim do pacote de
        mercado: ela nao tem variante por arma, e um desenho estatico de
        64px ao lado de uma animacao de 12 quadros faz o personagem
        piscar de desenho a cada passo. Entao o conjunto equipado
        aparece na PARADA, e a animacao assume assim que o jogador se
        move.
        """
        p = self.progresso
        chave = equip_mod.chave_com_desenho(
            p.arma if p else None, p.escudo if p else None
        )
        arte = assets.carregar_equipado(chave, escala=assets.get_sprite_scale())
        if arte is None or self.moving:
            quadros = self.frames
            if quadros:
                sprite = quadros[int(self.anim_time * 8) % len(quadros)]
                surface.blit(sprite, sprite.get_rect(
                    center=(int(self.posicao.x - self.camera.x + self.size[0] // 2),
                            int(self.posicao.y - self.camera.y + self.size[1] // 2))))
            return
        surface.blit(arte, arte.get_rect(
            center=(int(self.posicao.x - self.camera.x + self.size[0] // 2),
                    int(self.posicao.y - self.camera.y + self.size[1] // 2))))
