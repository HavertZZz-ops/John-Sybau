"""A cena de combate: o que o jogador ve enquanto luta.

Esta cena tem uma responsabilidade que as outras nao tem: **ela precisa
fazer a fase do inimigo ser LEGIVEL**. O combate decide tudo em um
instante (`jogada_inimiga()` resolve a fase inteira de uma vez), mas se
a cena desenhasse o resultado de uma vez, o jogador veria tres linhas de
dano quase juntas e nao saberia de quem foi. Por isso a cena tem uma
fila: ela desenha UM evento por vez, com pausa no meio.

E por isso que o ritmo importa: `PAUSA_ENTRE_INIMIGOS` e o tempo entre
um golpe e o seguinte. Curto demais e o jogador nao ve nada; longo demais
e a luta vira espera.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pygame

import arte
import combat as C
import settings

# A pausa entre um evento de combate e o proximo, em segundos.
#
# 0.7 da tempo de ler de quem foi o golpe e ver a animacao. Abaixo de
# ~0.4 a fase inteira passa em menos de meio segundo e o jogador ve "tres
# linhas de dano" sem saber de quem — foi exatamente o defeito que o
# valor antigo de 0.45 produzia.
PAUSA_ENTRE_EVENTOS = 0.7

# Onde cada lado fica na tela. Porcentagem, e nao pixel: a tela e 800x600
# mas o layout tem de sobreviver a uma resolucao diferente sem virar
# codigo novo.
# o heroi fica a esquerda, os inimigos a direita. Nao e uma escolha
# estetica: o jogador precisa saber em menos de um quadro de quem e o
# golpe, e a posicao na tela e a pista mais forte que existe.
LADO_ESQUERDO = 0.26
LADO_DIREITO = 0.66

# A altura onde os lutadores ficam, em fracao da altura. Um pouco acima
# do centro, porque o rodape de vida ocupa a parte de baixo.
ALTURA_LUTADORES = 0.55

# O tamanho de um lutador desenhado. A altura e calculada da tela para
# caber em qualquer resolucao; a largura segue a proporcao do sprite.
ALTURA_LUTADOR = 0.42


@dataclass
class ItemAnimado:
    """Um numero de dano subindo e sumindo."""

    x: int
    y: float
    texto: str
    cor: tuple[int, int, int]
    vida: float = 1.2
    # o valor inicial, para a subida ser constante em vez de desacelerar
    # com a distancia — o numero tem que correr, nao flutuar
    y_inicial: float = 0.0

    def atualizar(self, delta: float) -> None:
        self.vida -= delta
        self.y -= delta * 60.0

    @property
    def vivo(self) -> bool:
        return self.vida > 0


class Combate:
    """A cena de combate: liga o modelo `combat` na tela."""

    def __init__(self, jogo) -> None:
        self.jogo = jogo

        # A luta. O heroi e criado aqui com numeros de nivel 1, e nao
        # vindos do jogador ainda: o combate precisa funcionar mesmo sem
        # um jogador com progresso, e foi assim que o primeiro esqueleto
        # ficou impossivel de matar antes do teste existir.
        self.luta = C.Batalha(self._criar_heroi())
        self.luta.adicionar(
            C.novo_inimigo(C.PERFIL_ESQUELETO),
        )

        # a fila de eventos a mostrar, um por vez
        self._fila: list[C.Evento] = []
        self._espera = 0.0

        # os numeros flutuantes
        self._flutuantes: list[ItemAnimado] = []

        # o menu do jogador
        self.menu_aberto = False
        self.opcao_escolhida = 0

    @staticmethod
    def _criar_heroi() -> C.Combatente:
        return C.Combatente(
            nome="John", vida=60, vida_max=60, forca=9, defesa=2
        )

    # --- ciclo da luta ---------------------------------------------------

    def atualizar(self, delta: float) -> None:
        """Avanca um quadro.

        A ordem aqui e o coracao da legibilidade:

          1. se ha evento na fila, ESPERA e mostra. Nao age.
          2. se a fila acabou e for a vez do heroi, ABRE o menu.
          3. se for a vez dos inimigos, joga a fase inteira e enche a fila.

        O passo 1 e o que impede a fase de resolver em um quadro: sem
        ele, os tres inimigos batem juntos e o jogador ve tres linhas de
        dano de uma vez.
        """
        # os numeros flutuantes andam sempre
        restantes = [f for f in self._flutuantes if f.vivo]
        for f in restantes:
            f.atualizar(delta)
        self._flutuantes = [f for f in restantes if f.vivo]

        if self.luta.concluida:
            # o proximo estado e decidido pela cena que chamou esta
            return

        if self._fila:
            # tem coisa para mostrar: espera antes de gerar mais
            self._espera -= delta
            if self._espera <= 0:
                self._espera = PAUSA_ENTRE_EVENTOS
                self._mostrar_proximo()
            return

        if self.luta.turno_do_heroi:
            if not self.menu_aberto:
                self.menu_aberto = True
                self.opcao_escolhida = 0
            return

        # vez dos inimigos: resolve a fase inteira e enfileira
        eventos = self.luta.jogada_inimiga()
        self._fila = list(eventos)
        if self._fila:
            self._mostrar_proximo()

    def _mostrar_proximo(self) -> None:
        """Pega o proximo evento da fila e vira numero na tela."""
        if not self._fila:
            return
        evento = self._fila.pop(0)
        self._registrar_dano(evento)

    def _registrar_dano(self, evento: C.Evento) -> None:
        """Joga um numero na tela, se o evento for de dano ou cura."""
        if evento.tipo not in ("dano", "cura"):
            return

        # o numero e a ultima palavra do texto ("... por 12"), e nao a
        # palavra inteira: o jogador quer o numero, e o texto ja esta no
        # log
        numero = evento.texto.split()[-1]

        # o numero nasce em cima de QUEM levou o dano: ai o jogador
        # enxerga de quem foi sem precisar ler o log
        if evento.tipo == "dano" and evento.texto.startswith(self.luta.heroi.nome):
            x = int(settings.LARGURA * LADO_ESQUERDO)
        else:
            x = int(settings.LARGURA * LADO_DIREITO)

        self._flutuantes.append(
            ItemAnimado(
                x=x,
                y=settings.ALTURA * ALTURA_LUTADORES,
                texto=numero if numero.isdigit() else evento.texto,
                cor=settings.VERMELHO if evento.tipo == "dano"
                else settings.VERDE,
                y_inicial=settings.ALTURA * ALTURA_LUTADORES,
            )
        )

    # --- entrada ---------------------------------------------------------

    def tratar_tecla(self, tecla: int) -> None:
        """Uma tecla do jogador durante o combate."""
        if self.luta.concluida:
            self.jogo.ir_para(FimDeCombate, venceu=self.luta.vencida,
                              fugiu=self.luta.fugiu)
            return

        if not self.menu_aberto:
            return

        # cima e baixo movem a escolha
        if tecla == pygame.K_w or tecla == pygame.K_UP:
            self.opcao_escolhida = (self.opcao_escolhida - 1) % 3
        elif tecla == pygame.K_s or tecla == pygame.K_DOWN:
            self.opcao_escolhida = (self.opcao_escolhida + 1) % 3
        elif tecla == pygame.K_a or tecla == pygame.K_LEFT:
            self._escolher_opcao()
        elif tecla == pygame.K_d or tecla == pygame.K_RIGHT:
            self._escolher_opcao()
        elif tecla in (pygame.K_RETURN, pygame.K_SPACE):
            self._escolher_opcao()

    OPCOES = (
        C.AcaoHeroi.ATACAR,
        C.AcaoHeroi.DEFENDER,
        C.AcaoHeroi.FUGIR,
    )

    def _escolher_opcao(self) -> None:
        """O jogador confirmou a acao escolhida."""
        acao = self.OPCOES[self.opcao_escolhida]
        self.menu_aberto = False
        eventos = self.luta.acao_do_heroi(acao)

        if self.luta.fugiu or self.luta.concluida:
            self.jogo.ir_para(FimDeCombate, venceu=self.luta.vencida,
                              fugiu=self.luta.fugiu)
            return

        # O turno do heroi virou em uma acao so: o evento entra na MESMA
        # fila dos inimigos, para o jogador ver o golpe dele antes do
        # deles. E o que faz a rodada parecer uma rodada.
        self._fila = list(eventos)
        if self._fila:
            self._mostrar_proximo()

    # --- desenho ---------------------------------------------------------

    def desenhar(self, tela: pygame.Surface) -> None:
        tela.fill((18, 16, 22))

        self._desenhar_lutadores(tela)
        self._desenhar_barras(tela)
        self._desenhar_inimigos(tela)
        self._desenhar_flutuantes(tela)
        self._desenhar_menu(tela)

    def _desenhar_lutadores(self, tela: pygame.Surface) -> None:
        """Os dois lados, na posicao de cada um."""
        altura = int(settings.ALTURA * ALTURA_LUTADOR)
        base = int(settings.ALTURA * ALTURA_LUTADORES)

        heroi = self.luta.heroi
        destino = pygame.Rect(
            int(settings.LARGURA * LADO_ESQUERDO) - altura // 3,
            base - altura,
            altura // 3 * 2,
            altura,
        )
        sprite = arte.carregar_sprite("heroi/idl_sul.png",
                                      escala=settings.ESCALA_SPRITE)
        if sprite is not None:
            tela.blit(
                pygame.transform.scale(sprite, (destino.width, destino.height)),
                destino,
            )

        # o inimigo vem do perfil dele. Antes era pelo indice da lista, e
        # um guardiao aparecia com a arte do esqueleto.
        inimigo = self.luta.inimigos_vivos[0] if self.luta.inimigos_vivos else None
        if inimigo is not None:
            base_sprite = C.SPRITE_DO_PERFIL.get(
                inimigo.perfil.nome if inimigo.perfil else "esqueleto",
                "inimigos/esqueleto",
            )
            sprite = arte.carregar_sprite(f"{base_sprite}_sul.png",
                                          escala=settings.ESCALA_SPRITE)
            if sprite is not None:
                destino = pygame.Rect(
                    int(settings.LARGURA * LADO_DIREITO) - altura // 3,
                    base - altura,
                    altura // 3 * 2,
                    altura,
                )
                tela.blit(
                    pygame.transform.scale(
                        sprite, (destino.width, destino.height)
                    ),
                    destino,
                )

    def _desenhar_barras(self, tela: pygame.Surface) -> None:
        """Barra de vida do heroi e o nome de cada um."""
        largura = int(settings.LARGURA * 0.22)
        x = int(settings.LARGURA * LADO_ESQUERDO) - largura // 2
        y = int(settings.ALTURA * 0.12)

        self._barra(
            tela, pygame.Rect(x, y, largura, 10),
            self.luta.heroi.fracao_vida, settings.VERDE,
        )
        _texto(tela, self.luta.heroi.nome, (x, y - 20), settings.BRANCO)

        # o nome e a intencao de cada inimigo: o telegrafo na tela. E o
        # que permite planejar em vez de reagir.
        for indice, inimigo in enumerate(self.luta.inimigos_vivos):
            ix = int(settings.LARGURA * LADO_DIREITO) - largura // 2
            iy = int(settings.ALTURA * 0.12) + indice * 34

            self._barra(tela, pygame.Rect(ix, iy, largura, 10),
                        inimigo.fracao_vida, settings.VERMELHO)
            cor = (
                settings.OURO
                if self.luta.vai_fugir(inimigo)
                else settings.BRANCO
            )
            _texto(
                tela,
                f"{inimigo.nome} — {self.luta.intencao_de(inimigo)}",
                (ix, iy - 20), cor,
            )

    @staticmethod
    def _barra(
        tela: pygame.Surface,
        caixa: pygame.Rect,
        fracao: float,
        cor: tuple[int, int, int],
    ) -> None:
        """Uma barra de vida."""
        pygame.draw.rect(tela, (40, 38, 46), caixa)
        pygame.draw.rect(
            tela, cor,
            pygame.Rect(caixa.x, caixa.y,
                        int(caixa.width * fracao), caixa.height),
        )
        pygame.draw.rect(tela, (16, 15, 20), caixa, 1)

    def _desenhar_inimigos(self, tela: pygame.Surface) -> None:
        """A barra de vida embaixo de cada lado."""
        fonte = pygame.font.Font(None, 18)
        texto = fonte.render(self.luta.resumo(), True, settings.CINZA)
        tela.blit(texto, (10, settings.ALTURA - 26))

    def _desenhar_flutuantes(self, tela: pygame.Surface) -> None:
        """Os numeros de dano subindo."""
        fonte = pygame.font.Font(None, 34)
        for f in self._flutuantes:
            cor = cor_com_opacidade(f.cor, f.vida / 1.2)
            desenho = fonte.render(f.texto, True, cor)
            tela.blit(desenho, (f.x - desenho.get_width() // 2, int(f.y)))

    def _desenhar_menu(self, tela: pygame.Surface) -> None:
        """O menu de acao, quando for a vez do jogador.

        Aparece embaixo do heroi e nao no meio da tela: no meio, ele
        cobriria o combate. E embaixo porque e onde o olhar ja esta, depois
        de acompanhar o golpe.
        """
        if not self.menu_aberto:
            return

        acoes = ("Atacar", "Defender", "Fugir")
        largura = 260
        altura = 30 * len(acoes) + 24
        x = int(settings.LARGURA * LADO_ESQUERDO) - largura // 2
        y = int(settings.ALTURA * 0.62)

        painel = pygame.Surface((largura, altura), pygame.SRCALPHA)
        painel.fill((12, 11, 16, 220))
        pygame.draw.rect(painel, settings.CINZA, painel.get_rect(), 1)
        tela.blit(painel, (x, y))

        fonte = pygame.font.Font(None, 24)
        for indice, acao in enumerate(acoes):
            ay = y + 12 + indice * 30
            escolhida = indice == self.opcao_escolhida
            cor = settings.OURO if escolhida else settings.CINZA
            if escolhida:
                pygame.draw.rect(
                    tela, (60, 50, 20),
                    pygame.Rect(x + 4, ay - 4, largura - 8, 28),
                )
            tela.blit(fonte.render(acao, True, cor), (x + 16, ay))


class FimDeCombate:
    """A tela depois da luta. Registra no ranking e volta a explorar."""

    def __init__(self, jogo, venceu: bool, fugiu: bool) -> None:
        self.jogo = jogo
        self.venceu = venceu
        self.fugiu = fugiu
        self.resultado = None
        self._tentou = False

    def atualizar(self, delta: float) -> None:
        import pygame as _pygame

        if not self._tentou:
            self._tentou = True
            self.resultado = self.jogo.registrar_vitoria(
                venceu=self.venceu, fugiu=self.fugiu
            )

        for evento in _pygame.event.get():
            if evento.type == _pygame.KEYDOWN:
                self.jogo.ir_para(Exploracao)

    def desenhar(self, tela: pygame.Surface) -> None:
        tela.fill(settings.PRETO)

        if self.fugiu:
            titulo, cor = "VOCE FUGIU", settings.CINZA
        elif self.venceu:
            titulo, cor = "VITORIA", settings.OURO
        else:
            titulo, cor = "VOCE CAIU", settings.VERMELHO

        _texto_centro(tela, titulo, int(settings.ALTURA * 0.3), cor, 36)

        # O resultado do envio aparece DEPOIS que ele volta. Sem isso, a
        # tela mostraria "enviando..." e o jogador fecharia o jogo sem
        # saber se gravou.
        if self.resultado is None:
            texto, cor = "enviando para o ranking...", settings.CINZA
        elif self.resultado.ok:
            texto, cor = "pontuacao registrada", settings.VERDE
        else:
            texto, cor = f"nao gravou: {self.resultado.erro}", settings.VERMELHO

        _texto_centro(tela, texto, int(settings.ALTURA * 0.45), cor, 20)
        _texto_centro(
            tela, "aperte uma tecla para voltar", int(settings.ALTURA * 0.7),
            settings.CINZA,
        )


# --- texto -----------------------------------------------------------------


def _texto(
    tela: pygame.Surface,
    conteudo: str,
    posicao: tuple[int, int],
    cor: tuple[int, int, int],
    tamanho: int = 18,
) -> None:
    fonte = pygame.font.Font(None, tamanho)
    tela.blit(fonte.render(conteudo, True, cor), posicao)


def _texto_centro(
    tela: pygame.Surface,
    conteudo: str,
    y: int,
    cor: tuple[int, int, int],
    tamanho: int = 18,
) -> None:
    fonte = pygame.font.Font(None, tamanho)
    desenho = fonte.render(conteudo, True, cor)
    tela.blit(desenho, ((tela.get_width() - desenho.get_width()) // 2, y))


def cor_com_opacidade(
    cor: tuple[int, int, int], fracao: float
) -> tuple[int, int, int]:
    """Esmaece a cor conforme a fracao de vida do item.

    A cor vai para o PRETO, e nao para o branco: esmaecer para o branco
    faria o numero sumir aparecendo em claro no fundo escuro, que e o
    oposto de sumir.
    """
    f = max(0.0, min(1.0, fracao))
    return tuple(int(c * f) for c in cor)