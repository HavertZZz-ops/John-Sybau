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

from . import animacao, assets, cenarios, luz, rocha, settings, theme, wang
from .dungeon_map import CHAO, PAREDE, Mapa, gerar_mapa
from . import estado as estado_mod
from . import fogueira as fogueira_mod
from . import equipamento as equip_mod
from . import ui_arte
from . import itens as itens_mod
from .scene import Scene

CENARIO_CIDADE = "aldeia_wang"

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

    def __init__(self, nome: str, fala: str, dx: int, dy: int,
                 cor: tuple, sprite: str = "") -> None:
        self.nome = nome
        self.fala = fala
        self.dx = dx
        self.dy = dy
        self.cor = cor
        # o arquivo do desenho. Vazio usa o bloco colorido.
        self.sprite = sprite or nome.lower().replace(" ", "_")
        self.falando = 0.0


# Quem mora aqui. As falas sao curtas de proposito: e o lugar que
# estabelece o tom, nao um manual.
MORADORES: tuple[Morador, ...] = (
    Morador(
        "Ida", "Voce saiu andando. Quase ninguem faz isso.", -3, -1,
        (176, 148, 128), sprite="ida",
    ),
    Morador(
        "Borracha", "A masmorra e de cipo. Nao acende.", 3, -1,
        (150, 132, 116), sprite="borracha",
    ),
    Morador(
        "Ze", "Fugir nao e perder. Voltar e que e.", 0, 3,
        (162, 140, 120), sprite="ze",
    ),
    Morador(
        "Dona Mo", "Se te acharem la dentro outra vez, corre.", -2, 3,
        (186, 160, 138), sprite="dona_mo",
    ),
    # o mercador. E o unico que fala de dinheiro.
    Morador(
        "O Estranho",
        "Moeda chama moeda. E nao faco entrega a casa.",
        5, 2, (60, 56, 60), sprite="mercador",
    ),
    # o taverneiro. Descansar na taverna e outra coisa: aqui o
    # jogador paga, la ele descansa de graca. Sao dois servicos
    # diferentes e a distincao e o que da a taverna um motivo.
    Morador(
        "Tao Anchieta",
        "Cama limpa, caneca cheia. Dez de moeda a noite.",
        -6, 3, (150, 128, 104), sprite="taverneiro",
    ),
)

# quanto custa pernoitar na taverna
PRECO_DA_TAVERNA = 10
# quanto a taverna cura: menos que a fogueira, de proposito
CURA_DA_TAVERNA = 60


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



class Predio:
    """Um predio da aldeia, e quem fica na porta dele."""

    def __init__(self, sprite: str, dx: int, dy: int, quem: str = "") -> None:
        self.sprite = sprite
        self.dx = dx
        self.dy = dy
        # o morador que fica na porta deste predio
        self.quem = quem
        self.celula: tuple[int, int] | None = None


class CityScene(Scene):
    """A cidadezinha, com os moradores locales."""

    inventario_aberto = False
    modo_equip: int | None = None
    index_equip = 0

    def __init__(self, manager) -> None:
        super().__init__(manager)
        # O mapa e maior que a tela de proposito. Numa tela 1280x720
        # com tile de 32 cabem 40x22 celulas, e um mapa menor que isso
        # deixa um mar de preto em volta, que da a impressao de lugar
        # vazio em vez de aldeia.
        self.mapa: Mapa = gerar_mapa(
            largura=58, altura=34, salas=5, semente=777
        )
        self._wang: wang.GradeWang | None = None
        self.progresso = manager.ui_state.get("progresso")

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
        # A entrada do mapa fica quinze tiles a oeste do aglomerado, e
        # o jogador nascia la: o primeiro quadro da aldeia era uma
        # pedra vazia, sem morador, fogueira nem construcao. Agora ele
        # chega na borda oeste da aldeia, e ela aparece inteira.
        self.posicao = pygame.Vector2(
            self.mapa.para_pixels(
                *self._entrada_da_aldeia(), self.tile
            )
        )
        self.camera = pygame.Vector2(self.posicao)

        self.walk_frames = assets.load_animation(self.direction, "walk")
        self.idle_frames = assets.load_animation(self.direction, "idle")
        self.estado = estado_mod.do_gerenciador(self.manager)
        self.fogueira: fogueira_mod.Fogueira | None = (
            fogueira_mod.primeira_do_cenario("aldeia")
        )
        self.fogueira_pos: pygame.Vector2 | None = None
        self._colocar_fogueira()
        # Os predios ANTES dos moradores, nesta ordem exata. O
        # taverneiro fica na porta da taverna, e a porta so existe
        # depois que o predio foi colocado. Na ordem antiga a lista de
        # portas chegava vazia e o dono da taverna acabava do outro
        # lado da aldeia.
        self.predios: list[Predio] = []
        self._colocar_predios()
        self.moradores: list[Morador] = []
        self._posicionar_moradores()
        self.perto: Morador | None = None
        self.avisar = ""
        self.avisar_tempo = 0.0
        self.falas_ouvidas: set[str] = set()
        # a loja do Estranho: None = fechada, int = item em foco
        self.loja: int | None = None
        self.loja_aviso = ""

    # --- posicao dos moradores ---------------------------------------
    def _posicionar_moradores(self) -> list[Morador]:
        """Coloca cada morador num chao valido, longe dos outros.

        A distancia minima e o que importa. Com o offset de cada um
        perto do centro e o espaco curto, os seis moradores acabavam
        amontoados num circulo, e um desenho de 64px em cima do outro
        nao da para dizer quem e quem.
        """
        centro = self.mapa.centro_da_sala(2) or self.mapa.entrada
        MINIMO = 4  # celulas de distancia entre um morador e outro
        portas = {
            p.quem: p.celula for p in getattr(self, "predios", [])
            if p.quem and p.celula
        }
        for m in MORADORES:
            # quem tem predio fica NA PORTA dele. Sem isto o taverneiro
            # ends up do outro lado da aldeia, e o jogador nao sabe
            # que o dono da taverna e o dono da taverna.
            if m.nome in portas:
                px, py = portas[m.nome]
                for dy in (4, 5, 3):
                    for dx in (1, -1, 0, 2, -2):
                        celula = (px + dx, py + dy)
                        if self.mapa.andavel(*celula):
                            m.celula = celula  # type: ignore[attr-defined]
                            self.moradores.append(m)
                            break
                    if getattr(m, "celula", None) is not None:
                        break
                if getattr(m, "celula", None) is not None:
                    continue
            alvo = None
            for raio in range(0, 10):
                for dx in range(-raio, raio + 1):
                    for dy in range(-raio, raio + 1):
                        if max(abs(dx), abs(dy)) != raio:
                            continue
                        celula = (centro[0] + m.dx + dx, centro[1] + m.dy + dy)
                        if not self.mapa.andavel(*celula):
                            continue
                        perto = any(
                            abs(celula[0] - c[0]) < MINIMO
                            and abs(celula[1] - c[1]) < MINIMO
                            for c in self._celulas_ocupadas()
                        )
                        if perto:
                            continue
                        alvo = celula
                        break
                    if alvo:
                        break
                if alvo:
                    break
            if alvo is None:
                # sem lugar com folga: aceita qualquer chao valido,
                # melhor amontoado do que morador faltando
                for raio in range(0, 12):
                    for dx in range(-raio, raio + 1):
                        for dy in range(-raio, raio + 1):
                            celula = (centro[0] + dx, centro[1] + dy)
                            if self.mapa.andavel(*celula):
                                alvo = celula
                                break
                        if alvo:
                            break
                    if alvo:
                        break
            if alvo is None:
                continue
            m.celula = alvo  # type: ignore[attr-defined]
            # preenche a lista da cena, e nao uma local: a distancia
            # minima e conferida contra quem JA foi colocado, e a lista
            # local so existe no fim do metodo
            self.moradores.append(m)
        return self.moradores

    def _celulas_ocupadas(self) -> list[tuple[int, int]]:
        return [getattr(m, "celula") for m in getattr(self, "moradores", [])
                if getattr(m, "celula", None) is not None]

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

    def _entrada_da_aldeia(self) -> tuple[int, int]:
        """Onde o jogador aparece na aldeia: a oeste do aglomerado.

        Nao e a entrada do mapa. A entrada do mapa e quinze tiles a
        oeste de onde ficam os moradores, a fogueira e a taverna, e o
        primeiro quadro da cena era uma pedra vazia.
        """
        centro = self.mapa.centro_da_sala(2) or self.mapa.entrada
        melhor = (self.mapa.entrada, -1)
        # anda para oeste do centro ate achar chao andavel, sem sair da
        # sala: e o ponto de onde o jogador ve a aldeia inteira
        for raio in range(0, 12):
            for dx in range(-raio, raio + 1):
                for dy in range(-raio, raio + 1):
                    if max(abs(dx), abs(dy)) != raio:
                        continue
                    x = centro[0] - raio + dx
                    y = centro[1] + dy
                    if not self.mapa.andavel(x, y):
                        continue
                    if self.mapa.sala_de(x, y) != 2:
                        continue
                    if melhor[1] < raio:
                        melhor = ((x, y), raio)
        return melhor[0]

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
        acoes = self.controls.actions_for(event.key)

        if "voltar" in acoes:
            if self.perto is not None:
                # primeiro o Esc fecha a conversa, so depois sai da cidade
                self.perto = None
                return
            self.manager.salvar_progresso()
            self.manager.switch("road")
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

        # a loja e a unica coisa que o E nao fecha. Fechar antes de
        # comprar seria o jeito mais facil de o jogador gastar moeda
        # sem querer.
        if self.loja is not None:
            self._tecla_da_loja(acoes)
            return

        if "interagir" in acoes:
            if self._perto_da_fogueira():
                self._descansar()
                return
            if self.perto is not None:
                self.perto.falando = 4.0
                self._avisar(f"{self.perto.nome}: {self.perto.fala}", 4.0)
                self.falas_ouvidas.add(self.perto.nome)
                if self.perto.nome == "Tao Anchieta":
                    # o dono da taverna mora ATRAS do balcao. Antes
                    # ele dormia o jogador na porta da rua; agora o E
                    # na porta entra no salao e e la dentro que se
                    # dorme, que e o que uma taverna e.
                    self.manager.switch("tavern")
                    return
                if self.perto.nome == "O Estranho":
                    self._fechar_outros_menus()
                    self.loja = 0
                    self.loja_aviso = "Escolha o que quer. Esc sai sem gastar."
                    return
            elif self.avisar_tempo <= 0:
                self._avisar("Ninguem por perto. Aproxime-se de alguem.", 2.4)
            return

        for direcao, (dx, dy) in DIRECOES.items():
            acao = {"norte": "mover_cima", "sul": "mover_baixo",
                    "leste": "mover_direita", "oeste": "mover_esquerda"}[direcao]
            if acao in acoes:
                self._recarregar(direcao)
                # com Shift o aperto vale um tile inteiro, e nao meio
                self.andamento.correndo = animacao.correndo_agora()
                self.moving = True
                passo = self.tile * (
                    animacao.PASSO_CORRIDA if self.andamento.correndo
                    else animacao.PASSO_ANDAR
                )
                # o passo de corrida vale o dobro, entao so vale se o
                # MEIO do caminho estiver livre: testando so o
                # destino, o heroi aparecia do outro lado de uma
                # parede no meio do aperto
                meio = self.posicao + pygame.Vector2(dx, dy) * (self.tile / 2)
                if passo > self.tile / 2 and not self._livre(meio):
                    passo = self.tile / 2
                alvo = self.posicao + pygame.Vector2(dx * passo, dy * passo)
                if self._livre(alvo):
                    self.posicao = alvo
                self._limitar_camera()
                return

    def _pe_do_heroi(self) -> tuple[int, int]:
        """A caixa dos PÉS do heroi, em pixels.

        A mesma medida da masmorra, e pelo mesmo motivo: o que o olho ve
        e o desenho de 90px, e a colisao que mede um ponto so deixa o
        heroi com metade do corpo dentro da parede.
        """
        arte = assets.equipado_na_tela("punho", assets.get_sprite_scale())
        if arte is None:
            return self.tile // 2, self.tile // 2
        return max(4, arte.get_width() // 2), max(4, arte.get_height() * 3 // 20)

    def _livre(self, ponto: pygame.Vector2) -> bool:
        """True se a caixa dos pes do heroi cabe inteira em chao andavel.

        Antes era um ponto: o CENTRO do heroi em chao andavel, e nada
        mais. O desenho tem 90px de largura, entao ele encostava com o
        centro a uma parede e 45px do corpo ficavam na pedra.

        A altura e menor de proposito — o topo (cabeca) passa por cima
        da parede, como num jogo de plataforma. E a caixa e a mesma da
        masmorra, para as tres cenas darem a mesma sensacao.
        """
        meia_l, meia_a = self._pe_do_heroi()
        fx = int((ponto.x - meia_l) // self.tile)
        ax = int((ponto.x + meia_l) // self.tile)
        fy = int((ponto.y - meia_a) // self.tile)
        ay = int((ponto.y + meia_a) // self.tile)
        for cy in range(min(fy, ay), max(fy, ay) + 1):
            for cx in range(min(fx, ax), max(fx, ax) + 1):
                if not self.mapa.andavel(cx, cy):
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
                # `== PAREDE`, e nao `!= CHAO`. As celulas de enfeite
                # (talha, entulho, laje) sao andaveis mas nao sao
                # CHAO: com o teste antigo elas nao eram desenhadas e
                # apareciam como quadrados PRETOS no meio do chao.
                #
                # A parede e desenhada como pedra. Antes ela era
                # simplesmente pulada, e o que sobrava era a cor do
                # fundo: a aldeia parecia um retangulo de laje dentro
                # de um buraco negro, e o preto era tao parecido com
                # arte faltando que o defeito se lia como bug.
                if self.mapa.em(x, y) == PAREDE:
                    surface.blit(
                        rocha.celula(self.tile, x, y),
                        (x * self.tile + x_desenho, y * self.tile + y_desenho),
                    )
                    continue
                chave, _img = self._wang.tile_e_chave(x, y)
                surface.blit(
                    _tile(chave, self.tile),
                    (x * self.tile + x_desenho, y * self.tile + y_desenho),
                )

        self._desenhar_predios(surface, w, h, x_desenho, y_desenho)
        for m in self.moradores:
            self._desenhar_morador(surface, m, w, h, x_desenho, y_desenho)

        self._desenhar_heroi_equipado(surface)

        self._desenhar_loja(surface, w, h)
        self._desenhar_fala(surface, w, h)
        self._desenhar_fogueira(surface)
        theme.text_tracked_at(surface, "ALDEIA", 17, (20, 20), theme.TEXT_DIM)
        # a luz: mascara sobre a cena pronta. O mapa inteiro com a
        # mesma claridade e uma laje lisa; com a luz, o que esta longe
        # some e o que esta perto do heroi aparece.
        _luz = luz.Luz()
        _luz.add(
            int(self.posicao.x - self.camera.x + self.size[0] // 2),
            int(self.posicao.y - self.camera.y + self.size[1] // 2),
            int(self.tile * 6.5), luz.LUZ_HEROI,
        )
        if getattr(self, "fogueira_pos", None) is not None:
            _luz.add(
                int(self.fogueira_pos.x - self.camera.x + self.size[0] // 2),
                int(self.fogueira_pos.y - self.camera.y + self.size[1] // 2),
                int(self.tile * 8.5), luz.LUZ_FOGUEIRA,
            )
        _luz.aplicar(surface)
        self._desenhar_inventario_mundo(surface)
        theme.text_tracked_at(
            surface, "E para falar   esc para sair", 14,
            (w - 220, h - 24), theme.TEXT_DIM)

    def _desenhar_morador(self, surface, m, w, h, x_off, y_off) -> None:
        p = self._posicao_de(m)
        px = int(p.x + x_off)
        py = int(p.y + y_off)

        # o desenho quando existe; o bloco colorido quando nao
        arte = assets.carregar_morador(m.sprite, escala=assets.get_sprite_scale())
        if arte is not None:
            surface.blit(arte, arte.get_rect(midbottom=(px, py)))
        else:
            largura = max(6, self.tile // 3)
            altura = max(10, self.tile // 2)
            corpo = pygame.Rect(px - largura // 2, py - altura, largura, altura)
            pygame.draw.rect(surface, m.cor, corpo)
            pygame.draw.rect(surface, (28, 24, 22), corpo, 1)
            pygame.draw.circle(
                surface, m.cor,
                (px, corpo.top - max(2, altura // 6)),
                max(2, altura // 5),
            )

        # piscada quando esta falando
        if m.falando > 0:
            pygame.draw.circle(surface, theme.GOLD, (px, py - self.tile - 8), 3)

        theme.text_tracked_at(
            surface, m.nome, 13, (px - 18, py + 3), theme.TEXT_DIM)

    def _desenhar_fala(self, surface, w, h) -> None:
        if self.avisar_tempo <= 0 or not self.avisar:
            return
        caixa = pygame.Rect(0, 0, min(720, w - 60), 64)
        caixa.midbottom = (w // 2, h - 60)
        pygame.draw.rect(surface, theme.BACKGROUND, caixa.inflate(10, 10))
        pygame.draw.rect(surface, theme.HAIRLINE, caixa.inflate(10, 10), 1)
        theme.text_tracked_at(
            surface, self.avisar, 16, (caixa.x + 8, caixa.y), theme.TEXT)

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
    def _colocar_fogueira(self) -> None:
        """A fogueira da aldeia, perto do grupo de moradores.

        E a primeira fogueira do jogo: quem sai correndo da masmorra
        chega nela antes de qualquer outra, e e aqui que o jogador
        descobre o que e descansar.
        """
        self.fogueira_pos = None
        if self.fogueira is None:
            return
        centro = self.mapa.centro_da_sala(2) or self.mapa.entrada
        for dx, dy in ((0, -3), (3, -2), (-3, -2), (0, -4)):
            alvo = (centro[0] + dx, centro[1] + dy)
            if self.mapa.andavel(*alvo):
                self.fogueira_pos = pygame.Vector2(
                    self.mapa.para_pixels(*alvo, self.tile)
                )
                return

    def _perto_da_fogueira(self) -> bool:
        if self.fogueira_pos is None:
            return False
        return self.fogueira_pos.distance_to(self.posicao) <= fogueira_mod.ALCANCE

    def _descansar(self) -> None:
        p = self.progresso
        self.estado.descansar(fogueira_mod.POCOES_DO_DESCANSO)
        p.itens["pocao"] = p.itens.get("pocao", 0) + fogueira_mod.POCOES_DO_DESCANSO
        if self.fogueira is not None:
            self.estado.fogueira = self.fogueira.chave
        self.manager.ui_state["progresso"] = p
        self.manager.salvar_progresso()
        self._avisar("Voce descansou. Vida e pocoes repostas.", 3.2)

    def _desenhar_fogueira(self, surface: pygame.Surface) -> None:
        if self.fogueira_pos is None:
            return
        x = int(self.fogueira_pos.x - self.camera.x + self.size[0] // 2)
        y = int(self.fogueira_pos.y - self.camera.y + self.size[1] // 2)
        fogueira_mod.desenhar(surface, x, y, self.tile, self.time)
        if self._perto_da_fogueira():
            theme.text_tracked_at(
                surface, "E para descansar", 13, (x - 40, y - self.tile - 6),
                theme.GOLD)

    # --- a taverna ---------------------------------------------------
    def _pernoitar(self) -> None:
        """Dorme na taverna: paga, e cura menos que a fogueira.

        A fogueira e de graca e cura tudo. A taverna cobra e cura
        menos. Se as duas fossem iguais, a fogueira seria de graca e
        mais forte, e a taverna nao teria para que existir.
        """
        if self.estado.ouro < PRECO_DA_TAVERNA:
            self._avisar(
                f"Tao Anchieta: dorme qui com {PRECO_DA_TAVERNA} de moeda.",
                3.4,
            )
            return
        self.estado.ouro -= PRECO_DA_TAVERNA
        curado = self.estado.curar(CURA_DA_TAVERNA)
        self.manager.salvar_progresso()
        self._avisar(
            f"Voce dormiu. {curado} de vida de volta, "
            f"pelo preco de {PRECO_DA_TAVERNA}.",
            3.6,
        )

    # --- a loja do Estranho -------------------------------------------
    def _tecla_da_loja(self, acoes) -> None:
        lista = itens_mod.a_venda()
        if not lista:
            self.loja = None
            return
        if "voltar" in acoes:
            self.loja = None
            self.loja_aviso = ""
            return
        if "mover_cima" in acoes:
            self.loja = (self.loja - 1) % len(lista)
        elif "mover_baixo" in acoes:
            self.loja = (self.loja + 1) % len(lista)
        elif "interagir" in acoes or "confirmar" in acoes:
            item = lista[self.loja]
            inv = self.progresso.itens if self.progresso is not None else {}
            deu, aviso = itens_mod.comprar(inv, self.estado.ouro, item.id)
            if deu:
                self.estado.ouro -= item.preco
                self.manager.ui_state["progresso"] = self.progresso
                self.manager.salvar_progresso()
            self.loja_aviso = aviso

    def _desenhar_loja(self, surface, w, h) -> None:
        """A vitrine do Estranho, nos slots que a propria arte tem.

        A folha SHOP traz seis slots, seis botoes BUY e o contador de
        moeda, e nada disso muda: o jogo tem duas pocas e uma moeda.
        O que o codigo coloca e o CONTEUDO de cada slot, e a posicao dos
        slots nao e adivinhada â€” `ui_arte.slots_da_loja` devolve os
        retangulos medidos com `tools/medir_loja.py`.

        A versao anterior desenhava as linhas por cima da arte, e o
        jogador nao via nem o item nem o botao dele.
        """
        if self.loja is None:
            return
        lista = itens_mod.a_venda()
        if not lista:
            return
        # topo_rel menor que o do inventario: nesta folha os slots
        # comecam em 10% da altura, e nao nos 24% da barra de titulo
        painel = ui_arte.desenhar(
            surface, ui_arte.PAINEL_LOJA,
            (w // 2, h // 2), int(w * 0.34),
            topo_rel=0.10, base_rel=0.94,
        )
        if painel is None:
            return

        slots = ui_arte.slots_da_loja(painel, 6)
        for i, item in enumerate(lista):
            if i >= len(slots):
                break
            slot = slots[i]
            marcado = i == self.loja
            pygame.draw.rect(surface, theme.BACKGROUND_SOFT, slot)
            pygame.draw.rect(
                surface, theme.GOLD if marcado else theme.HAIRLINE, slot, 1)

            # o nome ocupa duas linhas: a primeira palavra e o resto. O corte e
            # medido com a fonte do jogo, e nao por numero de
            # caracteres: o slot tem 57px e "de cura maior" truncado em
            # 12 caracteres ainda passava da borda
            palavras = item.nome.split()
            cor = theme.GOLD if marcado else theme.TEXT
            util = slot.width - 8
            theme.text_tracked_at(
                surface, ui_arte.caber_texto(palavras[0], util, 12), 12,
                (slot.x + 4, slot.y + 4), cor)
            resto = " ".join(palavras[1:])
            if resto:
                theme.text_tracked_at(
                    surface, ui_arte.caber_texto(resto, util, 10), 10,
                    (slot.x + 4, slot.y + 20), theme.TEXT_DIM)

            # o preco fica no canto do SLOT, e nao em cima do BUY: o
            # botao ja tem a palavra BUY desenhada na arte e o numero
            # por cima dela virava "BU I"
            pode = self.estado.ouro >= item.preco
            cor_preco = theme.GOLD if (marcado and pode) else theme.TEXT_DIM
            theme.text_tracked_at(
                surface, f"{item.preco}", 12,
                (slot.right - 30, slot.bottom - 16), cor_preco)

            # o botao so acende junto com o item escolhido
            botao = ui_arte.botao_da_loja(painel, i)
            if marcado and botao is not None:
                pygame.draw.rect(surface, theme.GOLD, botao, 2)

        # o contador e da faixa de baixo do miolo, e nao do miolo inteiro: a
        # loja usa `base_rel` menor, e com o miolo inteiro o numero
        # caia abaixo do desenho da moeda
        _, faixa_rodape = ui_arte._cabe(painel)
        ui_arte.contador_de_moeda(surface, faixa_rodape, self.estado.ouro)
        rodape = self.loja_aviso or "enter compra   esc sai   setas mudam"
        theme.text_tracked_at(
            surface, rodape, 12, (painel.x, painel.bottom + 8),
            theme.GOLD if self.loja_aviso else theme.TEXT_DIM)
    def _colocar_predios(self) -> None:
        """Coloca a taverna longe da fogueira, e nao em cima dela.

        O predio e grande: uns 4 tiles. Se ele cair em cima da
        fogueira, o jogador ve o telhado e nao ve a brasa, e o lugar
        seguro do jogo some atras da architecture.
        """
        self.predios = []
        pedidos = (
            Predio("taverna", -8, -4, quem="Tao Anchieta"),
        )
        centro = self.mapa.centro_da_sala(2) or self.mapa.entrada
        for p in pedidos:
            alvo = None
            for raio in range(0, 14):
                for dx in range(-raio, raio + 1):
                    for dy in range(-raio, raio + 1):
                        if max(abs(dx), abs(dy)) != raio:
                            continue
                        x = centro[0] + p.dx + dx
                        y = centro[1] + p.dy + dy
                        if not self._livre_para_predio(x, y):
                            continue
                        alvo = (x, y)
                        break
                    if alvo:
                        break
                if alvo:
                    break
            if alvo is None:
                continue
            p.celula = alvo
            self.predios.append(p)

    def _livre_para_predio(self, x: int, y: int) -> bool:
        """Cabe um predio de 4x4 tiles aqui, longe da fogueira?"""
        for dy in range(4):
            for dx in range(4):
                if not self.mapa.andavel(x + dx, y + dy):
                    return False
        if self.fogueira_pos is None:
            return True
        centro_predio = (x + 2, y + 2)
        perto = pygame.Vector2(
            self.mapa.para_pixels(*centro_predio, self.tile)
        )
        return perto.distance_to(self.fogueira_pos) > self.tile * 4

    def _desenhar_predios(self, surface, w, h, x_off, y_off) -> None:
        """O predio e desenhado DEPOIS do chao e ANTES dos moradores.

        A ordem importa duas vezes. Depois do chao, senao o telhado
        ficaria sob o calÃ§amento. Antes dos moradores, senao o
        taverneiro apareceria desenhado por cima do telhado em vez de
        estar na porta.
        """
        for p in self.predios:
            if p.celula is None:
                continue
            px = int(p.celula[0] * self.tile + x_off)
            py = int(p.celula[1] * self.tile + y_off)
            arte = assets.carregar_casa(
                p.sprite, escala=max(1, assets.get_sprite_scale() - 1)
            )
            if arte is not None:
                surface.blit(arte, arte.get_rect(topleft=(px, py)))
            else:
                # sem o desenho: um volume de madeira, para o lugar
                # continuar sendo um lugar
                lado = self.tile * 4
                corpo = pygame.Rect(px, py, lado, lado - self.tile // 2)
                pygame.draw.rect(surface, (74, 56, 42), corpo)
                pygame.draw.rect(surface, (34, 26, 20), corpo, 2)
                pygame.draw.rect(
                    surface, (48, 36, 27),
                    pygame.Rect(px + 4, py + 4, lado - 8, lado // 3),
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

