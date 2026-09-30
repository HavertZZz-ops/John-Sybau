"""A cidadezinha dos moradores locais.

Fica depois da estrada, e e o lugar para onde o jogador vai quando sai
da masmorra. Sao quatro moradores, cada um com nome e uma frase. Nao ha
loja, nem cura, nem missao: o objetivo e dar nome e voz ao lugar, para
que a saida da masmorra tenha para onde levar.

Os moradores sao dados, nao codigo. Adicionar alguem e uma entrada em
MORADORES.
"""
from __future__ import annotations

import pygame

from . import assets, cenarios, settings, theme, wang
from .dungeon_map import CHAO, Mapa, gerar_mapa
from .scene import Scene

CENARIO_CIDADE = "cemiterio_wang"

TILE_BASE = 16
MOVE_SPEED = 190.0
ALCANCE_FALA = 34

DIRECOES = {
    "norte": (0, -1),
    "sul": (0, 1),
    "leste": (1, 0),
    "oeste": (-1, 0),
}

TABELA: dict | None = None
_TILES_ESCALADOS: dict[tuple, pygame.Surface] = {}
_ESCALA = -1


class Morador:
    """Um morador local: nome, uma frase e onde ele fica."""

    def __init__(self, nome: str, fala: str, dx: int, dy: int, cor: tuple) -> None:
        self.nome = nome
        self.fala = fala
        self.dx = dx
        self.dy = dy
        self.cor = cor
        self.falando = 0.0


# Quem mora aqui. As falas sao curtas de proposito: e o lugar que
# estabelece o tom, nao um manual.
MORADORES: tuple[Morador, ...] = (
    Morador(
        "Ida", "Voce saiu andando. Quase ninguem faz isso.", -3, -1,
        (176, 148, 128),
    ),
    Morador(
        "Borracha", "A masmorra e de cipo. Nao acende.", 3, -1,
        (150, 132, 116),
    ),
    Morador(
        "Ze", "Fugir nao e perder. Voltar e que e.", 0, 3,
        (162, 140, 120),
    ),
    Morador(
        "Dona Mo", "Se te acharem la dentro outra vez, corre.", -2, 3,
        (186, 160, 138),
    ),
)


def _tabela() -> dict | None:
    global TABELA
    if TABELA is not None:
        return TABELA
    tileset = next(
        (c for c in cenarios.CENARIOS if c.tileset == CENARIO_CIDADE), None
    )
    if tileset is None:
        return None
    png = settings.TILES_DIR / tileset.png
    meta = settings.TILES_DIR / tileset.json
    if not png.is_file() or not meta.is_file():
        return None
    try:
        TABELA, _ = wang.carregar_tileset_wang(png, meta)
    except (pygame.error, OSError, ValueError, KeyError):
        return None
    return TABELA


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


class CityScene(Scene):
    """A cidadezinha, com os moradores locales."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.mapa: Mapa = gerar_mapa(
            largura=34, altura=22, salas=3, semente=777
        )
        self._wang: wang.GradeWang | None = None
        self.progresso = manager.ui_state.get("progresso")

        self.direction = "sul"
        self.moving = False
        self.anim_time = 0.0
        self.time = 0.0
        self.tile = TILE_BASE * assets.get_sprite_scale()
        self.posicao = pygame.Vector2(
            self.mapa.para_pixels(*self.mapa.entrada, self.tile)
        )
        self.camera = pygame.Vector2(self.posicao)

        self.walk_frames = assets.load_animation(self.direction, "walk")
        self.idle_frames = assets.load_animation(self.direction, "idle")
        self.moradores: list[Morador] = self._posicionar_moradores()
        self.perto: Morador | None = None
        self.avisar = ""
        self.avisar_tempo = 0.0
        self.falas_ouvidas: set[str] = set()

    # --- posicao dos moradores ---------------------------------------
    def _posicionar_moradores(self) -> list[Morador]:
        """Coloca cada morador num chao valido perto do centro."""
        centro = self.mapa.centro_da_sala(2) or self.mapa.entrada
        usados: set[tuple[int, int]] = set()
        lista = []
        for m in MORADORES:
            alvo = None
            for raio in range(0, 7):
                for dx in range(-raio, raio + 1):
                    for dy in range(-raio, raio + 1):
                        if max(abs(dx), abs(dy)) != raio:
                            continue
                        celula = (centro[0] + m.dx + dx, centro[1] + m.dy + dy)
                        if not self.mapa.andavel(*celula):
                            continue
                        if celula in usados:
                            continue
                        alvo = celula
                        break
                    if alvo:
                        break
                if alvo:
                    break
            if alvo is None:
                continue
            usados.add(alvo)
            lista.append(m)
            m.celula = alvo  # type: ignore[attr-defined]
        return lista

    def _posicao_de(self, m: Morador) -> pygame.Vector2:
        return pygame.Vector2(
            self.mapa.para_pixels(*getattr(m, "celula"), self.tile)
        )

    # --- ciclo de vida -----------------------------------------------
    def on_enter(self) -> None:
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        p = self.progresso
        if p is not None and p.mundo == "estrada":
            p.mundo = "cidade"

    def _avisar(self, texto: str, segundos: float = 3.4) -> None:
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
        acoes = self.manager.input.actions_for(event)

        if "voltar" in acoes:
            if self.perto is not None:
                # primeiro o Esc fecha a conversa, so depois sai da cidade
                self.perto = None
                return
            self.manager.salvar_progresso()
            self.manager.switch("road")
            return

        if "interagir" in acoes:
            if self.perto is not None:
                self.perto.falando = 4.0
                self._avisar(f"{self.perto.nome}: {self.perto.fala}", 4.0)
                self.falas_ouvidas.add(self.perto.nome)
            elif self.avisar_tempo <= 0:
                self._avisar("Ninguem por perto. Aproxime-se de alguem.", 2.4)
            return

        for direcao, (dx, dy) in DIRECOES.items():
            acao = {"norte": "mover_cima", "sul": "mover_baixo",
                    "leste": "mover_direita", "oeste": "mover_esquerda"}[direcao]
            if acao in acoes:
                self._recarregar(direcao)
                self.moving = True
                passo = self.tile // 2
                alvo = self.posicao + pygame.Vector2(dx * passo, dy * passo)
                if self._livre(alvo):
                    self.posicao = alvo
                self._limitar_camera()
                return

    def _livre(self, ponto: pygame.Vector2) -> bool:
        return self.mapa.andavel(
            int(ponto.x // self.tile), int(ponto.y // self.tile)
        )

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
        for m in self.moradores:
            if m.falando > 0:
                m.falando -= dt
        # quem esta perto? o mais proximo dentro do alcance
        self.perto = None
        melhor = ALCANCE_FALA
        for m in self.moradores:
            d = self._posicao_de(m).distance_to(self.posicao)
            if d < melhor:
                melhor = d
                self.perto = m

    # --- desenho -----------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        tabela = _tabela()
        if tabela is None:
            theme.text_tracked_at(
                surface, f"tileset ausente: {CENARIO_CIDADE}.png",
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
                if self.mapa.em(x, y) != CHAO:
                    continue
                chave, _img = self._wang.tile_e_chave(x, y)
                surface.blit(
                    _tile(chave, self.tile),
                    (x * self.tile + x_desenho, y * self.tile + y_desenho),
                )

        for m in self.moradores:
            self._desenhar_morador(surface, m, w, h, x_desenho, y_desenho)

        quadros = self.frames
        if quadros:
            sprite = quadros[int(self.anim_time * 8) % len(quadros)]
            surface.blit(sprite, sprite.get_rect(
                center=(int(self.posicao.x - self.camera.x + w // 2),
                        int(self.posicao.y - self.camera.y + h // 2))))

        self._desenhar_fala(surface, w, h)
        theme.text_tracked_at(surface, "ALDEIA", 17, (20, 20), theme.TEXT_DIM)
        theme.text_tracked_at(
            surface, "E para falar   esc para sair", 14,
            (w - 220, h - 24), theme.TEXT_DIM)

    def _desenhar_morador(self, surface, m, w, h, x_off, y_off) -> None:
        p = self._posicao_de(m)
        px = int(p.x + x_off)
        py = int(p.y + y_off)
        # o corpo e um bloco com a cor do morador: e o bastante para
        # dizer "tem alguem aqui" sem gastar arte num NPC que so fala
        largura = max(6, self.tile // 3)
        altura = max(10, self.tile // 2)
        corpo = pygame.Rect(px - largura // 2, py - altura, largura, altura)
        pygame.draw.rect(surface, m.cor, corpo)
        pygame.draw.rect(surface, (28, 24, 22), corpo, 1)
        # cabeca
        pygame.draw.circle(
            surface, m.cor,
            (px, corpo.top - max(2, altura // 6)),
            max(2, altura // 5),
        )
        # piscada quando esta falando
        if m.falando > 0:
            pygame.draw.circle(surface, theme.GOLD, (px, py - altura - 6), 3)

        theme.text_tracked_at(
            surface, m.nome, 13, (px - 18, corpo.bottom + 3), theme.TEXT_DIM)

    def _desenhar_fala(self, surface, w, h) -> None:
        if self.avisar_tempo <= 0 or not self.avisar:
            return
        caixa = pygame.Rect(0, 0, min(720, w - 60), 64)
        caixa.midbottom = (w // 2, h - 60)
        pygame.draw.rect(surface, theme.BACKGROUND, caixa.inflate(10, 10))
        pygame.draw.rect(surface, theme.HAIRLINE, caixa.inflate(10, 10), 1)
        theme.text_tracked_at(
            surface, self.avisar, 16, (caixa.x + 8, caixa.y), theme.TEXT)