"""Primeiro cenario: as Catacumbas.

O jogo abre com o heroi dentro de um caixao de pedra. A tampa range e
desliza, ele sai andando, e o nome do lugar aparece no alto, do jeito
que o Dark Souls avisa que voce chegou num lugar novo.

A cena cuida de tres coisas:
  - desenhar a masmorra com camera que segue o jogador
  - a sequencia de abertura (acordar, abrir, sair)
  - o movimento livre depois que ele saiu
"""
from __future__ import annotations

import pygame

from . import assets, coffin, settings, theme
from .area_title import AreaTitle
from .dungeon_map import (
    ENFEITES,
    PAREDE,
    TILES_CHAO,
    TILES_PAREDE,
    Mapa,
    gerar_mapa,
)
from .scene import Scene
from .tutorial import TUTORIAL_CATACUMBAS
from .ui import formatar_tempo

# direcao -> acao do mapa de teclas
DIRECTION_ACTIONS = {
    "sul": "mover_baixo",
    "norte": "mover_cima",
    "leste": "mover_direita",
    "oeste": "mover_esquerda",
}
ACoes = {v: k for k, v in DIRECTION_ACTIONS.items()}

# tamanho do tile no tileset original; a tela usa tile * escala de sprite
TILE_BASE = 16
MOVE_SPEED = 190.0

# a que distancia o esqueleto acorda e a luta comeca
ALCANCE_LUTA = 46
# quantas vezes o jogador tem de andar para o esqueleto aparecer
PASSOS_ATE_O_ESQUELETO = 14

# fases da abertura, em segundos
FASE_DURADA = {
    "acordando": 2.0,
    "abrindo": 1.4,
    "saindo": 1.6,
}

NOME_AREA = "Catacumbas"
SUBTITULO_AREA = "onde os ossos descansam"

# o tileset e lido uma vez e reaproveitado por todas as instancias
_TILESET: pygame.Surface | None = None


def _tileset() -> pygame.Surface | None:
    """Tileset carregado, com a paleta ajustada para pedra fria.

    O tileset original e bem roxo e saturado. Deixado como esta, a
    masmorra parece um level de plataforma colorida, e nao uma
    catacumba. Converter para luminancia e dar um tom levemente azulado
    deixa tudo em pedra cinza fria, que e a paleta do resto do jogo.

    O ajuste e feito uma vez e o resultado fica em cache, entao o
    custo por quadro e zero.
    """
    global _TILESET
    if _TILESET is not None:
        return _TILESET
    caminho = settings.TILES_DIR / "dungeon_tileset.png"
    if not caminho.is_file():
        return None
    try:
        _TILESET = _classificar(assets._load_image(caminho))
    except (pygame.error, OSError) as exc:
        print(f"[dungeon] tileset ausente: {exc}")
        return None
    return _TILESET


def _classificar(surface: pygame.Surface) -> pygame.Surface:
    """Tira a saturacao e puxa para o cinza azulado das catacumbas."""
    img = surface.convert()
    w, h = img.get_size()
    for y in range(h):
        for x in range(w):
            r, g, b, a = img.get_at((x, y))
            if a == 0:
                continue
# luminancia com os pesos perceptualmente aproximados
            cinza = 0.299 * r + 0.587 * g + 0.114 * b
            # Curva de contraste forte. O veu da masmorra escurece a
            # tela inteira, e sem acentuar o chao e a parede chegam
            # quase iguais no fim: a tela inteira vira um campo escuro
            # sem leitura. Afastar os claros do meio da escala e o que
            # faz o desenho do tileset voltar a aparecer.
            cinza = (cinza - 92.0) * 2.05 + 92.0
            cinza = max(0.0, min(255.0, cinza))
            v = 6 + cinza * 1.02
            if v > 210:
                v = 210
            img.set_at(
                (x, y),
                (int(v * 0.93), int(v * 0.96), int(v * 1.0), a),
            )
    return img


# o veu de luz e caro de montar, entao fica em cache e e REAPROVEITADO:
# fazer `.copy()` de uma tela 1520x921 a cada quadro custava caro demais
_VEU: pygame.Surface | None = None
_VEU_TAM: tuple[int, int] = (0, 0)


def _veu(w: int, h: int) -> pygame.Surface:
    """Tela escurecida, reusada a cada quadro (blit nao altera a origem)."""
    global _VEU, _VEU_TAM
    if _VEU is None or _VEU_TAM != (w, h):
        _VEU = pygame.Surface((w, h), pygame.SRCALPHA)
        _VEU.fill((8, 8, 13, 120))
        _VEU_TAM = (w, h)
    return _VEU


def _desenhar_luz(self, surface: pygame.Surface) -> None:
        """Escuridao, com uma clara ao redor do heroi.

        E o que separa "masmorra" de "tabuleiro". Tres tentativas antes
        desta, e todas erradas por um motivo diferente:

        1. aneis concentricos desenhando alfa zero: nao apaga nada, a
           tela ficava preta
        2. um gradiente radial smoothscale de uma surface com alpha por
           pixel: o smoothscale PERDE o alpha e devolveu um QUADRADO
           opaco. Era o retangulo preto em volta do jogador
        3. um segundo circulo "quente" por cima: borda dura, aparecia
           como um disco colado no chao

        O caminho que funciona e guardar a REGIAO CLARA antes de
        escurecer, e restaura-la em aneis do maior para o menor com
        opacidade crescente. Sem alpha sobreposto, sem costura: o
        degrade sai da propria sobreposicao das aneis.
        """
        w, h = self.size
        cx = int(self.posicao.x - self.camera.x + w // 2)
        cy = int(self.posicao.y - self.camera.y + h // 2)
        raio = int(self.tile * 5.5)

        # o quanto da tela a luz alcança
        metade = min(raio, min(cx, cy, w - cx, h - cy) + raio)
        if metade <= 8:
            surface.blit(_veu(w, h), (0, 0))
            return

        # 1. guarda a regiao clara (com o mapa e o hero ja desenhados)
        claro = surface.subsurface(
            pygame.Rect(cx - metade, cy - metade, metade * 2, metade * 2)
        ).copy()

        # 2. escurece a tela inteira
        surface.blit(_veu(w, h), (0, 0))

        # 3. restaura a luz em aneis, do maior para o menor. Cada anel
        # devolve um pouco da clareza; a soma das aneis faz o degrade.
        # O recorte ja vem do tamanho certo: dar `transform.scale` com
        # origem e destino iguais parece inofensivo e nao e, porque o
        # pygame ainda copia a surface inteira toda vez.
        aneis = 12
        for i in range(aneis, 0, -1):
            t = i / aneis
            r = int(metade * t)
            if r < 2:
                continue
            alfa = int(246 * (1.0 - t) ** 0.7) + 10
            if alfa > 255:
                alfa = 255
            recorte = claro.subsurface(
                pygame.Rect(metade - r, metade - r, r * 2, r * 2)
            )
            recorte = recorte.copy()
            recorte.set_alpha(alfa)
            surface.blit(recorte, (cx - r, cy - r))


# tiles ja ampliados para o tamanho de tela, cacheados por coordenada.
# A versao anterior escalava CADA tile visivel a CADA quadro: numa tela
# 1520x921 sao mais de 600 tiles, e 600 `pygame.transform.scale` por
# quadro era o suficiente para derrubar o jogo para metade da
# velocidade. O tileset e estatico, entao ampliar uma vez e guardar.
_TILES_ESCALADOS: dict[tuple[int, int], pygame.Surface] = {}
_TILES_ESCALA = -1


def _tile_escalado(tileset: pygame.Surface, indice: tuple[int, int], tamanho: int) -> pygame.Surface:
    """Peca do tileset ja no tamanho de tela, em cache."""
    global _TILES_ESCALA
    if tamanho != _TILES_ESCALA:
        _TILES_ESCALADOS.clear()
        _TILES_ESCALA = tamanho
    pega = _TILES_ESCALADOS.get(indice)
    if pega is not None:
        return pega
    pedaco = tileset.subsurface(
        pygame.Rect(indice[0] * TILE_BASE, indice[1] * TILE_BASE,
                    TILE_BASE, TILE_BASE)
    )
    if tamanho != TILE_BASE:
        pedaco = pygame.transform.scale(pedaco, (tamanho, tamanho))
    _TILES_ESCALADOS[indice] = pedaco
    return pedaco


class DungeonScene(Scene):
    """As Catacumbas, com a entrada pelo caixao."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.mapa: Mapa = gerar_mapa()
        self.direction = "sul"
        self.moving = False
        self.anim_time = 0.0
        self.time = 0.0

        self.walk_frames = assets.load_animation(self.direction, "walk")
        self.idle_frames = assets.load_animation(self.direction, "idle")

        self.tile = TILE_BASE * assets.get_sprite_scale()
        self.posicao = pygame.Vector2(self._centro_caixao())
        self.camera = pygame.Vector2(self.posicao)

        self.tampa = 0.0  # 0 fechada, 1 aberta
        self.titulo = AreaTitle()
        self._titulo_mostrado = False

        self.tempo_jogado = 0.0
        self.aviso = ""
        self._aviso_tempo = 0.0

        # as aulas do comeco. `resetar` e obrigatorio: TUTORIAL_CATACUMBAS
        # e um objeto de modulo, e sem isso o estado da aula anterior
        # vazaria para esta partida
        self.tutorial = TUTORIAL_CATACUMBAS
        self.tutorial.resetar()

        # o esqueleto fica guardado dormindo ate a hora certa
        self.esqueleto: pygame.Vector2 | None = None
        self.esqueleto_vivo = False
        # quadros do esqueleto, carregados uma vez
        self._quadros_esqueleto: list | None = None
        self.passos = 0
        self.acabou_aula_de_mover = False
        # qual acao o jogador apertou neste quadro. E o que fecha as
        # aulas: o tutorial precisa saber que o jogador DEU o comando,
        # nao so que a tecla exists
        self._acao_deste_quadro: str | None = None

        # um save vindo do menu pula a abertura: o jogador ja acordou
        # uma vez e nao faz sentido ver o caixao toda vez que continua
        carregado = manager.ui_state.get("save_carregado")
        if carregado is not None:
            self._aplicar_save(carregado)
        else:
            self.fase = "acordando"
            self.fase_tempo = 0.0

    # --- save --------------------------------------------------------
    def para_save(self):
        """Estado da cena, no formato que o store sabe gravar."""
        from .saves import Save

        return Save(
            area="catacumbas",
            x=float(self.posicao.x),
            y=float(self.posicao.y),
            direcao=self.direction,
            tempo_jogado=self.tempo_jogado,
        )

    def _aplicar_save(self, save) -> None:
        """Coloca o jogador onde ele parou, sem a abertura."""
        self.fase = "livre"
        self.fase_tempo = 0.0
        self.tampa = 1.0
        self.tempo_jogado = max(0.0, float(getattr(save, "tempo_jogado", 0.0)))
        direcao = getattr(save, "direcao", "sul")
        if direcao in DIRECTION_ACTIONS:
            self._recarregar(direcao)
        self.posicao = pygame.Vector2(
            float(getattr(save, "x", 0.0)), float(getattr(save, "y", 0.0))
        )
        # um save com posicao 0,0 (ou de outra versao) cai no caixao,
        # em vez de deixar o jogador preso dentro da parede
        if not self._livre(self.posicao, max(4, self.tile // 6)):
            self.posicao = pygame.Vector2(self._centro_caixao())
        self.posicao = self._sem_bater(self.posicao, pygame.Vector2())
        self.camera = pygame.Vector2(self.posicao)
        self.moving = False
        # o nome do lugar aparece igual: quem chega numa area nova ou
        # quem volta para ela precisa saber onde esta
        self.titulo.show(NOME_AREA, SUBTITULO_AREA)
        self._titulo_mostrado = True

    def _avisar(self, texto: str, segundos: float = 2.4) -> None:
        self.aviso = texto
        self._aviso_tempo = segundos

    # --- posicoes ---------------------------------------------------
    def _centro_caixao(self) -> tuple[float, float]:
        cx, cy = self.mapa.caixao
        return self.mapa.para_pixels(cx, cy, self.tile)

    def _celula(self) -> tuple[int, int]:
        return (int(self.posicao.x // self.tile), int(self.posicao.y // self.tile))

    @property
    def frames(self) -> list[pygame.Surface]:
        return self.walk_frames if self.moving else self.idle_frames

    def _recarregar(self, direcao: str) -> None:
        self.direction = direcao
        self.walk_frames = assets.load_animation(direcao, "walk")
        self.idle_frames = assets.load_animation(direcao, "idle")

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        """Recalcula o tamanho do tile se a escala mudou nas opcoes."""
        novo_tile = TILE_BASE * assets.get_sprite_scale()
        if novo_tile != self.tile:
            # so agora vale reposicionar. Fazer isso em toda entrada
            # arredondava a posicao para o centro do tile, e o jogador
            # voltava um meio tile deslocado de onde o save dizia
            celula_x, celula_y = self._celula()
            self.tile = novo_tile
            self.posicao = pygame.Vector2(
                celula_x * self.tile + self.tile / 2,
                celula_y * self.tile + self.tile / 2,
            )
            self.posicao = self._sem_bater(self.posicao, pygame.Vector2())
            self.camera = pygame.Vector2(self.posicao)
        self._recarregar(self.direction)
        if self._quadros_esqueleto is not None:
            # a escala dos sprites mudou: recarrega
            self._quadros_esqueleto = None

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        # soltar a direcao e tratado antes do filtro de KEYDOWN: senao o
        # KEYUP nunca chega aqui e o heroi fica andando sozinho
        if event.type == pygame.KEYUP:
            if self.fase == "livre" and self.controls.pressed(
                event.key, DIRECTION_ACTIONS[self.direction]
            ):
                self.moving = False
            return

        if event.type != pygame.KEYDOWN:
            return

        if self.key(event, "salvar"):
            self._acao_deste_quadro = "salvar"
            if self.fase != "livre":
                return
            if self.manager.salvar_progresso():
                self._avisar("Jogo salvo")
            else:
                self._avisar("Falha ao salvar")
            return

        if self.key(event, "voltar"):
            self._acao_deste_quadro = "voltar"
            if self.fase == "livre":
                # volta ja salvando: o botao de voltar e o caminho mais
                # comum para sair, e nao salvar ali perde o progresso
                self.manager.salvar_progresso()
            self.manager.switch("title")
            return

        if self.fase != "livre":
            return
        for direcao, acao in DIRECTION_ACTIONS.items():
            if self.key(event, acao):
                self._acao_deste_quadro = acao
                if direcao != self.direction:
                    self._recarregar(direcao)
                self.moving = True

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        self.tempo_jogado += dt
        # a acao so vale por um quadro; o tutorial le e esquece
        self._acao_do_quadro = self._acao_deste_quadro
        self._acao_deste_quadro = None

        # o titulo da area corre sempre, e nao so durante a abertura: a
        # abertura acaba em 5s e o titulo so termina em 6.6s, entao
        # atualizar so dentro dela deixava o nome congelado no alto,
        # meio apagado, para sempre
        self.titulo.update(dt)

        if self._aviso_tempo > 0.0:
            self._aviso_tempo -= dt
            if self._aviso_tempo <= 0.0:
                self.aviso = ""

        if self.fase != "livre":
            self._atualizar_abertura(dt)
            self.tutorial.update(dt)
            return

        self._acao_do_quadro = self._acao_deste_quadro
        if self.moving:
            self.posicao = self._sem_bater(self.posicao, self._passo(dt))
            self.anim_time += dt
            self.passos += 1
        self.camera += (self.posicao - self.camera) * min(1.0, dt * 8.0)

        self._atualizar_esqueleto(dt)
        self.tutorial.update(dt, self._acao_do_quadro)

    def _atualizar_esqueleto(self, dt: float) -> None:
        """Acorda o esqueleto depois de alguns passos e chama a luta.

        O esqueleto fica guardado parado ate a hora: acorda-lo junto com
        a abertura transformaria a primeira luta numa emboscada, e o
        jogador nem teriaandedado ainda.
        """
        if self.esqueleto is None:
            if self.passos >= PASSOS_ATE_O_ESQUELETO:
                casa = self._casa_do_esqueleto()
                if casa is not None:
                    self.esqueleto = pygame.Vector2(
                        self.mapa.para_pixels(*casa, self.tile)
                    )
                    self.esqueleto_vivo = True
                    self.tutorial.mostrar("O esqueleto acordou")
            return

        if not self.esqueleto_vivo:
            return
        # so a luta apaga o esqueleto. Antes, cair no fim da funcao
        # depois do teste de distancia o apagava em TODO quadro, e ele
        # vivia exatamente um quadro: nascia e sumia antes de o jogador
        # chegar perto. O teste antigo nao pegou porque conferia logo
        # apos o nascimento.
        if self.esqueleto.distance_to(self.posicao) < ALCANCE_LUTA:
            self.esqueleto_vivo = False
            self.manager.iniciar_combate(1)
        return

    def _casa_do_esqueleto(self) -> tuple[int, int] | None:
        """Um tile de chao para o esqueleto ficar, longe do caixao.

        Um deslocamento fixo nao funciona: a sala do caixao tem tamanho
        variavel e muitas vezes as tres casas a leste sao parede. Sem
        essa busca o esqueleto nunca acordava, e o tutorial ficava
        travado na aula de combate.
        """
        cx, cy = self.mapa.caixao
        melhor = None
        for raio in range(2, 7):
            for dx in range(-raio, raio + 1):
                for dy in range(-raio, raio + 1):
                    # um anel, nao o quadrado todo
                    if max(abs(dx), abs(dy)) != raio:
                        continue
                    alvo = (cx + dx, cy + dy)
                    if not self.mapa.andavel(*alvo):
                        continue
                    if melhor is None:
                        melhor = alvo
        return melhor

    def _passo(self, dt: float) -> pygame.Vector2:
        passo = MOVE_SPEED * dt
        return {
            "sul": pygame.Vector2(0, passo),
            "norte": pygame.Vector2(0, -passo),
            "leste": pygame.Vector2(passo, 0),
            "oeste": pygame.Vector2(-passo, 0),
        }[self.direction]

    def _atualizar_abertura(self, dt: float) -> None:
        """Maquina de estados da saida do caixao."""
        self.fase_tempo += dt
        duracao = FASE_DURADA[self.fase]

        if self.fase == "acordando":
            # o caixao treme no fim: e o aviso de que algo se moveu
            self.tampa = min(0.12, self.fase_tempo * 0.06)
            if self.fase_tempo > 1.0:
                amplitude = 2.0 * assets.get_sprite_scale() / 3
                self.camera.x += amplitude * (1 if int(self.time * 18) % 2 else -1)
            if self.fase_tempo >= duracao:
                self.fase = "abrindo"
                self.fase_tempo = 0.0

        elif self.fase == "abrindo":
            self.tampa = 0.12 + 0.88 * (self.fase_tempo / duracao)
            # show() reinicia o relogio: so na primeira vez, senao o
            # titulo nunca chegaria ao fim
            if not self._titulo_mostrado:
                self.titulo.show(NOME_AREA, SUBTITULO_AREA)
                self._titulo_mostrado = True
            if self.fase_tempo >= duracao:
                self.fase = "saindo"
                self.fase_tempo = 0.0

        elif self.fase == "saindo":
            # sai andando para o sul, de dentro do caixao. A colisao
            # vale aqui tambem: sem ela o heroi andava reto e atravessava
            # a parede da sala, acordando de pe DENTRO dela
            self.tampa = 1.0
            self._recarregar("sul")
            self.posicao = self._sem_bater(
                self.posicao,
                pygame.Vector2(0, MOVE_SPEED * 0.55 * dt),
            )
            self.anim_time += dt
            self.moving = True
            self.camera += (self.posicao - self.camera) * min(1.0, dt * 6.0)
            if self.fase_tempo >= duracao:
                self.fase = "livre"
                self.fase_tempo = 0.0
                self.moving = False

    def _sem_bater(self, pos: pygame.Vector2, delta: pygame.Vector2) -> pygame.Vector2:
        """Aplica o movimento um eixo por vez, para deslizar na parede.

        Testar o deslocamento inteiro de uma vez trava o jogador na
        parede em diagonal: ele encosta na parede norte e nao sobe mais
        nem para o lado.
        """
        raio = max(4, self.tile // 6)
        novo = pos + delta

        alvo = pygame.Vector2(novo.x, pos.y)
        if not self._livre(alvo, raio):
            alvo.x = pos.x

        alvo.y = novo.y
        if not self._livre(alvo, raio):
            alvo.y = pos.y
        return alvo

    def _livre(self, pos: pygame.Vector2, raio: int) -> bool:
        """True se um circulo de raio `raio` nao cruza nenhuma parede.

        `pos` e em coordenadas de MAPA (pixels do mundo), nao de tela.
        Passar por `_tela_para_mapa` aqui descontaria a camera duas
        vezes e a colisao checaria tiles errados: o jogador andava
        atravessando parede e o teste pegava exatamente isso.
        """
        fx = int((pos.x - raio) // self.tile)
        fy = int((pos.y - raio) // self.tile)
        ax = int((pos.x + raio) // self.tile)
        ay = int((pos.y + raio) // self.tile)
        for cy in range(min(fy, ay), max(fy, ay) + 1):
            for cx in range(min(fx, ax), max(fx, ax) + 1):
                if self.mapa.em(cx, cy) == PAREDE:
                    return False
        return True

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((12, 11, 10))
        self._limitar_camera()
        self._desenhar_mapa(surface)
        self._desenhar_saida(surface)

        escala = assets.get_sprite_scale()
        cx, cy = self._centro_caixao()

        heroi_visivel = self.fase in ("saindo", "livre")
        # com a tampa meio fechada ela passa NA FRENTE do heroi: e isso
        # que faz parecer que ele sai de dentro do caixao
        tampa_à_frente = self.tampa < 0.55
        if not tampa_à_frente:
            self._desenhar_caixao(surface, (cx, cy), escala)
        if heroi_visivel:
            self._desenhar_heroi(surface)
        if tampa_à_frente:
            self._desenhar_caixao(surface, (cx, cy), escala)

        self._desenhar_hud(surface)
        if self.esqueleto is not None:
            self._desenhar_esqueleto(surface)
        self.titulo.draw(surface)
        self._desenhar_aula(surface)
        if self.aviso:
            theme.text_tracked(
                surface, self.aviso, int(self.size[1] * 0.030),
                (self.size[0] // 2, int(self.size[1] * 0.76)), theme.GOLD,
                tracking=3,
            )

        if self.fase == "acordando" and self.fase_tempo < 0.8:
            theme.fade_surface(surface, int(255 * (1 - self.fase_tempo / 0.8)))

    def _tela_para_mapa(self, ponto: tuple[int, int]) -> tuple[int, int]:
        """Converte coordenada de tela em coordenada de tile."""
        w, h = self.size
        return (
            int((ponto[0] + self.camera.x - w // 2) // self.tile),
            int((ponto[1] + self.camera.y - h // 2) // self.tile),
        )

    def _limitar_camera(self) -> None:
        """Prende a camera dentro do mapa.

        Sem isso, quando a camera segue o jogador ate uma borda, sobra
        metade da tela fora do mapa: o preto do fundo aparece embaixo e
        da para ver que a masmorra "acabou" no meio da cena.
        """
        w, h = self.size
        largura_mapa = self.mapa.largura * self.tile
        altura_mapa = self.mapa.altura * self.tile
        if largura_mapa <= w:
            self.camera.x = largura_mapa / 2
        else:
            self.camera.x = min(max(self.camera.x, w / 2),
                                largura_mapa - w / 2)
        if altura_mapa <= h:
            self.camera.y = altura_mapa / 2
        else:
            self.camera.y = min(max(self.camera.y, h / 2),
                                altura_mapa - h / 2)

    def _desenhar_mapa(self, surface: pygame.Surface) -> None:
        tileset = _tileset()
        if tileset is None:
            theme.text_tracked_at(
                surface,
                "tileset ausente: rode tools/import_sprites.py", 18,
                (20, 20), theme.TEXT_DIM,
            )
            return

        w, h = self.size
        x0, y0 = self._tela_para_mapa((0, 0))
        x1, y1 = self._tela_para_mapa((w, h))
        x_desenho = w // 2 - self.camera.x - self.tile // 2
        y_desenho = h // 2 - self.camera.y - self.tile // 2

        # os tiles sao filtrados antes do desenho: dois em cada direcao,
        # por causa da sombra da parede
        for y in range(max(0, y0 - 1), min(self.mapa.altura, y1 + 2)):
            linha = y * self.tile + y_desenho
            for x in range(max(0, x0 - 1), min(self.mapa.largura, x1 + 2)):
                celula = self.mapa.em(x, y)
                if celula == PAREDE:
                    indice = TILES_PAREDE[(x * 2 + y) % len(TILES_PAREDE)]
                elif celula in ENFEITES:
                    indice = ENFEITES[celula]
                else:
                    indice = TILES_CHAO[(x * 3 + y * 5) % len(TILES_CHAO)]
                surface.blit(
                    _tile_escalado(tileset, indice, self.tile),
                    (x * self.tile + x_desenho, linha),
                )

        self._desenhar_sombras_das_paredes(surface, x_desenho, y_desenho)
        self._desenhar_luz(surface)

    def _desenhar_sombras_das_paredes(
        self, surface: pygame.Surface, x_off: int, y_off: int
    ) -> None:
        """Sombra da parede caindo no chao, na borda de cima.

        Sem isso o chao e a parede se encostam sem profundidade nenhuma.
        A sombra sai da parede para o chao logo abaixo dela, que e a
        mesma luz que ja estava nos tijolos.
        """
        altura = max(3, self.tile // 5)
        for y in range(self.mapa.altura):
            for x in range(self.mapa.largura):
                if self.mapa.em(x, y) == PAREDE:
                    continue
                if self.mapa.em(x, y - 1) != PAREDE:
                    continue
                px = x * self.tile + x_off
                py = y * self.tile + y_off
                sombra = pygame.Surface((self.tile, altura), pygame.SRCALPHA)
                sombra.fill((0, 0, 0, 120))
                surface.blit(sombra, (px, py))

    def _desenhar_luz(self, surface: pygame.Surface) -> None:
        """Escuridao, com uma clara ao redor do heroi.

        E o que separa "masmorra" de "tabuleiro". A tela toda recebe um
        veu escuro e a mascara radial abre um buraco ao redor do
        jogador; fora do alcance da tocha, o mapa some.
        """
        w, h = self.size
        cx = int(self.posicao.x - self.camera.x + w // 2)
        cy = int(self.posicao.y - self.camera.y + h // 2)
        raio = int(self.tile * 7.0)

        # veu base: cobre ate onde a luz nao alcanca
        surface.blit(_veu(w, h), (0, 0))

        # Nao ha um segundo circulo "quente" por cima: desenhado com
        # draw.ellipse ele sai com borda dura e aparece como um disco
        # colado no chao. O proprio gradiente ja e levemente quente,
        # entao o brilho da tocha fica na mesma curva e nao tem costura.

    def _desenhar_caixao(self, surface, centro, escala) -> None:
        w, h = self.size
        px = centro[0] - self.camera.x + w // 2
        py = centro[1] - self.camera.y + h // 2
        coffin.draw_coffin(surface, (px, py), 0.0, escala)
        coffin.draw_lid(
            surface,
            (px, py - coffin.COFFIN_H * escala // 4),
            self.tampa,
            escala,
        )

    def _desenhar_heroi(self, surface: pygame.Surface) -> None:
        quadros = self.frames
        if not quadros:
            return
        indice = int(self.anim_time * assets.HERO_FPS) % len(quadros)
        sprite = quadros[indice]
        w, h = self.size
        px = self.posicao.x - self.camera.x + w // 2
        py = self.posicao.y - self.camera.y + h // 2
        rect = sprite.get_rect(center=(int(px), int(py)))

        sombra = pygame.Surface(
            (sprite.get_width() * 3 // 4, max(6, sprite.get_height() // 8)),
            pygame.SRCALPHA,
        )
        pygame.draw.ellipse(sombra, (0, 0, 0, 70), sombra.get_rect())
        surface.blit(
            sombra,
            sombra.get_rect(centerx=rect.centerx, bottom=rect.bottom - 2),
        )
        surface.blit(sprite, rect)

    def _desenhar_saida(self, surface: pygame.Surface) -> None:
        """Marca da saida, no fim do cenario."""
        w, h = self.size
        sx, sy = self.mapa.para_pixels(*self.mapa.saida, self.tile)
        px = sx - self.camera.x + w // 2
        py = sy - self.camera.y + h // 2
        cor = theme.lerp(theme.BACKGROUND, theme.GOLD, theme.pulse(self.time))
        pygame.draw.rect(
            surface, cor,
            pygame.Rect(px - self.tile // 6, py - self.tile // 6,
                        self.tile // 3, self.tile // 3),
            2,
        )

    def _desenhar_esqueleto(self, surface: pygame.Surface) -> None:
        """O esqueleto parado, antes da luta.

        Os quadros vem de um cache. A versao anterior chamava
        `assets.load_foe` aqui dentro, a CADA QUADRO: um glob na pasta,
        oito PNGs abertos do disco e oito escalas, sessenta vezes por
        segundo, com o esqueleto na tela. So isso derrubou o jogo para
        22 fps. O medidor de desempenho nao pegou porque ele rodava sem
        esqueleto na tela.
        """
        quadros = self._quadros_esqueleto
        if quadros is None:
            quadros = assets.load_foe(assets.FOE_KINDS[0], "oeste", "walk")
            self._quadros_esqueleto = quadros or []
            if not quadros:
                return
        idx = int(self.time * assets.fps_do_estado("walk")) % len(quadros)
        sprite = quadros[idx]
        w, h = self.size
        px = self.esqueleto.x - self.camera.x + w // 2
        py = self.esqueleto.y - self.camera.y + h // 2
        rect = sprite.get_rect(center=(int(px), int(py)))
        sombra = pygame.Surface(
            (sprite.get_width() * 3 // 4, max(5, sprite.get_height() // 9)),
            pygame.SRCALPHA,
        )
        pygame.draw.ellipse(sombra, (0, 0, 0, 70), sombra.get_rect())
        surface.blit(sombra, sombra.get_rect(centerx=rect.centerx,
                                             bottom=rect.bottom - 2))
        surface.blit(sprite, rect)

    def _desenhar_aula(self, surface: pygame.Surface) -> None:
        """A dica da vez, num bloco no canto superior esquerdo.

        Duas versoes antes desta falharam:

        - texto solto sobre o chao, em cinza apagado: sobre os tijolos do
          tileset o contraste era quase nulo e a linha de detalhe era
          pior ainda
        - uma faixa na base da tela, legivel mas POR CIMA do heroi:
          a camera encosta nele nas bordas do mapa, que e exatamente
          onde ele costuma estar

        O canto superior esquerdo fica vazio (e onde o nome da area e o
        rotulo da area ja aparecem), entao o bloco cabe ali sem cobrir
        ninguem.
        """
        aula = self.tutorial.atual
        if aula is None:
            return
        w, h = self.size
        # sobe de opacidade em vez de esmaecer: uma dica que aparece
        # devagar e uma dica que se perde
        entrada = min(1.0, self.tutorial.tempo / 0.35)
        if entrada <= 0.03:
            return

        linhas = 2 if aula.detalhe else 1
        altura = 30 + 22 * linhas
        x0 = int(w * 0.045)
        y0 = int(h * 0.075)

        # MEDE antes de desenhar. A primeira versao desenhava o texto e
        # depois pintava o fundo por cima, que e o caminho obvio para
        # descobrir a largura: o resultado era um retangulo vazio com o
        # texto soterrado embaixo dele.
        # As coordenadas no rascunho sao as de TELA, porque o blit do
        # rascunho e em (0, 0): usar posicoes relativas ao bloco
        # deixava o texto acima do fundo.
        rascunho = pygame.Surface((w, h), pygame.SRCALPHA)
        texto = theme.text_tracked_at(
            rascunho, aula.texto, 19, (x0 + 16, y0 + 26),
            theme.lerp(theme.BACKGROUND, theme.TEXT_BRIGHT, entrada),
        )
        largura = texto.width
        if aula.detalhe:
            detalhe = theme.text_tracked_at(
                rascunho, aula.detalhe, 14, (x0 + 16, y0 + 48),
                theme.lerp(theme.BACKGROUND, theme.TEXT, entrada * 0.95),
            )
            largura = max(largura, detalhe.width)

        caixa = pygame.Rect(x0, y0, max(largura, 120) + 32, altura)
        fundo = pygame.Surface(caixa.size, pygame.SRCALPHA)
        fundo.fill((8, 7, 6, int(222 * entrada)))
        surface.blit(fundo, caixa)
        theme.hairline(
            surface, caixa.x, caixa.y, caixa.x + caixa.width, (58, 52, 44)
        )

        # agora sim, por cima do fundo
        surface.blit(rascunho, (0, 0))

    def _desenhar_hud(self, surface: pygame.Surface) -> None:
        if self.fase != "livre":
            return
        w, h = self.size
        voltar = "/".join(self.controls.labels("voltar")) or "esc"
        salvar = "/".join(self.controls.labels("salvar")) or "f5"

        theme.text_tracked_at(surface, "CATACUMBAS", 16, (28, 34), theme.TEXT_DIM)

        # o tempo de jogo fica embaixo, a direita. No topo direito mora
        # o contador de FPS, e os dois se atropelavam ali: o tempo era
        # desenhado logo abaixo do FPS e a leitura ficava aberta de um
        # lado so.
        theme.text_tracked_right(
            surface, formatar_tempo(self.tempo_jogado), 16, w - 28, h - 26,
            theme.TEXT_DIM,
        )
        theme.text_tracked_at(
            surface, f"{voltar} voltar    {salvar} salvar", 15,
            (28, h - 26), theme.HAIRLINE, tracking=1,
        )
