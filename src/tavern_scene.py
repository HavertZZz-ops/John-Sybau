"""O interior da taverna: a sala de verdade, com o dono la dentro.

Antes a taverna era so um telhado na aldeia e um botao de pernoitar.
Agora o jogador entra: a porta abre, o salao aparece com o balcao, as
mesas, o relogio e o Tao Anchieta atras do balcao, e e la que se dorme.

O salao e montado com o pacote Top-Down Retro Interior: piso de tijolo,
paredes e moveis recortados por `tools/fatiar_interior.py`. O layout e
um mapa de texto, porque uma planta desenhada em texto da para ler e
corrigir; um monte de coordenadas nao.

Cada letra do mapa e uma celula de TILE px. As paredes sao desenhadas
na ordem em que aparecem na folha, o que da a sensacao de canto sem
precisar de nove tipos de parede.
"""
from __future__ import annotations

import pathlib

import pygame

from . import animacao, assets, equipamento as equip_mod, itens as itens_mod
from . import theme, ui_arte
from .scene import Scene

TILE = 48
CELULA_ARTES = 16  # a grade de 16px em que o pacote foi desenhado

# --- a planta do salao ------------------------------------------------
#  # parede   . piso de tijolo   , piso claro (varredura)
#  B balcao   M mesa   b banco   E estante   R relogio
#  L lareira  P poltrona  v vaso  t tapete   c cadeira  F fireplace
#
# A porta fica em baixo, no meio: e por onde o jogador veio.
PLANTA = (
    "#######################",
    "#,,.,.,.,.,.,.,.,.,.,.#",
    "#A......BBBBBBB.......#",
    "#A..M.S.BBBBBBB..E.L..#",
    "#...M.S......R..P.....#",
    "#...M.S..t...R..P.....#",
    "#........c.......c....#",
    "#...b..t..e.......V...#",
    "#G..b......l..........#",
    "#.......t..........d..#",
    "#######################",
)

# o que cada letra e: (peca, andavel, altura_em_celulas)
PECAS: dict[str, tuple[str, bool, int, int]] = {
    # letra: (peca, andavel, colunas, linhas que a peca ocupa)
    "#": ("parede_tijolo", False, 1, 1),
    ".": ("piso_terra", True, 1, 1),
    ",": ("piso_claro", True, 1, 1),
    # a porta: e chao andavel, e a unica saida do salao
    "d": ("porta_aberta", True, 1, 1),
    "A": ("adega", False, 3, 1),
    "B": ("balcao", False, 7, 3),
    "E": ("estante", False, 2, 2),
    "G": ("armario", False, 2, 2),
    "M": ("mesa", False, 3, 1),
    "S": ("sofa", False, 2, 2),
    "b": ("banco", False, 2, 1),
    "c": ("cadeira", False, 1, 2),
    "P": ("poltrona", False, 2, 3),
    "R": ("relogio", False, 1, 3),
    "L": ("lareira", False, 1, 3),
    "e": ("espelho", False, 2, 3),
    "l": ("luminaria", False, 1, 3),
    "v": ("vaso", False, 1, 2),
    "V": ("vaso", False, 1, 2),  # a planta escreve o vaso com V maiusculo
    "t": ("tapete", True, 2, 2),
    "u": ("tapete2", True, 3, 2),
    "x": ("bau", False, 2, 1),
}

DIRETORIOS = {
    "mover_cima": (0, -1), "mover_baixo": (0, 1),
    "mover_esquerda": (-1, 0), "mover_direita": (1, 0),
}
NOME_DIRECAO = {
    (0, -1): "norte", (0, 1): "sul", (-1, 0): "oeste", (1, 0): "leste",
}

_cache: dict[str, pygame.Surface | None] = {}


def peca(nome: str) -> pygame.Surface | None:
    """Um recorte do pacote de interiores, como esta no disco."""
    if nome in _cache:
        return _cache[nome]
    caminho = (pathlib.Path(__file__).resolve().parent.parent
               / "assets" / "interior" / f"{nome}.png")
    img = None
    if caminho.is_file():
        try:
            img = pygame.image.load(str(caminho)).convert_alpha()
        except (pygame.error, OSError):
            img = None
    _cache[nome] = img
    return img


def amenities(x: int, y: int) -> bool:
    """A celula esta livre para o jogador entrar?"""
    if not (0 <= y < len(PLANTA) and 0 <= x < len(PLANTA[y])):
        return False
    letra = PLANTA[y][x]
    dado = PECAS.get(letra)
    return bool(dado and dado[1])


class TavernScene(Scene):
    """O salao da taverna da aldeia."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.progresso = manager.ui_state.get("progresso")
        from . import estado as estado_mod
        self.estado = estado_mod.do_gerenciador(manager)
        self.posicao = pygame.Vector2(TILE * 17.5, TILE * 7.4)
        # o desenho do heroi e o mesmo das outras tres cenas, e ele
        # calcula a posicao na tela a partir de `camera` e `tile`. A
        # taverna centraliza a planta em vez de rolar, entao a camera
        # e recalculada a cada desenho e o tile e o da planta.
        self.camera = pygame.Vector2(0, 0)
        self.tile = TILE
        self.direction = "sul"
        self.moving = False
        self.time = 0.0
        # o relogio do passo do heroi: o corpo sobe duas vezes por
        # ciclo, inclina e achata. Nao e o mesmo que o metodo
        # `_passo()`, que calcula o deslocamento em pixels.
        self.andamento = animacao.Passo()
        # o relogio do passo do heroi. Antes nenhuma cena do mundo
        # tinha um: o personagem andava deslizando em vez de pisar.
        self.avisar = ""
        self.avisar_tempo = 0.0
        # onde o Tao Anchieta fica: atras do balcao, no meio do salao
        self.tao = pygame.Vector2(TILE * 11.0, TILE * 1.7)
        self.falando = 0.0
        # os menus sao os mesmos da aldeia, com o mesmo apertar de teclas
        self.inventario_aberto = False
        self.modo_equip: int | None = None
        self.index_equip = 0
        self.walk_frames = assets.load_animation(self.direction, "walk")
        self.idle_frames = assets.load_animation(self.direction, "idle")

    # --- ciclo de vida ------------------------------------------------
    @property
    def frames(self) -> list[pygame.Surface]:
        return self.walk_frames if self.moving else self.idle_frames

    def _avisar(self, texto: str, segundos: float = 3.4) -> None:
        self.avisar = texto
        self.avisar_tempo = segundos

    def _recarregar(self, direcao: str) -> None:
        if direcao == self.direction:
            return
        self.direction = direcao
        self.walk_frames = assets.load_animation(direcao, "walk")
        self.idle_frames = assets.load_animation(direcao, "idle")

    # --- entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        acoes = self.controls.actions_for(event.key)

        if self.inventario_aberto and self.key(event, "trocar_equipamento"):
            self.modo_equip = 0 if self.modo_equip is None else None
            return
        if self.key(event, "inventario"):
            self._fechar_outros_menus(mantem_inventario=True)
            self.inventario_aberto = not self.inventario_aberto
            return

        if self.inventario_aberto:
            if self.modo_equip is not None:
                self._tecla_equip(event)
            return

        if "voltar" in acoes:
            self.manager.switch("city")
            return

        if "interagir" in acoes:
            if self.posicao.distance_to(self.tao) < TILE * 1.6:
                self._dormir()
                return
            # a porta fica embaixo, no meio
            if abs(self.posicao.x - TILE * 18.0) < TILE * 1.5 and \
                    self.posicao.y > TILE * 7.5:
                self.manager.switch("city")
                return
            self._avisar("Ninguem por perto. O balcao e em cima.", 2.4)
            return

        if self.modo_equip is not None:
            return

        dx = dy = 0
        for acao, (ax, ay) in DIRETORIOS.items():
            if acao in acoes:
                dx, dy = ax, ay
                break
        if dx or dy:
            self._andar(dx, dy)

    def _andar(self, dx: int, dy: int) -> None:
        # com Shift o aperto vale um tile inteiro, e nao meio
        self.andamento.correndo = animacao.correndo_agora()
        passo = TILE * (
            animacao.PASSO_CORRIDA if self.andamento.correndo
            else animacao.PASSO_ANDAR
        )
        # o passo de corrida vale o dobro, entao o meio do caminho
        # tambem tem de estar livre, senao o heroi atravessa um movel
        # no meio do aperto
        if passo > TILE / 2 and not self._caminho_livre(
            self.posicao + pygame.Vector2(dx, dy) * (TILE / 2)
        ):
            passo = TILE / 2
        alvo = self.posicao + pygame.Vector2(dx * passo, dy * passo)
        # a caixa dos pes tem de caber: e o que impede o heroi de
        # encostar com metade do corpo num movel. O aviso vem daqui
        # para o jogador entender o que travou
        if not self._caminho_livre(alvo):
            self._avisar("O caminho esta fechado.", 1.8)
            return
        self.posicao = alvo
        self.moving = True
        self._recarregar(NOME_DIRECAO[(dx, dy)])

    def _caminho_livre(self, ponto: pygame.Vector2) -> bool:
        """Se a caixa dos pes do heroi cabe na planta da taverna.

        Antes eram tres celulas, uma em cada `oy`: a mesma celula do
        ponto, mais as duas de baixo. Um ponto so deixa o heroi com
        metade do corpo na parede; a caixa tem a mesma medida da
        masmorra e da aldeia, para as tres cenas darem a mesma
        sensacao.

        E o rodape do movel que importa: uma estante de tres celulas
        de altura e barrada pela celula de baixo dela, entao a caixa
        tem de ser testada contra as tres linhas de qualquer forma.
        """
        meia_l, meia_a = self._pe_do_heroi()
        fx = int((ponto.x - meia_l) // TILE)
        ax = int((ponto.x + meia_l) // TILE)
        fy = int((ponto.y - meia_a) // TILE)
        ay = int((ponto.y + meia_a) // TILE)
        for cy in range(min(fy, ay), max(fy, ay) + 1):
            for cx in range(min(fx, ax), max(fx, ax) + 1):
                if not all(amenities(cx, cy + oy) for oy in range(0, 3)):
                    return False
        return True

    def _pe_do_heroi(self) -> tuple[int, int]:
        """A caixa dos PÉS do heroi, em pixels. A mesma da masmorra."""
        arte = assets.equipado_na_tela("punho", assets.get_sprite_scale())
        if arte is None:
            return TILE // 2, TILE // 2
        return (max(4, arte.get_width() // 2),
                max(4, arte.get_height() * 3 // 20))

    def _dormir(self) -> None:
        """Dorme. Cobra, cura menos que a fogueira, e salva."""
        from .city_scene import CURA_DA_TAVERNA, PRECO_DA_TAVERNA
        if self.estado.ouro < PRECO_DA_TAVERNA:
            self._avisar(
                f"Tao Anchieta: dorme qui com {PRECO_DA_TAVERNA} de moeda.",
                3.4,
            )
            self.falando = 4.0
            return
        self.estado.ouro -= PRECO_DA_TAVERNA
        curado = self.estado.curar(CURA_DA_TAVERNA)
        self.manager.salvar_progresso()
        self._avisar(
            f"Voce dormiu. {curado} de vida de volta, "
            f"pelo preco de {PRECO_DA_TAVERNA}.", 3.6,
        )
        self.falando = 4.0

    # --- menus ---------------------------------------------------------
    def _fechar_outros_menus(self, mantem_inventario: bool = False) -> None:
        if not mantem_inventario:
            self.inventario_aberto = False
        self.modo_equip = None

    def _tecla_equip(self, event) -> None:
        conjuntos = equip_mod.todos_os_conjuntos()
        acoes = self.controls.actions_for(event.key)
        if "voltar" in acoes:
            self.modo_equip = None
            return
        if "mover_cima" in acoes:
            self.index_equip = (self.index_equip - 1) % len(conjuntos)
        elif "mover_baixo" in acoes:
            self.index_equip = (self.index_equip + 1) % len(conjuntos)
        elif "confirmar" in acoes:
            escolhido = conjuntos[self.index_equip]
            p = self.progresso
            p.arma = escolhido.arma or "espada"
            p.escudo = escolhido.escudo
            self.manager.ui_state["progresso"] = p
            self.manager.salvar_progresso()
            self.modo_equip = None

    # --- laco ----------------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        self.andamento.advance(dt, self.moving)
        if self.avisar_tempo > 0:
            self.avisar_tempo -= dt
        if self.falando > 0:
            self.falando -= dt
        if self.moving:
            self.moving = int(self.time * 8) % 2 == 0

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

    # --- desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        w, h = self.size
        # fundo de parede, nao preto: o salao e um lugar fechado e o
        # preto de fora lia como buraco no chao
        fundo = peca("parede_tijolo")
        if fundo is not None:
            lado = fundo.get_width() * 3
            lad = pygame.transform.scale(fundo, (lado, lado))
            for y in range(0, h, lado):
                for x in range(0, w, lado):
                    surface.blit(lad, (x, y))
            # escurece o fundo inteiro: a parede viva e o piso sao
            # claros demais para o resto do jogo
            sombra = pygame.Surface((w, h), pygame.SRCALPHA)
            sombra.fill((40, 30, 26, 214))
            surface.blit(sombra, (0, 0))
        else:
            surface.fill(theme.BACKGROUND)
        # a planta e pequena: centraliza em vez de camera
        largura = len(PLANTA[0]) * TILE
        altura = len(PLANTA) * TILE
        x0 = (w - largura) // 2
        y0 = (h - altura) // 2

        for y, linha in enumerate(PLANTA):
            for x, letra in enumerate(linha):
                nome_peca, _andavel, n_cols, n_lins = PECAS.get(
                    letra, ("piso_terra", True, 1, 1))
                arte = peca(nome_peca)
                destino = pygame.Rect(x0 + x * TILE, y0 + y * TILE, TILE, TILE)

                # uma peca que ocupa varias celulas e desenhada UMA vez,
                # no canto de baixo a esquerda. Sem isto o balcao de sete
                # celulas aparecia sete vezes enfileirado, e as mesas
                # viravam um colar de mesas.
                mesma_a_esq = n_cols > 1 and x > 0 and linha[x - 1] == letra
                mesma_abaixo = (
                    n_lins > 1
                    and y + 1 < len(PLANTA)
                    and PLANTA[y + 1][x] == letra
                )
                eh_canto = not (mesma_a_esq or mesma_abaixo)

                if arte is None:
                    pygame.draw.rect(
                        surface,
                        theme.BACKGROUND_SOFT if letra != "#" else (26, 20, 18),
                        destino,
                    )
                    pygame.draw.rect(surface, (18, 14, 12), destino, 1)
                    continue

                # a arte do pacote esta numa grade de 16px. A escala
                # vem dessa grade e nao da largura da peca: o balcao
                # tem 112px de largura e TILE//112 dava 1, e ele
                # aparecia com um terco do tamanho da area que ocupa
                escala = max(1, TILE // CELULA_ARTES)
                img = pygame.transform.scale(
                    arte, (arte.get_width() * escala, arte.get_height() * escala)
                )
                if letra == "#":
                    # a parede e tijolo escurecido: a cor original e
                    # laranja viva demais para uma parede de taberna
                    img = img.copy()
                    img.fill((70, 52, 46), special_flags=pygame.BLEND_RGBA_MULT)
                    surface.blit(img, destino)
                    continue

                if img.get_height() > TILE and not eh_canto:
                    # celula de apoio de uma peca grande: e o chao da
                    # sala, nao um retangulo escuro. Com o retangulo o
                    # balcao deixava um bloco preto do lado.
                    chao = peca("piso_terra")
                    if chao is not None:
                        c = pygame.transform.scale(
                            chao, (TILE, TILE))
                        surface.blit(c, destino)
                    continue
                if img.get_height() > TILE:
                    surface.blit(img, (destino.x,
                                       destino.bottom - img.get_height()))
                else:
                    surface.blit(img, destino)

        # o Tao Anchieta atras do balcao
        self._desenhar_tao(surface, x0, y0)
        # a taverna nao rola o mapa: ela centraliza a planta e pronto.
        # Mas `_desenhar_heroi_equipado` e o mesmo das outras tres
        # cenas e calcula a posicao na tela a partir de `camera`. A
        # camera daqui e a que faz a conta fechar: posicao - camera +
        # metade da janela = posicao + a origem da planta.
        self.camera = pygame.Vector2(w // 2 - x0, h // 2 - y0)
        self._desenhar_heroi_equipado(surface)

        theme.text_tracked_at(
            surface, "TAVERNA DE TAO ANCHIETA", 17, (20, 20), theme.TEXT_DIM)
        self._desenhar_inventario(surface, w, h)

        if self.avisar_tempo > 0:
            self._desenhar_aviso(surface, w, h)
        theme.text_tracked_at(
            surface, "E fala   esc sai   setas andam", 14,
            (w - 250, h - 24), theme.TEXT_DIM)

    def _desenhar_tao(self, surface: pygame.Surface, x0: int, y0: int) -> None:
        alvo = (int(self.tao.x + x0), int(self.tao.y + y0))
        arte = assets.carregar_morador(
            "taverneiro", escala=assets.get_sprite_scale())
        if arte is not None:
            surface.blit(arte, arte.get_rect(midbottom=alvo))
            altura = arte.get_height()
        else:
            pygame.draw.circle(surface, theme.GOLD, alvo, 10)
            altura = 20
        if self.falando > 0:
            pygame.draw.circle(surface, theme.GOLD, (alvo[0], alvo[1] - altura - 8), 3)
            theme.text_tracked_at(
                surface, "Tao Anchieta", 13,
                (alvo[0] - 46, alvo[1] - altura + 3), theme.GOLD)

    def _desenhar_aviso(self, surface: pygame.Surface, w: int, h: int) -> None:
        caixa = pygame.Rect(int(w * 0.16), int(h * 0.84), int(w * 0.68), 54)
        pygame.draw.rect(surface, theme.BACKGROUND_SOFT, caixa)
        pygame.draw.rect(surface, theme.GOLD, caixa, 1)
        theme.text_tracked_at(
            surface, self.avisar, 15,
            (caixa.x + 14, caixa.centery - 8), theme.TEXT)

    def _desenhar_inventario(self, surface: pygame.Surface, w: int, h: int) -> None:
        """O mesmo inventario da aldeia, sobre o salao."""
        if not self.inventario_aberto:
            return
        if self.modo_equip is not None:
            self._desenhar_equipamento(surface, w, h)
            return
        p = self.progresso
        linhas = itens_mod.rotulos(dict(p.itens) if p is not None else {})
        painel = ui_arte.desenhar(
            surface, ui_arte.PAINEL_INVENTARIO,
            (w // 2, h // 2), int(w * 0.42))
        if painel is None:
            return
        conjunto = equip_mod.Conjunto(
            p.arma if p else None, p.escudo if p else None)
        ui_arte.desenhar_inventario(
            surface, painel, linhas,
            conjunto=assets.carregar_equipado(conjunto.chave, escala=1),
            rotulo=conjunto.rotulo, ouro=self.estado.ouro,
        )
        theme.text_tracked_at(
            surface, "q ou esc fecha   r troca a arma", 13,
            (painel.x, painel.bottom + 8), theme.TEXT_DIM)

    def _desenhar_equipamento(self, surface: pygame.Surface,
                              w: int, h: int) -> None:
        conjuntos = equip_mod.todos_os_conjuntos()
        miolo = ui_arte.desenhar(
            surface, ui_arte.PAINEL_EQUIPAMENTO,
            (w // 2, h // 2), int(w * 0.34))
        if miolo is None:
            return
        linhas, passo = ui_arte.linhas_do_equipamento(miolo)
        for i, c in enumerate(conjuntos):
            if i >= len(linhas):
                break
            linha = linhas[i]
            marcado = i == self.index_equip
            if marcado:
                pygame.draw.rect(surface, theme.GOLD, linha, 1)
            arte = assets.carregar_equipado(c.chave, escala=1)
            # o boneco encolhe para a altura da linha, ou transborda
            # 46px para cima e invade a barra de EQUIPMENT
            if arte is None:
                texto_x = linha.x + 2
            else:
                pequeno = ui_arte._caber_pequeno(arte, ui_arte.lado_do_desenho(linha))
                surface.blit(pequeno, pequeno.get_rect(
                    midleft=(linha.x + 2, linha.centery)))
                texto_x = linha.x + pequeno.get_width() + 8
            theme.text_tracked_at(
                surface, c.rotulo, 13, (texto_x, linha.y + 2),
                theme.GOLD if marcado else theme.TEXT)
        theme.text_tracked_at(
            surface, "enter usa   esc volta", 12,
            (miolo.x, miolo.bottom + 6), theme.TEXT_DIM)
