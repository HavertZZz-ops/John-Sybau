"""Detalhe espalhado no chao, para a tela deixar de ler como papel.

O zoom da estrada e da aldeia mostrou a planura: a mesma peca de chao
em todas as celulas, o mesmo tufo na mesma distancia, e a grade de
48px aparecendo. Ja se tentou quebrar isso variando a peca por celula
(andar dentro do lugar, mudar o tom) e deu PIOR: o tile e esparso, entao
andar a janela cortou os tufos ao meio, e o tom por celula pintou
quadrados visiveis. A grade sumiu, mas a arte ficou estragada.

Entao a peca fica como veio, e o que quebra a leitura e detalhe POR
CIMA: pedrinha, rachadura e mancha, em posicoes que nao repetem, e
pequenas o bastante para nao aparecerem quadrado nenhum.

Tres regras que valem para tudo aqui:

1. a posicao sai de um hash da celula, e nao do sorteio: o chao nao
   pode cintilar enquanto o jogador esta parado;
2. nada e desenhado com a borda da celula, senao o quadrado volta;
3. o detalhe e pequeno e de baixo contraste: e textura, nao enfeite.

E o desenho vem da propria paleta do chao, entao o detalhe pertence ao
terreno: a pedrinha da aldeia e cinza, a da estrada e terra.
"""
from __future__ import annotations

import pygame

# quantos detalhes por celula. Pouco: o chao e fundo, e o que se ve
# primeiro e o heroi
DETALHES = 3
# o contraste maximo de um detalhe, em canais, sobre o fundo
CONTRASTE = 16

_cache: dict[tuple, pygame.Surface] = {}


def _hash(a: int, b: int, c: int = 0) -> int:
    h = (a * 374761393 + b * 668265263 + c * 2246822519) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return h


def paleta_do_chao(tile: pygame.Surface) -> tuple[int, int, int]:
    """A cor de fundo do chao, pela cor que mais se repete na peca.

    E o que o detalhe tem que seguir: se ele for de outra cor, aparece
    como peca colada, e nao como parte do chao.
    """
    chave = ("paleta", id(tile))
    achada = _cache.get(chave)
    if achada is not None:
        return achada
    contagem: dict[tuple[int, int, int], int] = {}
    for x in range(0, tile.get_width(), 2):
        for y in range(0, tile.get_height(), 2):
            cor = tile.get_at((x, y))[:3]
            contagem[cor] = contagem.get(cor, 0) + 1
    cor = max(contagem, key=contagem.get) if contagem else (0, 0, 0)
    _cache[chave] = cor
    return cor


def _detalhe(cor: tuple[int, int, int], tipo: int, tamanho: int) -> pygame.Surface:
    """Um detalhe pronto: uma marca pequena, de baixo contraste."""
    chave = ("detalhe", cor, tipo, tamanho)
    achada = _cache.get(chave)
    if achada is not None:
        return achada

    img = pygame.Surface((tamanho, tamanho), pygame.SRCALPHA)
    ajuste = -CONTRASTE if tipo % 2 == 0 else CONTRASTE
    tom = tuple(max(0, min(255, c + ajuste)) for c in cor)

    if tipo % 3 == 0:
        # pedrinha: um bloco de poucos pixels
        pygame.draw.rect(img, (*tom, 90), pygame.Rect(0, 0, tamanho, tamanho))
    elif tipo % 3 == 1:
        # rachadura: uma linha curta e fina
        pygame.draw.line(img, (*tom, 80), (0, tamanho - 1),
                         (tamanho - 1, 0), 1)
    else:
        # mancha: um disco bem fraco, e o que mais tira a sensacao de
        # cor chapada sem criar forma nenhuma
        pygame.draw.circle(img, (*tom, 26),
                           (tamanho // 2, tamanho // 2), tamanho // 2)

    _cache[chave] = img
    return img


def desenhar_celula(
    surface: pygame.Surface,
    tile: pygame.Surface,
    lado: int,
    x: int,
    y: int,
    cx: int,
    cy: int,
) -> None:
    """Espalha detalhe no chao da celula (cx, cy) da tela (x, y)."""
    fundo = paleta_do_chao(tile)
    for i in range(DETALHES):
        h = _hash(cx, cy, i)
        tipo = h % 6
        # o detalhe fica longe da borda da celula: se encostar nela, o
        # conjunto das celulas forma o quadrado de novo
        margem = lado // 4
        px = x + margem + (h >> 8) % max(1, lado - margem * 2)
        py = y + margem + (h >> 16) % max(1, lado - margem * 2)
        # o tamanho e pequeno de proposito, e sempre par para nao cair
        # entre dois pixels e ficar com borda dupla
        tamanho = 2 + 2 * ((h >> 24) % 2)
        surface.blit(_detalhe(fundo, tipo, tamanho), (px, py))


def limpar_cache() -> None:
    _cache.clear()
