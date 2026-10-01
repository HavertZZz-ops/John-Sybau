"""A massa solida do mapa: a parede que nao e parede de verdade.

O mapa e gerado cheio de `PAREDE` — pedra, mato, o interior de uma
colina. A grade de tiles so desenha o CHAO andavel, entao cada celula de
parede ficava com a cor do fundo, quase preta. A tela mostrava a
aldeia como um retangulo cercado de um buraco negro, e o preto era
indistinguivel de arte que falhou: o defeito lia como bug.

A pedra vira material com desenho de fiada. Ela e a mesma ideia de antes
(dar textura a parede), e ela ja falhou — duas vezes, e as duas com o
mesmo erro:

  - o degrade dentro do tile se repetia a cada 48 pixels e virava listra
    horizontal;
  - a variacao de tom entre pedras, de tres canais, saia como faixas de
    varias celulas de uma tonalidade so.

O erro era o MESMO nas duas: medir o contraste em canais absolutos. Num
mapa noturno, onde a pedra vive entre 24 e 33, seis canais de diferenca
sao 20% de mudanca relativa — e 20% se ve como listra. De dia, com a
pedra em torno de 100, os mesmos seis canais sao 5%: e textura, e nao
faixa. O que decide se a parede lista nao e o numero, e a diferenca
entre o numero e o tom em que ele cai.

Por isso a pedra nao tem um tom so. A cor vem da cena: a aldeia e a
estrada estao de dia e a parede delas e terra e mato claros; a
masmorra e a penumbra e a parede dela e rocha escura. Um tom unico
para as tres obrigava a escolher entre parede de dia que e quase preta e
parede de noite que e clara demais.

E a fiada e desenhada com o desfase pegando no hash da celula: sem
isso, todas as celulas desenham a junta na mesma posicao e a parede
vira uma colcha de retangulos identicos.
"""

from __future__ import annotations

import pygame

# O tom da pedra quando a cena nao diz nada. Escuro, para a masmorra.
BASE = (38, 34, 30)
# O tom de DIA, para a parede que fica fora da masmorra.
#
# Nao e o mesmo com mais luz: e outra coisa. De dia, o que fica em volta
# da aldeia e terra batida e mato seco ao sol, e nao rocha de caverna.
# Deixando o tom da noite, a aldeia ficava com um retangulo quase preto
# em volta, e a cena lia como buraco em vez de lugar.
BASE_DIA = (104, 96, 78)
# O quanto a junta e mais escura que a face da pedra, e o quanto o topo
# da fiada e mais claro.
#
# Este numero NAO e fixo, e essa e a correcao. A parede ja falhou duas
# vezes com textura, e as duas pelo mesmo motivo: o contraste foi medido
# em canais, e nao em relacao ao tom. Seis canais num tom de 38 (noite)
# sao 15% de mudanca e a parede lista; os mesmos seis num tom de 104
# (dia) sao 5% e a parede tem fiada. A proporcao decide se isto le como
# pedra ou como xadrez — entao o relevo segue o tom.
RELEVO_DE = 0.06


def relevo(tom: tuple[int, int, int]) -> int:
    """O relevo da fiada para este tom. Nunca zero, nunca listra."""
    return max(1, int(round(tom[0] * RELEVO_DE)))
_cache: dict[tuple[int, tuple[int, int, int], int], pygame.Surface] = {}


def _hash(x: int, y: int) -> int:
    h = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return h


def _variante(x: int, y: int) -> int:
    return _hash(x, y) % 4


def tile(lado: int, base: tuple[int, int, int] = BASE) -> pygame.Surface:
    """Uma pedra de `lado` pixels, cacheada por tamanho, cor e fiada."""
    achada = _cache.get((lado, base, 0))
    if achada is not None:
        return achada

    pedra = pygame.Surface((lado, lado))
    pedra.fill(base)

    # A fiada. A altura da fiada e em pixels de ARTE (a pedra e desenhada
    # no tamanho final, entao aqui ja e o tamanho de tela): a parede tem
    # de 4 a 5 fiadas por celula. Com fiada muito fina a parede vira
    # hachura; muito grossa, vira laje.
    fiada = max(6, lado // 5)
    r = relevo(base)
    sombra = tuple(max(0, c - r) for c in base)
    luz = tuple(min(255, c + r) for c in base)

    y = 0
    n = 0
    while y < lado:
        # a face da fiada, um canal mais clara embaixo: e a fiada de
        # baixo que pega a luz
        pygame.draw.rect(pedra, luz, pygame.Rect(0, y, lado, 1))
        # a junta entre esta fiada e a de baixo
        pygame.draw.rect(
            pedra, sombra, pygame.Rect(0, y + fiada - 1, lado, 1))
        y += fiada
        n += 1

    _cache[(lado, base, 0)] = pedra
    return pedra


def celula(
    lado: int,
    x: int = 0,
    y: int = 0,
    base: tuple[int, int, int] = BASE,
) -> pygame.Surface:
    """A pedra da celula (x, y), com a junta no lugar daquela celula.

    O desfase da junta vem do hash da celula. Sem ele, todas as celulas
    desenham a junta na mesma coluna e a parede vira uma colcha de
    retangulos identicos — que e o defeito que a pedra chapada estava
    escondendo, e que so aparece quando se ganha fiada.
    """
    variante = _variante(x, y)
    if variante == 0:
        return tile(lado, base)
    chave = (lado, base, variante)
    achada = _cache.get(chave)
    if achada is not None:
        return achada

    r = relevo(base)
    pedra = tile(lado, base).copy()
    sombra = tuple(max(0, c - r) for c in base)

    fiada = max(6, lado // 5)
    # quantas juntas verticais por fiada: poucas e largas, como pedra
    # de obra grande. A coluna de cada junta e o hash, entao a fiada
    # parece quebrada em pedacos de tamanho diferente entre as celulas.
    colunas = 2
    passo = lado / colunas
    deslocamento = (variante / colunas) * passo
    f = 0
    y = 0
    while y < lado:
        for c in range(colunas):
            # a junta comeca deslocada pela variante e senao todas as
            # celulas ficam com a junta na mesma coluna
            px = int(c * passo + deslocamento + (f % 2) * (passo / 2))
            px %= lado
            pygame.draw.rect(
                pedra, sombra, pygame.Rect(px, y, 1, min(fiada, lado - y)))
        y += fiada
        f += 1

    _cache[chave] = pedra
    return pedra


def limpar_cache() -> None:
    """Solta as pedras. Util quando a escala global muda."""
    _cache.clear()


