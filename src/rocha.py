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
# O entorno da ESTRADA, que e terra e nao pedra.
#
# A estrada usa o mesmo tom de dia da aldeia e ficava como um retangulo
# afundado: o solo clareia a cena inteira por igual, entao ele nao muda a
# diferenca entre a terra da estrada e o entorno — so levanta os dois. O
# que faz o terreno ler como buraco e a DIFFERENCA, e nao o nivel.
#
# Entao o entorno da estrada e terra tambem, e mais perto do chao dela.
# A aldeia fica com pedra, porque em volta de um calçamento de aldeia o
# entorno e calçamento velho e muro; na estrada, e terra batida.
BASE_TERRA = (52, 47, 38)
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
# a variante de cada celula, lembrada. `celula` e chamada milhares de
# vezes por quadro (a tela inteira, a cada quadro) e recalcular o hash a
# cada chamada, mesmo com a pedra ja em cache, era metade do custo da
# cena. O hash e puro: repetir a conta da o mesmo numero, todo quadro,
# sem nenhum ganho.
_variantes: dict[tuple[int, int], int] = {}
# a tela de fundo pronta, por posicao da camera. O fundo e estatico: e a
# mesma pedra no mesmo lugar ate a camera cruzar de celula. Desenhar as
# miles de celulas de novo a cada quadro era o que segurava o jogo em
# menos de 60 FPS.
_telas: dict[tuple, pygame.Surface] = {}


def _hash(x: int, y: int) -> int:
    h = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return h


def _variante(x: int, y: int) -> int:
    chave = (x, y)
    achada = _variantes.get(chave)
    if achada is None:
        achada = _hash(x, y) % 4
        _variantes[chave] = achada
    return achada


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


def campo(
    surface: pygame.Surface,
    lado: int,
    camera_x: float = 0.0,
    camera_y: float = 0.0,
    base: tuple[int, int, int] = BASE,
) -> None:
    """Preenche a tela toda com a mesma pedra, celula por celula.

    E o fundo das cenas de fora. Encher com a cor chapada e mais
    rapido, mas deixa uma linha visivel onde o preenchimento encontra a
    alvenaria desenhada: o lado de dentro tem fiada e o de fora nao. O
    terreno e o mesmo dos dois lados, e o preto aparecia em volta da
    aldeia.

    Aqui o fundo usa a MESMA pedra, com o mesmo hash por celula, entao a
    fiada continua de uma ponta a outra da tela. A emenda some porque
    as duas pontas sao a mesma parede, e nao duas paredes.

    A camera entra para a pedra ficar ancorada no mapa. Sem ela, o
    fundo nadaria por baixo do mapa quando a camera andasse, e a
    fiada da tela passaria por cima da fiada desenhada.

    O fundo e montado UMA VEZ por posicao de camera e depois e uma blit
    so. Montar a tela inteira a cada quadro custava milhares de blits
    por quadro — era o gargalo do jogo. A tela so e refeita quando a
    camera cruza uma celula, porque ate la o resultado e identico.
    """
    w, h = surface.get_size()
    cx0 = int(camera_x // lado)
    cy0 = int(camera_y // lado)
    margem = lado
    chave = (lado, base, cx0, cy0, w, h)
    tela = _telas.get(chave)
    if tela is None:
        tela = pygame.Surface((w + margem * 2, h + margem * 2))
        for cy in range(cy0 - 1, cy0 + h // lado + 3):
            for cx in range(cx0 - 1, cx0 + w // lado + 3):
                tela.blit(
                    celula(lado, cx, cy, base),
                    ((cx - cx0 + 1) * lado, (cy - cy0 + 1) * lado),
                )
        # so as duas ultimas linhas de cache sao necessarias para a
        # camera andar: a anterior e a nova. Mais que isso e memoria
        # gastas com uma tela que ninguem vai pedir de novo.
        for antiga in [k for k in _telas if len(_telas) > 4 and k != chave]:
            del _telas[antiga]
        _telas[chave] = tela
    surface.blit(tela, (cx0 * lado - int(camera_x), cy0 * lado - int(camera_y)))


def limpar_cache() -> None:
    """Solta as pedras. Util quando a escala global muda."""
    _cache.clear()


