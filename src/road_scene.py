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

from . import animacao, assets, cenarios, chao as chao_mod, luz, rocha, settings, theme, wang
from .dungeon_map import CHAO, PAREDE, Mapa, gerar_mapa
from . import estado as estado_mod
from . import equipamento as equip_mod
from . import ui_arte
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
    modo_equip: int | None = None
    index_equip = 0

    def __init__(self, manager) -> None:
        super().__init__(manager)
        # um mapa aberto e largo: nao e uma masmorra, e um caminho
        self.mapa: Mapa = gerar_mapa(
            largura=40, altura=24, salas=3, semente=101
        )
        self._wang: wang.GradeWang | None = None
        self.progresso = manager.ui_state.get("progresso")
        # a estrada tambem mostra o contador de ouro no inventario, e o
        # ouro vive no estado do gerenciador
        self.estado = estado_mod.do_gerenciador(manager)

        self.direction = "sul"
        self.moving = False
        self.anim_time = 0.0
        # o relogio do passo do heroi: o corpo sobe duas vezes por
        # ciclo, inclina e achata. Nao e o mesmo que o metodo
        # `_passo()`, que calcula o deslocamento em pixels.
        self.andamento = animacao.Passo()
        # o relogio do passo do heroi. Antes nenhuma cena do mundo
        # tinha um: o personagem andava deslizando em vez de pisar.

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
        # o R entra no submenu de equipamento, mas so com o inventario
        # aberto: trocar arma sem ver o que esta nas maos seria trocar no
        # escuro. O teste do R fica FORA do do Q - aninhado dentro dele o
        # R nunca satisfazia a condicao e o submenu nao abria nunca.
        if self.inventario_aberto and self.key(event, "trocar_equipamento"):
            self.modo_equip = 0 if self.modo_equip is None else None
            return
        if self.key(event, "inventario"):
            # fecha os outros menus SEM mexer no inventario: e o
            # proprio Q que esta decidindo se ele fica aberto
            self._fechar_outros_menus(mantem_inventario=True)
            self.inventario_aberto = not self.inventario_aberto
            return

        if "interagir" in acoes:
            # a estrada e o caminho para a aldeia. Sem isso a fuga da
            # masmorra levaria a um lugar sem saida, e a aldeia ficaria
            # inalcancavel.
            # o atributo e `avisar_tempo`, com o nome que a cena usa
            # para o contador do aviso. `_avisar_tempo` nao existe aqui
            # e o E na estrada quebrava com AttributeError.
            if self.avisar_tempo <= 0:
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
        # com Shift o aperto vale um tile inteiro, e nao meio: e o que
        # faz a estrada deixar de ser uma sequencia de photographs
        self.andamento.correndo = animacao.correndo_agora()
        passo = self.tile * (
            animacao.PASSO_CORRIDA if self.andamento.correndo
            else animacao.PASSO_ANDAR
        )
        # o passo de corrida vale o dobro, entao so vale se o MEIO do
        # caminho estiver livre. Testando so o destino, o heroi
        # aparecia do outro lado de uma parede no meio do aperto
        meio = self.posicao + pygame.Vector2(dx, dy) * (self.tile / 2)
        if passo > self.tile / 2 and not self._livre(meio):
            passo = self.tile / 2
        alvo = self.posicao + pygame.Vector2(dx * passo, dy * passo)
        if self._livre(alvo):
            self.posicao = alvo
        self._limitar_camera()

    def _pe_do_heroi(self) -> tuple[int, int]:
        """A caixa dos PÉS do heroi, em pixels. A mesma da aldeia.

        O que o olho ve e o desenho de 90px; medir so o centro deixa
        metade do corpo dentro da parede.
        """
        arte = assets.equipado_na_tela("punho", assets.get_sprite_scale())
        if arte is None:
            return self.tile // 2, self.tile // 2
        return (max(4, arte.get_width() // 2),
                max(4, arte.get_height() * 3 // 20))

    def _livre(self, ponto: pygame.Vector2) -> bool:
        """True se a caixa dos pes do heroi cabe inteira em chao andavel.

        Antes era um ponto, e o heroi encostava com o centro a uma
        parede deixando metade do corpo na pedra.
        """
        meia_l, meia_a = self._pe_do_heroi()
        fx = int((ponto.x - meia_l) // self.tile)
        ax = int((ponto.x + meia_l) // self.tile)
        fy = int((ponto.y - meia_a) // self.tile)
        ay = int((ponto.y + meia_a) // self.tile)
        for cy in range(min(fy, ay), max(fy, ay) + 1):
            for cx in range(min(fx, ax), max(fx, ax) + 1):
                x = int(cx)
                y = int(cy)
                if not self.mapa.andavel(x, y):
                    return False
        return True

    def _limitar_camera(self) -> None:
        self.camera.x = max(0.0, min(
            self.camera.x, self.mapa.largura * self.tile - self.size[0]))
        self.camera.y = max(0.0, min(
            self.camera.y, self.mapa.altura * self.tile - self.size[1]))

    def update(self, dt: float) -> None:
        self.time += dt
        self.anim_time += dt
        self.andamento.advance(dt, self.moving)
        if self.avisar_tempo > 0:
            self.avisar_tempo -= dt

    # --- desenho -----------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        # o fundo e o material de fora, e nao o preto do tema: a estrada e
        # mais estreita que a tela e a borda aparecia como buraco
        surface.fill(rocha.BASE_DIA)
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
                    # a parede e pedra, e nao a cor do fundo: a estrada
                    # ficava desenhada no meio de um buraco negro
                    surface.blit(
                        rocha.celula(self.tile, x, y, rocha.BASE_DIA),
                        (x * self.tile + x_desenho, y * self.tile + y_desenho),
                    )
                    continue
                chave, _img = self._wang.tile_e_chave(x, y)
                pos = (x * self.tile + x_desenho, y * self.tile + y_desenho)
                surface.blit(_tile(chave, self.tile), pos)
                # detalhe espalhado no chao: a peca sozinha repete na
                # mesma distancia em todas as celulas e a tela vira
                # papel de parede. A peca nao e mexida — mexer nela
                # cortava os tufos ao meio
                chao_mod.desenhar_celula(
                    surface, _tile(chave, self.tile), self.tile,
                    pos[0], pos[1], x, y,
                )

        # heroi
        self._desenhar_heroi_equipado(surface)

        if self.avisar_tempo > 0 and self.avisar:
            theme.text_tracked_at(
                surface, self.avisar, 19,
                (w // 2, 40), theme.GOLD)

        theme.text_tracked_at(
            surface, "ESTRADA", 17, (20, 20), theme.TEXT_DIM)
        # a luz: mascara sobre a cena pronta. O mapa inteiro com a
        # mesma claridade e uma laje lisa; com a luz, o que esta longe
        # some e o que esta perto do heroi aparece.
        # DE DIA, como a aldeia: sem mascara de luz. A estrada ao sol
        # escurecida num circulo em volta do heroi era a cena inteira
        # apagada, com um anel de luz no meio de nada.
        if getattr(self, "fogueira_pos", None) is not None:
            self._desenhar_fogueira(surface)
        self._desenhar_inventario_mundo(surface)
        theme.text_tracked_at(
            surface, "E segue para a aldeia", 15,
            (w // 2 - 90, h - 44), theme.GOLD)
        theme.text_tracked_at(
            surface, "voltar para o menu", 14,
            (w - 190, h - 24), theme.TEXT_DIM)

    def _desenhar_inventario_mundo(self, surface: pygame.Surface) -> None:
        # o submenu de equipamento e um submenu, nao uma segunda janela:
        # desenhado por cima do inventario os dois painÃ©is caiam no mesmo
        # centro. Aqui ele SUBSTITUI o inventario enquanto estiver aberto.
        if self.modo_equip is not None:
            self._desenhar_equipamento(surface)
            return

        """O inventario andando pelo mapa, nos slots do painel.

        Fora da luta o Q e so o QUE: usar pocao com o jogo pausado nao
        tem efeito em ninguem, e fingir que tem seria pior do que nao
        ter. A conversao em vida de verdade acontece na luta.
        """
        if not self.inventario_aberto:
            return
        w, h = self.size
        p = self.manager.ui_state.get("progresso")
        linhas = itens_mod.rotulos(dict(p.itens) if p is not None else {})

        painel = ui_arte.desenhar(
            surface, ui_arte.PAINEL_INVENTARIO,
            (w // 2, h // 2), int(w * 0.42),
        )
        if painel is None:
            itens_mod.desenhar_inventario(
                surface, dict(p.itens) if p is not None else {},
                (w // 2 - 165, h // 2 - 60),
            )
            return

        conjunto = equip_mod.Conjunto(
            p.arma if p else None, p.escudo if p else None)
        arte_conjunto = assets.carregar_equipado(conjunto.chave, escala=1)
        ui_arte.desenhar_inventario(
            surface, painel, linhas,
            conjunto=arte_conjunto, rotulo=conjunto.rotulo,
            ouro=self.estado.ouro,
        )
        theme.text_tracked_at(
            surface, "q ou esc fecha", 13,
            (painel.x, painel.bottom + 8), theme.TEXT_DIM)
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
        """A escolha do conjunto, no painel EQUIPMENT do CraftPix."""
        if self.modo_equip is None:
            return
        conjuntos = equip_mod.todos_os_conjuntos()
        w, h = self.size
        miolo = ui_arte.desenhar(
            surface, ui_arte.PAINEL_EQUIPAMENTO,
            (w // 2, h // 2), int(w * 0.34),
        )
        if miolo is None:
            return
        linhas, passo = ui_arte.linhas_do_equipamento(miolo)
        for i, c in enumerate(conjuntos):
            if i >= len(linhas):
                break
            linha = linhas[i]
            marcado = i == self.index_equip
            cor = theme.GOLD if marcado else theme.TEXT
            if marcado:
                pygame.draw.rect(surface, theme.GOLD, linha, 1)
            arte = assets.carregar_equipado(c.chave, escala=1)
            # o boneco encolhe para a altura da linha. Com a altura
            # inteira ele transbordava 46px para cima e a primeira
            # linha invadia a barra de EQUIPMENT
            if arte is None:
                texto_x = linha.x + 2
            else:
                pequeno = ui_arte._caber_pequeno(arte, ui_arte.lado_do_desenho(linha))
                surface.blit(pequeno, pequeno.get_rect(
                    midleft=(linha.x + 2, linha.centery)))
                texto_x = linha.x + pequeno.get_width() + 8
            theme.text_tracked_at(
                surface, c.rotulo, 13, (texto_x, linha.y + 2), cor)
        theme.text_tracked_at(
            surface, "enter usa   esc volta", 12,
            (miolo.x, miolo.bottom + 6), theme.TEXT_DIM)
    def _desenhar_heroi_equipado(self, surface: pygame.Surface) -> None:
        """O heroi no mapa, com o que esta nas maos e um passo de verdade.

        O desenho do conjunto manda em TODOS os estados: ele tem a arma
        certa e o personagem e sempre o mesmo. A animacao de caminhada
        do pacote de mercado traria uma espada na mao em todos os
        conjuntos, e o jogador comeca desarmado.

        O que faz o movimento e `animacao.Passo`: o corpo sobe duas
        vezes por ciclo, inclina e achata na aterrissagem, e a sombra
        encolhe junto. O desenho nunca sai do lugar no chao, que e o que
        o olho le como andar de verdade.
        """
        p = self.progresso
        chave = equip_mod.chave_com_desenho(
            p.arma if p else None, p.escudo if p else None
        )
        centro = (
            int(self.posicao.x - self.camera.x + self.size[0] // 2),
            int(self.posicao.y - self.camera.y + self.size[1] // 2),
        )
        arte = assets.equipado_na_tela(chave, assets.get_sprite_scale())
        if arte is not None:
            animacao.desenhar_heroi(
                surface, arte, self.andamento, centro,
                direcao=self.direction, movendo=self.moving,
                tile=self.tile,
            )
            return
        quadros = self.frames
        if quadros:
            animacao.desenhar_heroi(
                surface, quadros[int(self.anim_time * 8) % len(quadros)],
                self.andamento, centro, direcao=self.direction,
                movendo=self.moving, tile=self.tile, com_sombra=False,
            )
    def _fechar_outros_menus(self, mantem_inventario: bool = False) -> None:
        """So um menu por vez.

        A loja abria POR CIMA do inventario, e os dois paineis
        ficavam empilhados no meio da tela. Cada menu aqui e a unica
        coisa que o jogador precisa ver enquanto ele esta aberto.

        `mantem_inventario` existe para o Q. O Q primeiro fecha os
        outros menus e depois alterna o inventario; sem este sinal o
        metodo zerava a flag e o `not` seguinte a reabria, e o painel
        nunca saia de tela.
        """
        if not mantem_inventario:
            self.inventario_aberto = False
        self.modo_equip = None
        self.loja = None
        self.loja_aviso = ""




