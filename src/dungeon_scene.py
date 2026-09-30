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
            # escuro nas sombras, sem estourar o branco
            v = 10 + cinza * 0.86
            if v > 210:
                v = 210
            img.set_at(
                (x, y),
                (int(v * 0.93), int(v * 0.96), int(v * 1.0), a),
            )
    return img


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
                # duas casas a leste do caixao, se tiver chao
                cx = self.mapa.caixao[0] + 3
                cy = self.mapa.caixao[1]
                if self.mapa.andavel(cx, cy):
                    self.esqueleto = pygame.Vector2(
                        self.mapa.para_pixels(cx, cy, self.tile)
                    )
                    self.esqueleto_vivo = True
                    self.tutorial.mostrar("O esqueleto acordou")
            return

        if not self.esqueleto_vivo:
            return
        if self.esqueleto.distance_to(self.posicao) < ALCANCE_LUTA:
            self.esqueleto_vivo = False
            self.manager.iniciar_combate(1)
            return
        # some da tela assim que a luta comeca
        self.esqueleto = None
        self.esqueleto_vivo = False

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
        escala = self.tile != TILE_BASE
        for y in range(max(0, y0 - 1), min(self.mapa.altura, y1 + 2)):
            for x in range(max(0, x0 - 1), min(self.mapa.largura, x1 + 2)):
                celula = self.mapa.em(x, y)
                if celula == PAREDE:
                    indice = TILES_PAREDE[(x + y) % len(TILES_PAREDE)]
                elif celula in ENFEITES:
                    indice = ENFEITES[celula]
                else:
                    indice = TILES_CHAO[(x * 3 + y * 5) % len(TILES_CHAO)]
                pedaco = tileset.subsurface(
                    pygame.Rect(indice[0] * TILE_BASE, indice[1] * TILE_BASE,
                                TILE_BASE, TILE_BASE)
                )
                if escala:
                    pedaco = pygame.transform.scale(pedaco, (self.tile, self.tile))
                surface.blit(
                    pedaco,
                    (x * self.tile - self.camera.x + w // 2 - self.tile // 2,
                     y * self.tile - self.camera.y + h // 2 - self.tile // 2),
                )

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
        """O esqueleto parado, antes da luta."""
        quadros = assets.load_foe(assets.FOE_KINDS[0], "oeste", "walk")
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
        """A dica da vez, no alto, sem cobrir a acao.

        A aula some sozinha quando o jogador faz o que ela ensina. Ela
        nunca bloqueia o controle: e um aviso, nao um painel.
        """
        aula = self.tutorial.atual
        if aula is None:
            return
        w, h = self.size
        # entra esmaecendo, para nao aparecer de uma vez
        alpha = min(255, int(self.tutorial.tempo * 420))
        if alpha <= 0:
            return
        y = int(h * 0.62)
        cor = theme.lerp(theme.BACKGROUND, theme.TEXT_BRIGHT, alpha / 255)
        theme.text_tracked_at(
            surface, aula.texto, 19, (int(w * 0.06), y), cor, alpha=alpha
        )
        if aula.detalhe:
            detalhe = theme.lerp(theme.BACKGROUND, theme.TEXT_DIM, alpha / 255)
            theme.text_tracked_at(
                surface, aula.detalhe, 14, (int(w * 0.06), y + 24),
                detalhe, alpha=alpha,
            )

    def _desenhar_hud(self, surface: pygame.Surface) -> None:
        if self.fase != "livre":
            return
        w, h = self.size
        voltar = "/".join(self.controls.labels("voltar")) or "esc"
        salvar = "/".join(self.controls.labels("salvar")) or "f5"

        theme.text_tracked_at(surface, "CATACUMBAS", 16, (28, 34), theme.TEXT_DIM)
        # tempo de jogo, no canto oposto: e o que o jogador olha para
        # saber se vale a pena continuar
        theme.text_tracked_right(
            surface, formatar_tempo(self.tempo_jogado), 16, w - 28, 34,
            theme.TEXT_DIM,
        )
        theme.text_tracked_at(
            surface, f"{voltar} voltar    {salvar} salvar", 15,
            (28, h - 26), theme.HAIRLINE, tracking=1,
        )