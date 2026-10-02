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

from . import (  # noqa: I001
    animacao,
    assets,
    luz,
    cenarios,
    chao as chao_mod,
    coffin,
    rocha,
    settings,
    theme,
    wang,
)
from . import cenario as cenario_mod
from . import progresso as progresso_mod
from . import equipamento as equip_mod
from . import ui_arte
from . import estado as estado_mod
from . import fogueira as fogueira_mod
from . import itens as itens_mod
from .area_title import AreaTitle
from .dungeon_map import (
    CHAO,
    PAREDE,
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
# quanto tempo o corpo leva para cair e a tela escurecer, antes do
# caixao abrir de novo. Curto o bastante para nao encher, longo o
# bastante para o jogador ver que morreu.
DURACAO_MORTE = 1.9
# quantos quadros a arte de queda tem. O pacote traz sete; se a
# arte mudar, este numero e o unico lugar a acertar.
QUADROS_MORTE = 6.0

FASE_DURADA = {
    "morrendo": DURACAO_MORTE,
    "acordando": 2.0,
    "abrindo": 1.4,
    "saindo": 1.6,
}




# o tileset de cada cenario e lido uma vez e reusado
_TABLES_WANG: dict[str, dict] = {}


def _tabela_wang(cenario) -> dict | None:
    """Monta e guarda a tabela de tiles Wang do cenario.

    Sem cache, os 16 tiles seriam lidos do disco e recortados a cada
    quadro. A tabela so depende do cenario, entao e montada uma vez.

    `_TABELA_ATUAL` e atualizada nos DOIS caminhos, cacheado ou nao.
    So no caminho novo, uma troca de cenario deixaria a tabela do
    cenario anterior por tras e o desenho buscaria a peca de origem pelo
    canto errado.
    """
    if cenario.tileset in _TABLES_WANG:
        tabela = _TABLES_WANG[cenario.tileset]
    else:
        png = settings.TILES_DIR / cenario.png
        meta = settings.TILES_DIR / cenario.json
        if not png.is_file() or not meta.is_file():
            print(f"[dungeon] tileset do cenario ausente: {png.name}")
            return None
        try:
            tabela, _lado = wang.carregar_tileset_wang(png, meta)
            tabela = _ajustar_legibilidade(tabela)
        except (pygame.error, OSError, ValueError, KeyError) as exc:
            print(f"[dungeon] tileset do cenario ilegivel: {exc}")
            return None
        _TABLES_WANG[cenario.tileset] = tabela

    _TABELA_ATUAL.clear()
    _TABELA_ATUAL.update(tabela)
    return tabela


def _ajustar_legibilidade(
    tabela: dict[tuple[bool, bool, bool, bool], pygame.Surface],
) -> dict[tuple[bool, bool, bool, bool], pygame.Surface]:
    """Escurece a parede e clareia o chao, tile por tile.

    A tela inteira passa por um veu escuro, e o tileset novo tem parede
    e chao na mesma faixa de brilho. Sob o veu os dois viravam a mesma
    coisa e nao dava para saber onde da para andar: o jogador via um
    corredor de tijolo em todo lugar.

    Como a tabela Wang sabe, tile por tile, quantos cantos sao parede,
    nao precisa adivinhar pelo desenho: o chao e o unico tile sem
    nenhum canto de parede.
    """
    ajustada = {}
    for cantos, tile in tabela.items():
        tem_parede = any(cantos)
        img = tile.copy()
        if tem_parede:
            ganho = 0.62
        else:
            ganho = 1.18
        w, h = img.get_size()
        for y in range(h):
            for x in range(w):
                r, g, b, a = img.get_at((x, y))
                if a == 0:
                    continue
                img.set_at(
                    (x, y),
                    (
                        min(255, int(r * ganho)),
                        min(255, int(g * ganho)),
                        min(255, int(b * ganho)),
                        a,
                    ),
                )
        ajustada[cantos] = img
    return ajustada


def _tile_pronto(
    chave: tuple[bool, bool, bool, bool], lado: tuple[int, int]
) -> pygame.Surface:
    """Tile de Wang ja no tamanho de tela, em cache.

    O tileset novo e de 32px e o jogo desenha tile de 16px vezes a
    escala dos sprites. Escalar a cada celula a cada quadro seria o
    mesmo preco que o cache do tileset antigo evitava. A chave e a de
    cantos, nunca o `id()` da imagem: o id de um objeto liberado volta
    a ser usado e o cache entregaria a peca errada sem avisar.
    """
    global _TILES_ESCALA
    if lado[0] != _TILES_ESCALA:
        _TILES_ESCALADOS.clear()
        _TILES_ESCALA = lado[0]
    pega = _TILES_ESCALADOS.get(chave)
    if pega is not None:
        return pega
    origem = _TABELA_ATUAL.get(chave)
    if origem is None:
        return _TILES_ESCALADOS.setdefault(
            chave, pygame.Surface(lado, pygame.SRCALPHA)
        )
    tile = origem if origem.get_size() == lado else pygame.transform.scale(origem, lado)
    _TILES_ESCALADOS[chave] = tile
    return tile



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


# tiles ja ampliados para o tamanho de tela, cacheados pela chave de
# cantos. A versao anterior escalava CADA tile visivel a CADA quadro: numa
# tela 1520x921 sao mais de 600 tiles, e 600 `pygame.transform.scale` por
# quadro era o suficiente para derrubar o jogo para metade da velocidade.
# O tileset e estatico, entao ampliar uma vez e guardar.
_TILES_ESCALADOS: dict[tuple, pygame.Surface] = {}
_TILES_ESCALA = -1

# a tabela do cenario em uso, para o cache de escala achar a imagem de
# origem a partir da chave
_TABELA_ATUAL: dict[tuple, pygame.Surface] = {}


class DungeonScene(Scene):
    """Um cenario de masmorra, com autotiling de Wang."""

    inventario_aberto = False

    def __init__(self, manager, cenario=None) -> None:
        super().__init__(manager)
        self.cenario = cenario or cenarios.primeiro()
        self._wang: wang.GradeWang | None = None
        # as celulas de parede com tocha. None = ainda nao calculado; a
        # lista e a mesma para o mapa inteiro, e recalcular a cada quadro
        # seria varrer o mapa inteiro por quadro
        self._tochas: list[tuple[int, int]] | None = None
        # o progresso da campanha vem do estado do gerenciador, que o
        # carrega do save. Sem ele a masmorra nao saberia em que sala
        # o jogador esta nem onde o chefe foi recambiado.
        self.progresso: progresso_mod.Progresso = (
            self.manager.ui_state.get("progresso")
            or progresso_mod.Progresso(cenario=self.cenario.nome.lower())
        )
        self.mapa: Mapa = gerar_mapa(
            salas=len(progresso_mod.SALAS),
            semente=self.cenario.semente,
        )
        self.direction = "sul"
        self.moving = False
        self.anim_time = 0.0
        self.time = 0.0

        self.walk_frames = assets.load_animation(self.direction, "walk")
        self.idle_frames = assets.load_animation(self.direction, "idle")

        self.tile = TILE_BASE * assets.get_sprite_scale()
        self.posicao = pygame.Vector2(self._posicao_inicial())
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
        # a pocao da sala da pocao, largada no chao. Vira None quando
        # o jogador pega, e o progresso e que guarda se ja foi pega:
        # recarregar a cena nao pode devolver a pocao no chao.
        self.estado = estado_mod.do_gerenciador(self.manager)
        self.fogueira_ativa: fogueira_mod.Fogueira | None = None
        self.fogueira_pos: pygame.Vector2 | None = None
        self.item_no_chao: pygame.Vector2 | None = None
        # a aula da sala da pocao: a luta aponta a opcao de item
        self.ensinar_item = False
        # em que sala o jogador esta agora. Comeca na sala do cofre,
        # senao a primeira frase de dica apareceria duas vezes
        self.sala_atual = self.mapa.sala_de(*self.mapa.caixao)
        self._colocar_item()
        self._colocar_fogueira()
        # quadros do esqueleto, carregados uma vez
        self._quadros_esqueleto: list | None = None
        self.passos = 0
        # os enfeites de chao. Sao escolhidos uma vez, com semente
        # fixa: um caco nao muda de lugar entre duas visitas.
        self.enfeites = cenario_mod.distribuir(
            self.mapa, quantos=self._quantos_enfeites(),
            semente=self._semente(),
        )
        # o quadro da animacao de morte. A fase "morrendo" roda o
        # `death` do pacote e so depois chama a abertura.
        self.morte_quadro = 0
        # o relogio do passo do heroi: o corpo sobe duas vezes por
        # ciclo, inclina e achata. Nao e o mesmo que o metodo
        # `_passo()`, que calcula o deslocamento em pixels.
        self.andamento = animacao.Passo()
        # de onde comecou a caminhada de saida do caixao. None
        # quando nao esta na fase 'saindo'.
        self._saida_inicio: float | None = None
        self.acabou_aula_de_mover = False
        # qual acao o jogador apertou neste quadro. E o que fecha as
        # aulas: o tutorial precisa saber que o jogador DEU o comando,
        # nao so que a tecla exists
        self._acao_deste_quadro: str | None = None

        # um save vindo do menu pula a abertura: o jogador ja acordou
        # uma vez e nao faz sentido ver o caixao toda vez que continua.
        #
        # E `pop`, e nao `get`: a masmorra e recriada ao voltar de uma
        # luta, e com `get` o save continuava no estado e era aplicado
        # DE NOVO — a vida, o ouro e as salas vencidas que a luta tinha
        # dado eram apagados e o jogador voltava ao caixao. Era o
        # "quando eu mato o esqueleto o jogo comeca de novo".
        # o resultado da luta e lido ANTES do save: e ele que diz se
        # esta e a volta de uma luta (a cena nao abre o caixao de novo)
        # ou a primeira entrada da partida (abre).
        self._resultado_pendente = manager.ui_state.pop(
            "resultado_combate", None
        )
        self._pendente_contra_chefe = bool(
            manager.ui_state.pop("combate_contra_chefe", False)
        )
        voltando_de_luta = self._resultado_pendente is not None
        # onde o jogador estava quando a luta comecou. A masmorra e
        # recriada ao voltar, e sem isto a cena nova so comecaria na
        # posicao do save — ou, sem save, dentro do caixao.
        volta_em = manager.ui_state.pop("posicao_antes_da_luta", None)

        carregado = manager.ui_state.pop("save_carregado", None)
        if carregado is not None:
            self._aplicar_save(carregado)
            # o progresso da campanha vem do `extra` do save. Sem isto
            # a sala, a pocao, o chefe recambiado e o mundo aberto
            # voltavam ao zero a cada F5, e a campanha nao sobrevivia
            # nem a uma ida ao menu.
            self.progresso = progresso_mod.Progresso.de_extra(
                (getattr(carregado, "extra", None) or {}).get("progresso")
            )
            # a vida, o ouro e a ultima fogueira tambem. Sem isto o
            # jogador acordava com a vida cheia e a carteira vazia a
            # cada F5, e a loja da aldeia viraria vitrine sem uso.
            self.estado = estado_mod.Estado.de_extra(
                (getattr(carregado, "extra", None) or {}).get("estado")
            )
            manager.ui_state["progresso"] = self.progresso
            manager.ui_state["estado"] = self.estado
        elif voltando_de_luta and volta_em is not None:
            # volta de luta: o jogador ja estava acordado, entao nao
            # ha o que abrir. Ele volta EXATAMENTE onde a luta comecou.
            self.fase = "livre"
            self.fase_tempo = 0.0
            self.tampa = 0.0
            self.posicao = pygame.Vector2(volta_em)
            self.posicao = self._sem_bater(self.posicao, pygame.Vector2())
            self.camera = pygame.Vector2(self.posicao)
            self._recarregar(self.direction)
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
            extra={
                "progresso": self.progresso.para_extra(),
                "estado": self.estado.para_extra(),
            },
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
            self.posicao = pygame.Vector2(self._posicao_inicial())
        self.posicao = self._sem_bater(self.posicao, pygame.Vector2())
        self.camera = pygame.Vector2(self.posicao)
        self.moving = False
        # o nome do lugar aparece igual: quem chega numa area nova ou
        # quem volta para ela precisa saber onde esta
        self.titulo.show(self.cenario.nome, self.cenario.subtitulo)
        self._titulo_mostrado = True

    def _avisar(self, texto: str, segundos: float = 2.4) -> None:
        self.aviso = texto
        self._aviso_tempo = segundos

    # --- posicoes ---------------------------------------------------
    def _posicao_inicial(self) -> tuple[float, float]:
        """Onde o jogador comeca.

        No cenario com caixao, dentro dele. Nos outros, na entrada do
        mapa: comecar no meio de um cenario que o jogador nao conhecia
        deixa o lugar sem nome e sem sentido de chegada.
        """
        if self.cenario.tem_caixao:
            cx, cy = self.mapa.caixao
        else:
            cx, cy = self.mapa.entrada
        return self.mapa.para_pixels(cx, cy, self.tile)

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

    # --- o que a luta deixou para tras --------------------------------
    def _resolver_resultado(self) -> None:
        """Reage ao fim da luta: venceu, fugiu, ou perdeu.

        Sem isto a fuga so sobrescrevia um estado: o jogador voltava
        para a masmorra, no mesmo lugar, com o chefe de novo na sala, e
        nao entendia o que a mecanica tinha feito. Fugir do chefe e
        SAIR da masmorra; e o que faz o chefe mudar de sala depois.
        """
        resultado = self._resultado_pendente
        if resultado is None:
            return
        self._resultado_pendente = None
        contra_chefe = self._pendente_contra_chefe
        self._pendente_contra_chefe = False
        # a pocao da sala da pocao, largada no chao. Fica None depois
        # que o jogador pega, e o progresso e que guarda se ela ja foi
        # pega: recarregar a cena nao pode devolver a pocao.
        self.item_no_chao = None
        self.ensinar_item = False

        self.esqueleto = None
        self.esqueleto_vivo = False
        self._quadros_esqueleto = None

        if resultado == "fuga":
            if contra_chefe:
                self.progresso.fugir_do_chefe()
                self.progresso.sair_da_masmorra()
                self.manager.ui_state["progresso"] = self.progresso
                self.manager.salvar_progresso()
                self.manager.switch("road")
                return
            self._avisar("Voce fugiu. O esqueleto nao te seguiu.")
            return

        if resultado == "vitoria":
            # A sala e ONDE O JOGADOR LUTOU, e nao onde esta o chefe.
            # Usar `onde_esta_o_chefe()` aqui marcava a quinta sala
            # como vencida ao matar o esqueleto da primeira, e pagava a
            # recompensa do chefe em vez da da sala.
            sala = self.sala_atual
            if sala in (0, None):
                # corredor: nao ha sala para marcar. Acontece se o
                # jogador fugir ou ser jogado para fora durante a luta.
                self._avisar("Voce venceu.")
                return
            primeira = not self.progresso.concluida(sala)
            self.progresso.vencer(sala)
            if primeira:
                # so paga na primeira vez. Sem isto, voltar a uma sala
                # ja vencida daria ouro novo e a moeda viraria uma
                # maquina de imprimir nao intencional.
                self.estado.ouro += self.progresso.recompensa_por_vencer(sala)
            if contra_chefe:
                # vencer o chefe tambem tira o jogador da masmorra
                self.progresso.sair_da_masmorra()
                self.manager.ui_state["progresso"] = self.progresso
                self.manager.salvar_progresso()
                self.manager.switch("road")
                return
            self._avisar("Voce venceu. A aula de combate passou.")
            return

        if resultado == "derrota":
            # Nao e um teleporte. A fase "morrendo" roda a animacao de
            # queda e escurece a tela; quando ela acaba, a abertura
            # comeca normalmente. Antes o jogador aparecia no caixao no
            # mesmo quadro da derrota, e lia como o jogo reiniciando.
            self._avisar("Voce acordou no caixao de novo.", 3.0)
            self.fase = "morrendo"
            self.fase_tempo = 0.0
            self.morte_quadro = 0
            self.moving = False

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

        if self.key(event, "interagir"):
            if self._perto_da_fogueira():
                self._descansar()
                return
            self._pegar_item()
            return
        for direcao, acao in DIRECTION_ACTIONS.items():
            if self.key(event, acao):
                self._acao_deste_quadro = acao
                if direcao != self.direction:
                    self._recarregar(direcao)
                self.moving = True

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        self._resolver_resultado()
        if self._resultado_pendente is not None:
            return
        self.time += dt
        self.tempo_jogado += dt
        # o Shift e lido a cada quadro, e nao no aperto da seta: quem
        # segura a direcao acelera ou desacelera no meio do passo
        self.andamento.correndo = animacao.correndo_agora()
        self.andamento.advance(dt, self.moving)
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

        self._acompanhar_sala()
        self._atualizar_esqueleto(dt)
        self.tutorial.update(dt, self._acao_do_quadro)

    def _acompanhar_sala(self) -> None:
        """Avisa a sala em que o jogador entrou, e arma a licao dela.

        O numero da sala vem da posicao, nao de um contador: se o
        jogador andar para tras e voltar, o numero e o mesmo e a
        frase nao pisca a cada passo.
        """
        numero = self.mapa.sala_de(*self._celula())
        if numero == self.sala_atual:
            return
        primeira_visita = numero != 0 and not self.progresso.concluida(numero)
        self.sala_atual = numero
        # o progresso tambem muda de sala. Sem isto `progresso.sala`
        # ficava na 1 para sempre, e `sala_atual()` devolvia sempre a
        # primeira: a dica da tela era a da sala 1 em qualquer lugar, e
        # o esqueleto nascia fraco em TODAS as salas.
        if numero != 0:
            self.progresso.sala = numero
        if not primeira_visita:
            return

        sala = self.progresso.sala_atual()
        if numero == sala.numero and sala.dica:
            self.tutorial.mostrar(sala.dica)

    def _casa_longe_do_caixao(self, numero: int) -> tuple[int, int] | None:
        """Onde o esqueleto brota: o ponto andavel mais longe do caixao.

        O centro da sala brotava a dois tiles e meio do caixao, e o
        alcance de contato e um pouco maior que isso. A luta começava no
        mesmo instante em que a abertura terminava: o jogador via o
        monstro e ja estava dentro da tela de combate, sem dar um passo
        nem ver a sala.

        Aqui a escolha e o ponto mais distante do caixao dentro da
        sala. Numa sala onde nao ha ponto assim longe — uma sala
        pequena, ou um caixao no meio — cai no centro, que e melhor do
        que nao brotar.
        """
        centro = self.mapa.centro_da_sala(numero)
        if centro is None:
            return None
        melhor = None
        melhor_distancia = -1.0
        caixao = pygame.Vector2(
            self.mapa.para_pixels(*self.mapa.caixao, self.tile)
        )
        for y in range(0, self.mapa.altura):
            for x in range(0, self.mapa.largura):
                if self.mapa.sala_de(x, y) != numero:
                    continue
                if not self.mapa.andavel(x, y):
                    continue
                if self._ocupada(x, y):
                    continue
                ponto = pygame.Vector2(self.mapa.para_pixels(x, y, self.tile))
                distancia = ponto.distance_to(caixao)
                if distancia > melhor_distancia:
                    melhor_distancia = distancia
                    melhor = (x, y)
        return melhor if melhor is not None else centro

    def _ocupada(self, x: int, y: int) -> bool:
        """O esqueleto cabe nesse ponto: ele e a propria celula e as vizinhas.

        O raio e de UMA celula. Com um raio maior a busca nao achava
        ponto nenhum numa sala de 16x9 — quase tudo era rejeitado por ter
        parede a duas celulas de distancia — e caia no centro da sala,
        que era o defeito que este metodo existe para corrigir.
        """
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                if not self.mapa.andavel(x + dx, y + dy):
                    return True
        return False

    def _atualizar_esqueleto(self, dt: float) -> None:
        """Arma o esqueleto da sala em que o jogador esta.

        A sala 4 tem tratamento proprio: o esqueleto dela so aparece
        quando o jogador pega a pocao, para a aula do item comecar
        com o item na mao. A sala 5 e a do chefe.
        """
        if self.esqueleto is None:
            numero = self.sala_atual
            if numero in (0, 4):
                return
            # uma sala vencida nao brota esqueleto de novo. O comentario
            # abaixo prometia isso e o teste nao existia: voltar para uma
            # sala ja limpa repetia a luta inteira, e o jogador tinha que
            # lutar de novo so para receber o aviso de "Voce venceu".
            if self.progresso.concluida(numero):
                return
            # NAO ha espera por passos. A espera existia para a aula
            # de "ande um pouco" caber antes do primeiro esqueleto, mas a
            # abertura ja segura o jogador por seis segundos e ele so
            # acorda quando a fase vira "livre" — os 14 passos eram uma
            # segunda espera sem motivo, e era ela que escondia o
            # esqueleto no corredor onde o jogador sai do caixao.
            if numero == self.progresso.onde_esta_o_chefe():
                casa = self._casa_do_chefe()
            else:
                casa = self._casa_longe_do_caixao(numero)
            if casa is None:
                return
            # um esqueleto por sala: o proximo so nasce quando o
            # jogador entra numa sala ainda nao limpa
            if not self.mapa.andavel(*casa):
                return
            self.esqueleto = pygame.Vector2(
                self.mapa.para_pixels(*casa, self.tile)
            )
            self.esqueleto_vivo = True
            if numero == 1:
                self.tutorial.mostrar("O esqueleto acordou")
            else:
                self.tutorial.mostrar("Ha alguem aqui")
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
            # a masmorra diz que e o chefe, e nao um esqueleto qualquer:
            # a cena de combate monta o inimigo e a masmorra trata o
            # resultado
            self.manager.ui_state["e_chefe"] = self.progresso.e_sala_do_chefe()
            # e a sala marcada como `fracos` que monta o esqueleto
            # fraco. O campo existia no progresso desde o comeco e
            # ninguem lia: a primeira luta era dura como as outras.
            self.manager.ui_state["fracos"] = bool(
                self.progresso.sala_atual().fracos
            )
            # a masmorra e destruida e recriada quando a luta acaba.
            # Sem esta posicao a cena nova comecaria no caixao, e o
            # jogador voltaria da luta "para o comeco do jogo".
            self.manager.ui_state["posicao_antes_da_luta"] = (
                self.posicao.x, self.posicao.y
            )
            self.manager.ui_state["ensinar_item"] = self.ensinar_item
            # o cenario da luta: a sala onde o jogador esta, com o
            # tileset e os enfeites que ela ja tem. Sem isto a luta
            # acontece num limbo preto e o jogador perde de vista o
            # lugar de onde veio: a parede de tras, os barris que ele
            # tinha acabado de ver, tudo some.
            self.manager.ui_state["cenario_luta"] = {
                "tileset": self.cenario.tileset,
                "sala": self.sala_atual,
                "enfeites": list(self.enfeites),
            }
            self.manager.iniciar_combate(1)
        return

    def _colocar_item(self) -> None:
        """Larga a pocao no chao da sala 4, conforme o que o jogador tem.

        Tres casos, e o terceiro e o que o jogador pediu:

        - a sala ja foi vencida: a pocao nao volta mais, a aula acabou;
        - o jogador ainda tem pocao na mao: nao precisa de outra no
          chao. Sem esta checagem ele pegava, usava na luta, fugia e
          voltava para pegar de novo, juntando poções sem limite;
        - o jogador NAO tem pocao e a sala ainda nao foi vencida: a
          pocao volta. E o caso de usar a pocao, perder a luta e
          voltar. Sem isso a sala da pocao viraria um beco sem saida
          depois do primeiro uso.
        """
        self.inventario_aberto = False
        self.modo_equip: int | None = None
        self.index_equip = 0
        sala_item = 4
        if not self.progresso.precisa_de_pocao_no_chao():
            self.ensinar_item = False
            return

        centro = self.mapa.centro_da_sala(sala_item)
        if centro is None:
            return
        # um pouco para o lado do centro, para a poçao nao ficar
        # exatamente em cima do ponto de nascimento do inimigo
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (0, 0)):
            alvo = (centro[0] + dx, centro[1] + dy)
            if self.mapa.andavel(*alvo):
                self.item_no_chao = pygame.Vector2(
                    self.mapa.para_pixels(*alvo, self.tile)
                )
                return

    def _pegar_item(self) -> None:
        """Jogador perto da pocao: pega, e um inimigo aparece.

        A luta comeca junto com a coleta de proposito: o jogador aprende
        a usar o item dentro da luta, e nao num menu fora dela. A
        pocao precisa estar na mao ANTES de a luta comecar, senao a
        aula mostraria um item que o jogador ainda nao tem.
        """
        if self.item_no_chao is None:
            return
        if self.item_no_chao.distance_to(self.posicao) > self.tile * 1.2:
            return

        self.item_no_chao = None
        self.progresso.itens["pocao"] = self.progresso.itens.get("pocao", 0) + 1
        self.ensinar_item = True
        self.manager.ui_state["progresso"] = self.progresso
        self._avisar("Pocao de cura. Use na luta.", 3.0)

        # o inimigo da aula da pocao, no centro da sala
        centro = self.mapa.centro_da_sala(4)
        if centro is not None:
            self.esqueleto = pygame.Vector2(
                self.mapa.para_pixels(*centro, self.tile)
            )
            self.esqueleto_vivo = True
            self.tutorial.mostrar("Um esqueleto se levanta")

    def _casa_do_chefe(self) -> tuple[int, int] | None:
        """Onde o chefe fica: no centro da sala que ele ocupa.

        Antes o esqueleto nascia num anel de casas em volta do caixao.
        Com a campanha isso nao serve: o chefe tem que estar na sala
        que o progresso aponta, e a sala do chefe muda depois da fuga.
        """
        numero = self.progresso.onde_esta_o_chefe()
        centro = self.mapa.centro_da_sala(numero)
        if centro is None:
            return None
        if self.mapa.andavel(*centro):
            return centro
        # a sala tem que ter chao no centro; se nao tiver, procura
        # a casa valida mais proxima
        melhor = None
        cx, cy = centro
        for raio in range(1, 6):
            for dx in range(-raio, raio + 1):
                for dy in range(-raio, raio + 1):
                    if max(abs(dx), abs(dy)) != raio:
                        continue
                    alvo = (cx + dx, cy + dy)
                    if self.mapa.andavel(*alvo):
                        return alvo
        return melhor

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
        # o passo do heroi no mapa e continuo, e nao meio tile por
        # aperto como nas cenas da superficie. Com Shift a velocidade
        # sobe: o mesmo desenho, andando mais rapido e levantando poeira.
        passo = MOVE_SPEED * dt * animacao.fator_passo(self.andamento.correndo)
        return {
            "sul": pygame.Vector2(0, passo),
            "norte": pygame.Vector2(0, -passo),
            "leste": pygame.Vector2(passo, 0),
            "oeste": pygame.Vector2(-passo, 0),
        }[self.direction]

    def _atualizar_abertura(self, dt: float) -> None:
        """Maquina de estados da saida do caixao e da morte."""
        self.fase_tempo += dt
        duracao = FASE_DURADA[self.fase]

        if self.fase == "morrendo":
            # o corpo cai e a tela escurece. O `death` do pacote tem
            # sete quadros; a tela vai de clara a preta no mesmo tempo,
            # para a imagem e o fundo chegarem juntos no fim.
            # o quadro e o QUE DA TEMPO da fase, com uma curva: rapido
            # no comeco, que e o tombo, e lento no fim, que e o corpo
            # parado no chao. A 8fps a arte acabava em 0,75s de 1,9s e
            # passava mais de um segundo parada com a tela ja preta.
            avanco = min(1.0, self.fase_tempo / DURACAO_MORTE)
            self.morte_quadro = QUADROS_MORTE * (1.0 - (1.0 - avanco) ** 2)
            self.tampa = 1.0
            if self.fase_tempo >= duracao:
                self.fase = "acordando"
                self.fase_tempo = 0.0
                self.morte_quadro = 0
            return

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
                self.titulo.show(self.cenario.nome, self.cenario.subtitulo)
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
            if self._saida_inicio is None:
                self._saida_inicio = self.posicao.y
            self.posicao = self._sem_bater(
                self.posicao,
                pygame.Vector2(0, MOVE_SPEED * 0.55 * dt),
            )
            self.anim_time += dt
            self.moving = True
            self.camera += (self.posicao - self.camera) * min(1.0, dt * 6.0)
            andou = self.posicao.y - (self._saida_inicio or 0.0)
            travou = abs(self.posicao.y - self._saida_inicio - andou) > 0.01
            # sai do caixao, e nao atravessa a sala: antes esta fase
            # durava ate o jogador bater na parede, o que o deixava onze
            # tiles longe, num corredor onde nao nasce esqueleto
            if (andou >= 2.4 * self.tile
                    or self.fase_tempo >= duracao
                    or (travou and self.fase_tempo > 0.8)):
                self.fase = "livre"
                self.fase_tempo = 0.0
                self.moving = False
                self._saida_inicio = None

    def _sem_bater(self, pos: pygame.Vector2, delta: pygame.Vector2) -> pygame.Vector2:
        """Aplica o movimento um eixo por vez, para deslizar na parede.

        Testar o deslocamento inteiro de uma vez trava o jogador na
        parede em diagonal: ele encosta na parede norte e nao sobe mais
        nem para o lado.
        """
        alvo = pygame.Vector2(novo := pos + delta)
        if not self._livre(alvo):
            alvo.x = pos.x

        alvo.y = novo.y
        if not self._livre(alvo):
            alvo.y = pos.y
        return alvo

    def _pe_do_heroi(self) -> tuple[int, int]:
        """A largura e a altura que o heroi ocupa NO CHAO.

        A colisao usava um circulo de raio `tile // 6` — 8px num tile de
        48. O desenho do heroi tem 90px de largura. O resultado era o que
        o jogador viu: ele encostava com o CENTRO a uma parede e metade
        do corpo ficava dentro da pedra. Medido, 59% da largura.

        A medida aqui e a do SPRITE, nao uma fracao do tile: e o desenho
        que o jogador ve que tem de caber, e ele muda com a escala das
        opcoes. Um `tile // 6` fixo nao acompanha.

        A altura e menor que a largura de proposito: o topo do desenho
        (a cabeca, a espada) pode passar por cima da parede, como num
        jogo de plataforma de verdade. O que nao entra no chao e o chao.
        """
        arte = assets.equipado_na_tela("punho", assets.get_sprite_scale())
        if arte is None:
            arte = pygame.Surface((self.tile // 2, self.tile // 2))
        # O que e devolvido e a METADE: o raio em X e em Y do circulo
        # que substitui a caixa.
        #
        # A metade tem de ser pelo menos a metade do desenho, senao o
        # sprite entra na parede. Com `tile // 6` (8px) o desenho de
        # 90px entrava 37px; com 0.34 da arte (30px) entrava 15px. A
        # metade do desenho e o que para o corpo na borda.
        #
        # A altura e menor, de proposito: o topo (cabeca, espada) pode
        # passar por cima da parede, como num jogo de plataforma. O que
        # nao entra no chao e o chao.
        meia_l = arte.get_width() // 2
        meia_a = int(arte.get_height() * 0.30) // 2
        return max(4, meia_l), max(4, meia_a)

    def _livre(self, pos: pygame.Vector2, raio: int | None = None) -> bool:
        """True se a caixa do heroi em `pos` nao cruza parede nem objeto.

        `pos` e em coordenadas de MAPA (pixels do mundo), nao de tela.
        Passar por `_tela_para_mapa` aqui descontaria a camera duas
        vezes e a colisao checaria tiles errados: o jogador andava
        atravessando parede e o teste pegava exatamente isso.

        A caixa e a dos PÉS do heroi, e nao um circulo. E o que separa
        a parede do desenho: com um circulo, metade do corpo entrava na
        pedra; com a caixa dos pes, o corpo para na borda e o topo pode
        passar por cima, como num jogo de plataforma.

        O caixao e um OBJETO com colisao, e nao um tile de parede: o
        jogador sai de dentro dele no comeco do jogo, entao a celula
        dele e andavel, mas o OBJETO bloqueia. Sem isso o heroi andava
        por cima do caixao e oSprite do caixao ficava no meio do
        personagem.
        """
        if raio is not None:
            # o parametro antigo, em px de raio. Quem chama assim
            # quer um circulo, e nao a caixa do heroi
            fx = int((pos.x - raio) // self.tile)
            fy = int((pos.y - raio) // self.tile)
            ax = int((pos.x + raio) // self.tile)
            ay = int((pos.y + raio) // self.tile)
            for cy in range(min(fy, ay), max(fy, ay) + 1):
                for cx in range(min(fx, ax), max(fx, ax) + 1):
                    if self.mapa.em(cx, cy) == PAREDE:
                        return False
            return True

        meia_l, meia_a = self._pe_do_heroi()
        fx = int((pos.x - meia_l) // self.tile)
        ax = int((pos.x + meia_l) // self.tile)
        fy = int((pos.y - meia_a) // self.tile)
        ay = int((pos.y + meia_a) // self.tile)
        for cy in range(min(fy, ay), max(fy, ay) + 1):
            for cx in range(min(fx, ax), max(fx, ax) + 1):
                if self.mapa.em(cx, cy) == PAREDE:
                    return False

        # o caixao: um objeto solido, do tamanho do desenho dele. A
        # celula continua andavel (o jogador COMECA dentro dela), mas o
        # objeto nao deixa passar por cima
        if self._dentro_do_caixao(pos):
            return False
        return True

    def _caixa_do_caixao(self) -> pygame.Rect | None:
        """O retangulo do caixao em pixels de mapa, ou None sem caixao.

        A caixa e a do DESENHO, e nao a da celula: e a arte que diz
        onde a pedra esta, e o que o jogador ve que tem de bloquear.
        Ela e menor que a celula, senao o jogador nao sai de dentro dela
        — que e o que acontece no comeco do jogo, quando ele acorda
        DENTRO do caixao.
        """
        if self.mapa.caixao is None:
            return None
        cx, cy = self._centro_caixao()
        # A caixa vem do DESENHO, e nao de uma fracao do tile: e a arte
        # que diz onde a pedra esta. `COFFIN_W` e `COFFIN_H` sao as
        # medidas do corpo desenhado por `coffin.draw_coffin`, e a
        # ancora e o CENTRO (o desenho e pendurado no `center`).
        #
        # A caixa e menor que a celula, de proposito: no comeco do jogo
        # o jogador acorda DENTRO do caixao, e uma caixa do tamanho da
        # celula o prenderia la para sempre.
        escala = assets.get_sprite_scale()
        largura = coffin.COFFIN_W * escala
        altura = coffin.COFFIN_H * escala
        return pygame.Rect(cx - largura / 2, cy - altura / 2,
                           largura, altura)

    def _dentro_do_caixao(self, pos: pygame.Vector2) -> bool:
        """Se o heroi esta sobre o desenho do caixao.

        O pedido do jogador: o caixao tem colisao de objeto, e a
        colisao esta sincronizada com os pixels dele. Aqui a caixa e a
        mesma que o desenho usa, entao o que bloqueia e o que se ve.
        """
        # A saida do caixao nao e bloqueada: e o unico momento em que o
        # jogador esta DENTRO do objeto, e ele esta subindo para fora.
        # Sem esta liberacao o jogador acorda preso na pedra, que e
        # pior do que ele atravessar a pedra por dois segundos.
        if self.fase in ("saindo", "morrendo", "acordando"):
            return False
        caixa = self._caixa_do_caixao()
        if caixa is None:
            return False
        meia_l, meia_a = self._pe_do_heroi()
        pe = pygame.Rect(
            pos.x - meia_l, pos.y - meia_a, meia_l * 2, meia_a * 2)
        return pe.colliderect(caixa)

    # desenho -------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        # O fundo e rocha, e nao preto. Fora das salas ainda e caverna, e
        # o preto ali lia como buraco na tela em vez de pedra no escuro.
        # E a mesma pedra que a parede usa, ancorada na camera, entao a
        # fiada do fundo continua na da parede sem emenda.
        rocha.campo(surface, self.tile, self.camera.x, self.camera.y)
        self._limitar_camera()
        self._desenhar_mapa(surface)
        # os enfeites vem logo apos o chao e antes de qualquer pessoa:
        # um barril no chao e uma peca de cenario, e nao algo que
        # atravessa a frente do personagem
        cenario_mod.desenhar(
            surface, self.mapa, self.enfeites, self.tile,
            self.camera, self.size,
        )
        self._desenhar_saida(surface)
        self._desenhar_item(surface)
        self._desenhar_fogueira(surface)

        escala = assets.get_sprite_scale()
        cx, cy = self._centro_caixao()

        heroi_visivel = self.fase in ("morrendo", "saindo", "livre")
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
        self._desenhar_inventario_mundo(surface)
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

        # a luz vem depois de TUDO estar desenhado: e uma mascara sobre
        # a cena pronta, e nao um desenho a mais. Antes dela o mapa era
        # uma laje marrom com luz igual em todo canto, e a fogueira era
        # so um desenho.
        self._aplicar_luz(surface)
        # a chama das tochas vem DEPOIS do veu: desenhada antes, a
        # mascara escurecia a propria chama e a tocha virava so um
        # borrão de luz
        self._desenhar_chamas(surface)

        if self.fase == "morrendo":
            # a tela escurece enquanto o corpo cai, e ja chega quase
            # preta quando a abertura comeca. Sem isto a morte era um
            # corte seco de uma cena para a outra e o jogador lia como
            # o jogo reiniciando, e nao como ele morrendo.
            escuro = int(150 * min(1.0, self.fase_tempo / DURACAO_MORTE))
            theme.fade_surface(surface, escuro)
        elif self.fase == "acordando" and self.fase_tempo < 0.8:
            theme.fade_surface(surface, int(255 * (1 - self.fase_tempo / 0.8)))

    def _quantos_enfeites(self) -> int:
        """Quantos enfeites cabem na sala, pela area andavel.

        Um enfeite a cada vinte celulas andaveis. Densidade baixa de
        proposito: encher a sala de barrel e o mesmo que nao ter
        nenhum — o olho para de ler o chao.
        """
        andaveis = sum(
            1
            for y in range(self.mapa.altura)
            for x in range(self.mapa.largura)
            if self.mapa.andavel(x, y)
        )
        return max(6, min(30, andaveis // 20))

    def _semente(self) -> int:
        """A semente do mapa, para a decoracao acompanhar o layout."""
        for nome in ("semente", "seed", "_semente"):
            valor = getattr(self.mapa, nome, None)
            if isinstance(valor, int):
                return valor
        # sem semente no mapa: o mesmo valor de sempre, e a decoracao
        # fica igual entre visitas
        return 12345

    def _aplicar_luz(self, surface: pygame.Surface) -> None:
        """Escurece a cena e abre a luz no heroi, na fogueira e nas tochas.

        O alcance e medido em TILES, e nao em pixels: seis tiles de luz
        em 720p e seis tiles em 1080p, e nao um circulo que cresce
        junto com a janela. Sem isso o jogador enxerga o dobro do
        cenario numa tela grande e nada numa pequena.
        """
        w, h = self.size
        mascara = luz.Luz()
        # A masmorra e escura, e a luz dela vem das tochas da parede.
        #
        # NAO ha luz no heroi: ele caiu no mundo medieval sem nada, sem
        # tocha na mao e sem lampiao. O escuro ao redor dele e o que o
        # jogador tem de fato, e e assim que a masmorra tem clima.
        #
        # As tochas da parede sao o que torna a masmorra jogavel, e por
        # isso precisam cobrir a tela: uma a cada 4 celulas de parede
        # visivel, mais a fogueira, e nao sobra buraco preto.
        for tx, ty in self._tochas_visiveis(*self._origem_do_desenho(), w, h):
            mascara.add(tx, ty, int(self.tile * 5.0), luz.LUZ_TOCHA)
        # a fogueira: maior e mais quente, e e a unica luz parada da
        # sala — o jogador precisa poder achar o caminho de volta
        if self.fogueira_pos is not None:
            mascara.add(
                int(self.fogueira_pos.x - self.camera.x + w // 2),
                int(self.fogueira_pos.y - self.camera.y + h // 2),
                int(self.tile * 8.5),
                luz.LUZ_FOGUEIRA,
            )
        mascara.aplicar(surface)
        surface.blit(luz.vinhete(w, h), (0, 0))

    # uma tocha a cada N celulas de parede. Medido no zoom: com 3 os
    # focos se fundiam num continuo e nao dava para ver onde uma acabava
    # e a outra comecava; com 4 o foco continua separado.
    ESPACO_TOCHAS = 4

    def _celulas_de_tocha(self) -> list[tuple[int, int]]:
        """As celulas de parede que recebem tocha. Fixas por mapa.

        A posicao sai do mapa, e nao da tela: a tocha esta na parede,
        entao fica onde esta quando a camera se move, e o jogador ve a
        mesma tocha quando volta. E o que faz a masmorra parecer um
        lugar, e nao um efeito de luz que persegue o personagem.
        """
        if self._tochas is None:
            saida: list[tuple[int, int]] = []
            n = 0
            for y in range(1, self.mapa.altura - 1):
                for x in range(1, self.mapa.largura - 1):
                    if self.mapa.em(x, y) != PAREDE:
                        continue
                    # so na parede que da para uma sala. Uma tocha
                    # fechada dentro da rocha nao acende nada e so
                    # gasta desenho.
                    if not (
                        self.mapa.em(x, y - 1) == CHAO
                        or self.mapa.em(x, y + 1) == CHAO
                        or self.mapa.em(x - 1, y) == CHAO
                        or self.mapa.em(x + 1, y) == CHAO
                    ):
                        continue
                    n += 1
                    if n % self.ESPACO_TOCHAS == 0:
                        saida.append((x, y))
            self._tochas = saida
        return self._tochas

    def _origem_do_desenho(self) -> tuple[int, int]:
        """O canto (0, 0) da tela em pixel de mapa.

        E o mesmo deslocamento que `_desenhar_mapa` usa. As tochas
        precisam dele para saber onde esta cada uma na tela, e fazer o
        calculo em dois lugares e a forma de a tocha ficar um tile fora
        do lugar quando um dos dois for ajustado.
        """
        w, h = self.size
        return (
            w // 2 - self.camera.x - self.tile // 2,
            h // 2 - self.camera.y - self.tile // 2,
        )

    def _tochas_visiveis(
        self, x_desenho: int, y_desenho: int, w: int, h: int
    ) -> list[tuple[int, int]]:
        """As tochas dentro da tela, em pixel de tela."""
        visiveis: list[tuple[int, int]] = []
        for cx, cy in self._celulas_de_tocha():
            tx = cx * self.tile + x_desenho + self.tile // 2
            ty = cy * self.tile + y_desenho + self.tile // 2
            if (-self.tile <= tx < w + self.tile
                    and -self.tile <= ty < h + self.tile):
                visiveis.append((tx, ty))
        return visiveis

    def _desenhar_chamas(self, surface: pygame.Surface) -> None:
        """A chama de cada tocha, DESENHADA DEPOIS da mascara.

        A mascara de luz cuida do brilho em volta: ela clareia o chao e
        a parede perto de cada tocha. A chama e o pixel art em si, e
        precisa sair por cima do veu escuro senao ela tambem escurece e
        some — e a tocha vira um borrão de luz sem chama nenhuma.

        Por isso a chama nao e desenhada antes da mascara, como todo o
        resto da cena.
        """
        for tx, ty in self._tochas_visiveis(
            *self._origem_do_desenho(), self.size[0], self.size[1]
        ):
            pygame.draw.rect(
                surface, (168, 96, 34),
                pygame.Rect(tx - 2, ty - 10, 4, 12))
            pygame.draw.rect(
                surface, (226, 150, 60),
                pygame.Rect(tx - 4, ty - 18, 8, 9))
            pygame.draw.rect(
                surface, (255, 244, 208),
                pygame.Rect(tx - 2, ty - 15, 4, 5))
            pygame.draw.rect(
                surface, (255, 255, 248),
                pygame.Rect(tx - 1, ty - 12, 2, 4))

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
        tabela = _tabela_wang(self.cenario)
        if tabela is None:
            theme.text_tracked_at(
                surface,
                f"tileset ausente: {self.cenario.png}",
                18, (20, 20), theme.TEXT_DIM,
            )
            return
        if self._wang is None:
            self._wang = wang.GradeWang(self.mapa.celulas, tabela=tabela)

        w, h = self.size
        x0, y0 = self._tela_para_mapa((0, 0))
        x1, y1 = self._tela_para_mapa((w, h))
        x_desenho = w // 2 - self.camera.x - self.tile // 2
        y_desenho = h // 2 - self.camera.y - self.tile // 2
        lado = (self.tile, self.tile)
        referencia = None

        # os tiles sao filtrados antes do desenho: dois em cada direcao,
        # por causa da sombra da parede
        for y in range(max(0, y0 - 1), min(self.mapa.altura, y1 + 2)):
            linha = y * self.tile + y_desenho
            for x in range(max(0, x0 - 1), min(self.mapa.largura, x1 + 2)):
                if self.mapa.em(x, y) == PAREDE:
                    # A parede ANTES nao era desenhada. O que se via de
                    # parede era so a faixa que o tile do chao carrega na
                    # borda, entao a massa de rocha ficava preta — e as
                    # tochas, que sao postas na parede, apareciam
                    # flutuando no preto sem nada em volta.
                    #
                    # A parede e a mesma rocha das cenas de fora, no tom
                    # da noite: e ela que faz a sala ter fundo em vez de
                    # recorte flutuando no vazio.
                    surface.blit(
                        rocha.celula(self.tile, x, y),
                        (x * self.tile + x_desenho, linha),
                    )
                    continue
                chave, _img = self._wang.tile_e_chave(x, y)
                surface.blit(
                    _tile_pronto(chave, lado),
                    (x * self.tile + x_desenho, linha),
                )
                if referencia is None:
                    # a peca de chao vista na tela serve de referencia
                    # para a paleta do detalhe espalhado
                    referencia = _tile_pronto(chave, lado)

        # o detalhe do chao e uma camada so, e uma blit — o mesmo que a
        # cidade e a estrada fazem. Espalhar celula a celula a cada
        # quadro era o que segurava a masmorra abaixo de 60 FPS.
        if referencia is not None:
            chao_mod.camada(
                surface, referencia, self.tile,
                self.camera.x, self.camera.y,
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
        """O heroi no mapa: andando, parado, ou caindo.

        Andando e parado e o desenho do conjunto equipado, animado pelo
        passo de `animacao`. A animacao de caminhada do pacote de
        mercado traria uma espada na mao em todos os conjuntos, e o
        jogador comeca desarmado.

        Na fase "morrendo" o que vale e a arte de queda do pacote, que
        e uma tira so e serve para qualquer direcao. Sem isto a fase
        existia so no relogio: a tela escurecia e o heroi continuava em
        pe.
        """
        if self.fase == "morrendo" and self.morte_quadro > 0:
            quadros = assets.load_animation(
                "sul", "death", scale=assets.get_sprite_scale()
            )
            if quadros:
                i = int(self.morte_quadro) % len(quadros)
                sprite = quadros[i]
                centro = (
                    int(self.posicao.x - self.camera.x + self.size[0] // 2),
                    int(self.posicao.y - self.camera.y + self.size[1] // 2),
                )
                rect = sprite.get_rect(midbottom=centro)
                sombra = pygame.Surface(
                    (sprite.get_width() * 3 // 4, max(4, sprite.get_height() // 8)),
                    pygame.SRCALPHA,
                )
                pygame.draw.ellipse(
                    sombra, (0, 0, 0, 80), sombra.get_rect()
                )
                surface.blit(
                    sombra,
                    sombra.get_rect(centerx=rect.centerx, bottom=rect.bottom),
                )
                surface.blit(sprite, rect)
                return
        self._desenhar_heroi_equipado(surface)
    def _desenhar_item(self, surface: pygame.Surface) -> None:
        """A pocao no chao, com um brilho para o jogador achar.

        O desenho e um frasco pequeno de Purpose: e menos informacao que
        um sprite, mas nao depende de nenhum arquivo de arte e aparece
        em qualquer cenario. Um item invisivel nao ensina nada.
        """
        if self.item_no_chao is None:
            return
        w, h = self.size
        px = int(self.item_no_chao.x - self.camera.x + w // 2)
        py = int(self.item_no_chao.y - self.camera.y + h // 2)
        pulso = theme.pulse(self.time)

        # halo pulsando no chao
        raio = int(self.tile * 0.42 + pulso * 3)
        halo = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
        pygame.draw.circle(halo, (198, 168, 102, 40 + int(40 * pulso)),
                           (raio, raio), raio)
        surface.blit(halo, (px - raio, py - raio))

        # frasco
        altura = max(6, self.tile // 3)
        largura = max(4, altura // 2)
        corpo = pygame.Rect(px - largura // 2, py - altura // 2, largura, altura)
        pygame.draw.rect(surface, (176, 60, 58), corpo)
        pygame.draw.rect(surface, (24, 20, 18), corpo, 1)
        gargalo = pygame.Rect(px - largura // 4, corpo.top - 3,
                              max(2, largura // 2), 4)
        pygame.draw.rect(surface, (196, 188, 172), gargalo)
        pygame.draw.rect(surface, (24, 20, 18), gargalo, 1)

        theme.text_tracked_at(
            surface, "E para pegar", 13, (px - 34, corpo.bottom + 4),
            theme.GOLD)

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
            # o mesmo enlarge do heroi: com o enlarge padrao de
            # `load_foe` o esqueleto saia com 32px dentro de um tile de
            # 16, o dobro de tudo que estava em volta
            quadros = assets.load_foe(
                assets.FOE_KINDS[0], "oeste", "walk",
                scale=assets.get_sprite_scale(),
            )
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

    def _desenhar_inventario_mundo(self, surface: pygame.Surface) -> None:
        # o submenu de equipamento e um submenu, nao uma segunda janela:
        # desenhado por cima do inventario os dois painéis caiam no mesmo
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
        """Deixa a fogueira no chao da sala do jogador, se houver.

        A fogueira NAO esta na sala 5. A ultima sala e o lugar onde nao
        se descansa, e e por isso que a regra do recambio do chefe
        funciona: nao existe um lugar seguro para recuar.
        """
        self.fogueira_ativa = None
        self.fogueira_pos = None
        centro = self.mapa.centro_da_sala(self.sala_atual)
        if centro is None:
            return
        f = fogueira_mod.da_sala(self.cenario.nome.lower(), self.sala_atual)
        if f is None:
            return
        for dx, dy in ((-2, 2), (2, 2), (0, 3), (-3, 1), (3, 1)):
            alvo = (centro[0] + dx, centro[1] + dy)
            if self.mapa.andavel(*alvo):
                self.fogueira_ativa = f
                self.fogueira_pos = pygame.Vector2(
                    self.mapa.para_pixels(*alvo, self.tile)
                )
                return

    def _perto_da_fogueira(self) -> bool:
        if self.fogueira_pos is None:
            return False
        return self.fogueira_pos.distance_to(self.posicao) <= fogueira_mod.ALCANCE

    def _descansar(self) -> None:
        """Descanso: vida cheia, pocoes repostas, save na hora.

        Descansar ja salva. Um descanso que nao gravasse deixaria o
        jogador com a vida cheia e o save de antes da luta, e um
        Ctrl+Z nao existe neste jogo.
        """
        p = self.progresso
        self.estado.descansar(fogueira_mod.POCOES_DO_DESCANSO)
        p.itens["pocao"] = p.itens.get("pocao", 0) + fogueira_mod.POCOES_DO_DESCANSO
        if self.fogueira_ativa is not None:
            self.estado.fogueira = self.fogueira_ativa.chave
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
            # o boneco encolhe para a faixa da linha. Com a altura
            # inteira ele transbordava 46px para cima e a primeira
            # linha invadia a barra de EQUIPMENT
            if arte is None:
                texto_x = linha.x + 2
            else:
                pequeno = ui_arte._caber_pequeno(
                    arte, ui_arte.lado_do_desenho(linha))
                surface.blit(pequeno, pequeno.get_rect(
                    midleft=(linha.x + 2, linha.centery)))
                texto_x = linha.x + pequeno.get_width() + 8
            theme.text_tracked_at(
                surface, c.rotulo, 13, (texto_x, linha.y + 2), cor)
        theme.text_tracked_at(
            surface, "enter usa   esc volta", 12,
            (miolo.x, miolo.bottom + 6), theme.TEXT_DIM)
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
        arte = assets.equipado_na_tela(chave, assets.get_sprite_scale())
        if arte is not None:
            surface.blit(arte, arte.get_rect(
                center=(int(self.posicao.x - self.camera.x + self.size[0] // 2),
                        int(self.posicao.y - self.camera.y + self.size[1] // 2))))
            return
        # sem o desenho do conjunto, cai na animacao do pacote
        quadros = self.frames
        if quadros:
            sprite = quadros[int(self.anim_time * 8) % len(quadros)]
            surface.blit(sprite, sprite.get_rect(
                center=(int(self.posicao.x - self.camera.x + self.size[0] // 2),
                        int(self.posicao.y - self.camera.y + self.size[1] // 2))))

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




