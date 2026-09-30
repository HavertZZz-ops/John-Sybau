"""Mapa da masmorra: geracao, tiles e colisao.

Separado da cena para poder ser testado sem pygame: `gerar_mapa` e
`alcancavel` sao funcoes puras, e e assim que o teste garante que o
jogador consegue sair do caixao e andar ate o fim do cenario.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

# tipos de celula
CHAO = "."
PAREDE = "#"

# indices (coluna, linha) dentro do tileset da masmorra.
# Escolhidos olhando o tileset anotado: a fileira 11 e o chao de pedra
# com losango, e as duas primeiras sao a parede de tijolo escuro.
TILES_CHAO = ((1, 11), (2, 11), (3, 11), (4, 11), (0, 11), (5, 11))
TILES_PAREDE = ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1))

# enfeites opacos que podem ficar no chao
ENFEITES = {
    "o": (10, 7),   # talha de barro
    "d": (7, 7),    # entulho de pedra
    "s": (9, 7),    # laje de pedra
}


@dataclass
class Mapa:
    """Grade da masmorra, com a posicao do caixao."""

    largura: int
    altura: int
    celulas: list[list[str]] = field(default_factory=list)
    caixao: tuple[int, int] = (0, 0)
    saida: tuple[int, int] = (0, 0)

    def em(self, x: int, y: int) -> str:
        """Conteudo da celula, treating fora do mapa como parede."""
        if 0 <= y < self.altura and 0 <= x < self.largura:
            return self.celulas[y][x]
        return PAREDE

    def andavel(self, x: int, y: int) -> bool:
        """True se o jogador pode ocupar a celula."""
        return self.em(x, y) in (CHAO, *ENFEITES)

    def para_pixels(self, x: int, y: int, tile: int) -> tuple[float, float]:
        """Centro da celula em pixels de tela."""
        return (x * tile + tile / 2, y * tile + tile / 2)


def gerar_mapa(
    largura: int = 42,
    altura: int = 28,
    salas: int = 7,
    semente: int = 7,
) -> Mapa:
    """Gera salas conectadas por corredores, com saidas garantidas.

    A primeira sala e o ponto de partida e sempre recebe o caixao; a
    ultima recebe a saida. Semente fixa para o mapa ser sempre o
    mesmo entre execucoes: um cenario procedural que muda a cada
    boot impossible testar.
    """
    rng = random.Random(semente)
    mapa = Mapa(largura, altura,
                [[PAREDE for _ in range(largura)] for _ in range(altura)])

    def carve(x0: int, y0: int, x1: int, y1: int) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                mapa.celulas[y][x] = CHAO

    # salas retangulares, sem sobrepor, com folga de um tile de parede
    boxes: list[tuple[int, int, int, int]] = []
    tentativas = 0
    while len(boxes) < salas and tentativas < 500:
        tentativas += 1
        w = rng.randint(5, 9)
        h = rng.randint(4, 7)
        x = rng.randint(1, largura - w - 2)
        y = rng.randint(1, altura - h - 2)
        if any(
            x < bx + bw + 2 and bx - 2 < x + w and
            y < by + bh + 2 and by - 2 < y + h
            for bx, by, bw, bh in boxes
        ):
            continue
        boxes.append((x, y, w, h))

    for x, y, w, h in boxes:
        carve(x, y, x + w, y + h)

    # corredores ligando cada sala ate a seguinte
    for i in range(len(boxes) - 1):
        ax, ay, aw, ah = boxes[i]
        bx, by, bw, bh = boxes[i + 1]
        p1 = (ax + aw // 2, ay + ah // 2)
        p2 = (bx + bw // 2, by + bh // 2)
        if rng.random() < 0.5:
            carve(p1[0], p1[1], p2[0], p1[1])
            carve(p2[0], p1[1], p2[0], p2[1])
        else:
            carve(p1[0], p1[1], p1[0], p2[1])
            carve(p1[0], p2[1], p2[0], p2[1])

    # enfeites: so em celulas de chao, sem fechar caminho
    for y in range(altura):
        for x in range(largura):
            if mapa.celulas[y][x] != CHAO:
                continue
            if rng.random() < 0.04:
                mapa.celulas[y][x] = rng.choice(tuple(ENFEITES))

    # caixao no centro da primeira sala, saida no centro da ultima
    if boxes:
        x, y, w, h = boxes[0]
        mapa.caixao = (x + w // 2, y + h // 2)
        mapa.celulas[mapa.caixao[1]][mapa.caixao[0]] = CHAO
    if len(boxes) > 1:
        x, y, w, h = boxes[-1]
        mapa.saida = (x + w // 2, y + h // 2)
        mapa.celulas[mapa.saida[1]][mapa.saida[0]] = CHAO

    return mapa


def alcancavel(mapa: Mapa, origem: tuple[int, int]) -> set[tuple[int, int]]:
    """Celulas de chao que da para ir do inicio, em 4 direcoes."""
    vistos = {origem}
    fila = [origem]
    while fila:
        x, y = fila.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            viz = (x + dx, y + dy)
            if viz in vistos or not mapa.andavel(*viz):
                continue
            vistos.add(viz)
            fila.append(viz)
    return vistos


def validar(mapa: Mapa) -> list[str]:
    """Problemas do mapa, lista vazia quando esta bom.

    O teste usa isso: um mapa onde o caixao fica preso num canto sem
    saida parece correto na tela, e so aparece quando o jogador tenta
    andar.
    """
    problemas = []
    if mapa.caixao not in alcancavel(mapa, mapa.caixao):
        problemas.append("caixao nao alcanca nada")
    if mapa.caixao != mapa.saida:
        reached = alcancavel(mapa, mapa.caixao)
        if mapa.saida not in reached:
            problemas.append("saida inacessivel a partir do caixao")
        elif len(reached) < (larg := mapa.largura * mapa.altura) // 8:
            problemas.append(f"so {len(reached)} de {larg} celulas alcancaveis")
    return problemas