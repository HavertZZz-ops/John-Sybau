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
#
# Estes indices foram medidos no tileset anotado, e a primeira escolha
# estava errada: usei as pecas de tijolo da linha 0 achando que eram
# "parede". Elas sao a FACE de uma parede vista de lado, com o topo e a
# frente da pedra. Repetidas em grade, como um tabuleiro, viram um
# tijolo sem fim e o chao some dentro do padrao.
#
# O que funciona em vista de cima e o par de (6..8, 8) e (0..5, 11):
# a parede e pedra escura com a BORDA SUPERIOR CLARA, e o chao e a
# pedra clara com o motivo em losango. Escuro com brilho em cima le
# como parede; claro com motivo le como chao. A diferenca sozinha ja
# diz onde da para andar.
TILES_CHAO = ((1, 11), (2, 11), (3, 11), (4, 11), (0, 11), (5, 11))
TILES_PAREDE = ((6, 8), (7, 8), (8, 8))

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
    largura: int = 56,
    altura: int = 38,
    salas: int = 6,
    semente: int = 7,
) -> Mapa:
    """Gera salas conectadas por corredores, com saidas garantidas.

    A primeira sala e o ponto de partida e sempre recebe o caixao; a
    ultima recebe a saida. Semente fixa para o mapa ser sempre o
    mesmo entre execucoes: um cenario procedural que muda a cada
    boot impossible testar.

    As salas sao grandes de proposito. Com salas de 5x4 tiles e a tela
    mostrando 27x15, a sala cabia inteira na tela e o que aparecia em
    volta era so parede repetida: a tela virava um tabuleiro de
    tijolo, sem a sensacao de estar dentro de um lugar. Uma sala maior
    que a tela faz o jogador ver CHAO, com a parede so na borda.
    """
    rng = random.Random(semente)
    mapa = Mapa(largura, altura,
                [[PAREDE for _ in range(largura)] for _ in range(altura)])

    def carve(x0: int, y0: int, x1: int, y1: int) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                mapa.celulas[y][x] = CHAO

    boxes: list[tuple[int, int, int, int]] = []
    tentativas = 0
    while len(boxes) < salas and tentativas < 800:
        tentativas += 1
        w = rng.randint(13, 19)
        h = rng.randint(10, 14)
        x = rng.randint(1, largura - w - 2)
        y = rng.randint(1, altura - h - 2)
        if any(
            x < bx + bw + 3 and bx - 3 < x + w and
            y < by + bh + 3 and by - 3 < y + h
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

    _garantir_ligacao(mapa)
    return mapa


def _garantir_ligacao(mapa: Mapa) -> None:
    """Abre um caminho do caixao ate a saida, se faltou algum.

    Os corredores ligam as salas uma a uma, mas com salas grandes e
    margem de separacao grande as vezes sobra uma sala nao ligada, e a
    geracao termina com uma saida que ninguem alcanca. Achar o numero
    certo de tamanho e margem seria depender da sorte: e um gerador com
    semente fixa, entao bastaria um ajuste para quebrar de novo.

    Aqui a ligacao e garantida depois. Um corredor em L direto resolve,
    porque o mapa e um retangulo e qualquer ponto dele se liga a
    qualquer outro por dois trechos retos.
    """
    if mapa.caixao == mapa.saida:
        return
    if mapa.saida in alcancavel(mapa, mapa.caixao):
        return

    ax, ay = mapa.caixao
    bx, by = mapa.saida

    def abrir(x0: int, y0: int, x1: int, y1: int) -> None:
        passo = 1 if x1 >= x0 else -1
        for x in range(x0, x1 + passo, passo):
            mapa.celulas[ay][x] = CHAO
            mapa.celulas[by][x] = CHAO
        passo = 1 if y1 >= y0 else -1
        for y in range(y0, y1 + passo, passo):
            mapa.celulas[y][bx] = CHAO

    abrir(ax, ay, bx, by)
    # abre tambem em volta dos dois extremos, para o corredor ter largura
    for x in range(min(ax, bx) - 1, max(ax, bx) + 2):
        for dy in (-1, 0, 1):
            if 0 <= ay + dy < mapa.altura and 0 <= x < mapa.largura:
                mapa.celulas[ay + dy][x] = CHAO
            if 0 <= by + dy < mapa.altura and 0 <= x < mapa.largura:
                mapa.celulas[by + dy][x] = CHAO
    for y in range(min(ay, by) - 1, max(ay, by) + 2):
        for dx in (-1, 0, 1):
            if 0 <= y < mapa.altura and 0 <= ax + dx < mapa.largura:
                mapa.celulas[y][ax + dx] = CHAO
            if 0 <= y < mapa.altura and 0 <= bx + dx < mapa.largura:
                mapa.celulas[y][bx + dx] = CHAO

    # os enfeites nao podem fechar o caminho que acabou de ser aberto
    for y in range(mapa.altura):
        for x in range(mapa.largura):
            if mapa.celulas[y][x] in ENFEITES:
                mapa.celulas[y][x] = CHAO


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