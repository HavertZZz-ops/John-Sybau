"""O passo do heroi, feito no codigo em vez de na arte.

O pacote de mercado traz um personagem andando, e ele traz uma espada
na mao. O jogo tem seis conjuntos, e tres deles (punho, escudo, e o
heroi no comeco) nao tem espada nenhuma. Trocar entre o desenho
equipado e a animacao do pacote a cada passo fazia o heroi piscar de
desenho e aparecer com a espada so quando andava.

Aqui o sprite equipado e animado por conta propria: um passo de duas
batidas, como um passo de verdade, com o corpo subindo duas vezes por
ciclo, inclinando para o lado e achatando na aterrissagem. O desenho do
personagem nunca muda, a arma nunca mente, e vale para os seis
conjuntos de uma vez.

O mesmo movimento, na mesma funcao, nas quatro cenas do mundo. Se cada
cena tivesse o seu, elas divergiriam na segunda edicao.

Tudo e medido em FRACAO DA ALTURA DO SPRITE, e nao em pixels: o jogo
pode escalar o desenho de 1x a 4x nas opcoes, e um passo de dois pixels
que some num sprite de 64 vira um tremor de meio pixel quando o mesmo
desenho e ampliado quatro vezes.
"""
from __future__ import annotations

import math

import pygame

# o quanto o corpo sobe no ponto mais alto do passo, em fracao da altura
BALANCO = 0.045
# o quanto o corpo desliza para o lado, em fracao da altura
INCLINACAO = 0.020
# o quanto o corpo achata quando o pe toca o chao, em fracao
ACHATAMENTO = 0.055
# o quanto o corpo estica quando esta no alto, em fracao
ESTICAO = 0.030
# o balancer de respiro de quem esta parado, em fracao da altura
RESPIRO = 0.016
# quadros por segundo do passo andando
FPS_PASSO = 8.0
# o quanto a corrida acelera o passo
FATOR_CORRIDA = 1.55

# quantos tiles vale um aperto de direcao. O corredor do mundo e passo a
# passo, e meio tile por aperto e curto demais para andar ate a taverna.
# Com Shift o aperto vale um tile inteiro: o olho le como dois passos
# seguidos, e nao como um teleporte.
PASSO_ANDAR = 0.5
PASSO_CORRIDA = 1.0

# o mesmo Shift, para as cenas em que o passo e continuo e nao por
# aperto: la o que muda e a velocidade, e nao o tamanho do passo
FATOR_PASSO = FATOR_CORRIDA


def fator_passo(correndo: bool) -> float:
    """O quanto o deslocamento do heroi e multiplicado."""
    return FATOR_PASSO if correndo else 1.0


def correndo_agora() -> bool:
    """Se o Shift esta apertado neste instante.

    O Shift e lido do teclado e nao do evento: o jogador segura a
    direcao e o Shift decide o tamanho do passo enquanto ele caminha, e
    um evento so contaria o que aconteceu no primeiro quadro.
    """
    return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

# a altura do desenho a que as fracoes acima se aplicam. As cenas
# passam a altura real; este e so o valor quando alguem nao passa nada.
ALTURA_PADRAO = 64


class Passo:
    """O estado do passo de um personagem, com a fase ja acumulada.

    As cenas guardam um destes e Advance() ele a cada quadro, em vez de
    recalcular a fase de um tempo que anda e para. Um `tempo` que so
    corre quando o personagem anda ja serve para o passo, mas o
    respiro de quem esta parado precisa de um relogio que nunca para.
    """

    __slots__ = ("fase", "respiro", "correndo")

    def __init__(self) -> None:
        self.fase = 0.0
        self.respiro = 0.0
        self.correndo = False

    def advance(self, dt: float, movendo: bool) -> None:
        """Avanca o passo. O respiro anda sempre, andando ou nao."""
        self.respiro = (self.respiro + dt) % 1.0
        if movendo:
            velocidade = FPS_PASSO * (FATOR_CORRIDA if self.correndo else 1.0)
            # dois tempos por ciclo: o pe que bate e o outro que volta
            self.fase = (self.fase + dt * velocidade) % 1.0
        else:
            # parado, o passo volta para o primeiro tempo em vez de
            # parar no meio de uma batida: e o que evita o personagem
            # congelar com o pe no ar quando o jogador solta a tecla
            self.fase = 0.0

    def deslocamento(
        self,
        altura: int = ALTURA_PADRAO,
        lado: int = 0,
        movendo: bool = True,
    ) -> tuple[int, int, tuple[float, float]]:
        """`(y, x, (fator_x, fator_y))` para desenhar este quadro.

        `lado` e -1, 0 ou 1, o sinal do deslize lateral. Quem olha de
        perfil pisa para a frente, quem olha de frente pisa para o lado.
        """
        if not movendo:
            sobe = math.sin(self.respiro * math.tau) * RESPIRO * altura
            return int(round(sobe)), 0, (1.0, 1.0)

        onda = abs(math.sin(self.fase * math.tau))
        y = -onda * BALANCO * altura

        # a inclinacao e o dobro da frequencia do balaanco: o corpo
        # pende para um lado no primeiro tempo e para o outro no segundo
        deslize = math.cos(self.fase * math.tau * 2.0) * INCLINACAO * altura
        x = int(round(deslize)) * (1 if lado >= 0 else -1)

        achatamento = (1.0 - onda) * ACHATAMENTO
        esticamento = onda * ESTICAO
        return (
            int(round(y)),
            x,
            (1.0 + esticamento, 1.0 - achatamento),
        )


def aplicar(
    sprite: pygame.Surface,
    passo: Passo,
    altura: int,
    lado: int = 0,
    movendo: bool = True,
    escala: int = 1,
) -> pygame.Surface:
    """O desenho do personagem neste quadro do passo.

    O escalonamento e feito aqui e nao pela cena porque o Y tem de
    acompanhar a escala: esticar a altura depois de aplicar o passo
    faria o personagem piscar de tamanho a cada batida.
    """
    y, x, (fx, fy) = passo.deslocamento(altura, lado, movendo)
    alvo = sprite.get_size()
    novo = (
        max(1, int(round(alvo[0] * escala * fx))),
        max(1, int(round(alvo[1] * escala * fy))),
    )
    if novo != alvo:
        # escala por um inteiro conserva a pixel art; o achatamento e
        # sub-pixel de proposito e usa o filtro do pygame
        sprite = pygame.transform.smoothscale(sprite, novo)
    copia = sprite.copy()
    if y or x:
        copia = _deslocar(copia, x, y)
    return copia


def _deslocar(sprite: pygame.Surface, x: int, y: int) -> pygame.Surface:
    """Move o desenho sem mexer no retangulo que o ancora."""
    fundo = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
    fundo.blit(sprite, (x, y))
    return fundo


def sombra(
    largura: int,
    altura_sombra: int,
    passo: Passo,
    movendo: bool = True,
) -> pygame.Surface:
    """A sombra no chao, que encolhe quando o corpo sobe.

    Sem isso o personagem parece deslizar: o desenho sobe mas a sombra
    fica igual, e o olho le o sprite colado no chao.
    """
    y, _x, _f = passo.deslocamento(altura_sombra * 6, 0, movendo)
    fracao = max(0.45, min(1.0, 1.0 + y / (altura_sombra * 6.0) * 0.5))
    s = pygame.Surface(
        (max(4, int(largura * fracao)), max(3, int(altura_sombra * fracao))),
        pygame.SRCALPHA,
    )
    pygame.draw.ellipse(s, (0, 0, 0, 85), s.get_rect())
    return s


# quem olha de frente pisa para o lado; quem olha de perfil, para a
# frente. Sem isso o personagem de frente andava sem sair do lugar.
_LADO_POR_DIRECAO = {
    "norte": 0, "sul": 0, "leste": 1, "oeste": -1,
}


def _poeira_de_corrida(
    surface: pygame.Surface,
    rect: pygame.Rect,
    passo: Passo,
    tile: int,
) -> None:
    """As marcas de poeira atras dos pes de quem corre.

    Sem isso a corrida so existe na velocidade do sprite: um boneco
    andando mais depressa numa tela parada parece o mesmo boneco
    andando mais depressa. A poeira diz que o chao esta sendo comido.
    """
    if not passo.correndo:
        return
    # uma marca por batida de pe, alternando os lados. O tamanho e a
    # cor sao exagerados de proposito: poeira de verdade neste tamanho
    # de tela some, e o que precisa aparecer e que o chao foi comido
    marca = int(passo.fase * 2.0) % 2
    chao = rect.bottom - int(tile * 0.08)
    for indice, (lado, tamanho, alpha) in enumerate((
        (-1.0, 0.26, 105),
        (1.0, 0.20, 78),
    )):
        if indice != marca:
            continue
        raio = max(3, int(tile * tamanho))
        marca_ = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            marca_, (214, 196, 156, alpha), (raio, raio), raio
        )
        surface.blit(marca_, marca_.get_rect(
            centerx=rect.centerx + int(lado * tile * 0.26),
            centery=chao - raio // 2,
        ))


def desenhar_heroi(
    surface: pygame.Surface,
    arte: pygame.Surface,
    passo: Passo,
    centro: tuple[int, int],
    direcao: str = "sul",
    movendo: bool = False,
    tile: int = 32,
    com_sombra: bool = True,
    espelhar: bool = False,
) -> None:
    """Desenha o heroi do mundo: sombra, passo e o desenho por cima.

    Todas as quatro cenas do mundo passam por aqui. Cada uma tinha o
    seu `blit` e o seu jeito de ancorar, e o resultado era o mesmo
    personagem com a sombra em um lugar e o passo em outro.
    """
    lado = _LADO_POR_DIRECAO.get(direcao, 0)
    if espelhar and direcao == "oeste":
        arte = pygame.transform.flip(arte, True, False)

    y, x, (fx, fy) = passo.deslocamento(arte.get_height(), lado, movendo)
    desenho = arte
    if (fx, fy) != (1.0, 1.0):
        desenho = pygame.transform.smoothscale(
            arte,
            (max(1, int(arte.get_width() * fx)),
             max(1, int(arte.get_height() * fy))),
        )

    cx, cy = centro
    rect = desenho.get_rect(center=(cx, cy + y))

    if com_sombra:
        largura = int(tile * 0.62)
        altura = max(4, int(tile * 0.20))
        # a sombra fica no chao, entao ela NAO acompanha o balaanco do
        # corpo: e a base do personagem que a ancora
        sombra_ = sombra(largura, altura, passo, movendo)
        surface.blit(sombra_, sombra_.get_rect(
            centerx=rect.centerx, bottom=rect.bottom - int(tile * 0.10)))

    _poeira_de_corrida(surface, rect, passo, tile)

    surface.blit(desenho, (rect.x + x, rect.y))