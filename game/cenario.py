"""O mundo de tiles: o cenario desenhado embaixo do jogador.

Um tile de 32px e um sprite. O mapa sabe o que e parede e o que e chao
(o modulo `player`), e este sabe COMO DESENHAR. A separacao e o que
permite trocar o desenho sem mexer na colisao: e o defeito classico de
mudar a arte e o jogador de repente atravessar parede, ou travar em
cima do chao.

Duas coisas que este modulo resolve e queUsually dao problema:

**O tile precisa ser desenhado de um jeito so.** A parede nao pode ser
desenhada como chao por um quadro e como parede no seguinte: com
`surf` diferente, o jogador ve a parede piscando. Por isso o desenho de
cada tipo de tile vem de uma superficie Montada uma vez e blitada
depois, e nunca de um desenho feito na hora.

**A borda da tela.** O mapa e maior que a tela, e o desenho comeca pela
primeira celula VISIVEL, nao pela celula (0, 0). Desenhar o mapa inteiro
a cada quadro e desperdicio: em um mapa de 50x30 sao 1500 tiles, e
aparecem uns 700.
"""
from __future__ import annotations

import pygame

import settings

# As cores do cenario, antes de haver arte.
#
# Sao valores de PROPOSITO, nao placeholders esquecidos. Um cenario de
# teste com cor chapada permite medir contraste e ver a colisao; um
# cenario de teste com arte mostra a arte e esconde o resto.
CHAO = (78, 92, 68)
PAREDE = (46, 44, 58)
BORDA = (26, 24, 34)
SAIDA = (196, 156, 62)

_cache: dict[tuple[int, str], pygame.Surface] = {}


def tile_de(tipo: str, lado: int = settings.TAMANHO_DO_TILE) -> pygame.Surface:
    """A superficie de um tile, montada uma vez e reaproveitada.

    O cache existe porque montar um retangulo de 32x32 por tile por quadro
    e 700 alocacoes por quadro — e alocar e caro. Montado uma vez, o
    custo vira um blit.
    """
    chave = (lado, tipo)
    achada = _cache.get(chave)
    if achada is not None:
        return achada

    img = pygame.Surface((lado, lado))

    if tipo == "parede":
        img.fill(PAREDE)
        # Uma borda mais clara em cima: e o que da a sensacao de que a
        # parede tem altura. Sem ela, a parede e uma mancha chapada e o
        # jogador nao distingue parede de buraco.
        pygame.draw.rect(img, (58, 55, 70), pygame.Rect(0, 0, lado, 3))
        pygame.draw.rect(img, (34, 32, 42), pygame.Rect(0, lado - 3, lado, 3))
    elif tipo == "chao":
        img.fill(CHAO)
    elif tipo == "saida":
        img.fill(CHAO)
        # A saida e o unico tile que precisa ser NOTADO a distancia, e
        # por isso que ela tem cor propria e um desenho: um retangulo
        # dourado no chao e o unico que o jogador identifica sem chegar
        # perto.
        pygame.draw.rect(
            img, SAIDA,
            pygame.Rect(lado // 4, lado // 4, lado // 2, lado // 2),
        )
        pygame.draw.rect(
            img, (240, 210, 140),
            pygame.Rect(lado // 4, lado // 4, lado // 2, lado // 2), 2,
        )
    else:
        img.fill(BORDA)

    _cache[chave] = img
    return img


def desenhar(
    tela: pygame.Surface,
    mapa: "player.Mapa",  # noqa: F821 — o tipo vem do modulo que chama
    camera: pygame.Vector2,
) -> None:
    """Desenha o mapa visivel na tela.

    `camera` e o canto superior esquerdo do mundo, em pixels.
    """
    lado = settings.TAMANHO_DO_TILE
    largura_tela, altura_tela = tela.get_size()

    # A primeira celula visivel. `//` arredonda para baixo, entao
    # subtrair 1 de cada lado garante a celula parcialmente visivel na
    # borda — sem isso, aparece um vao de um tile quando a camera esta
    # entre duas celulas.
    primeira_coluna = int(camera.x // lado) - 1
    primeira_linha = int(camera.y // lado) - 1
    colunas = largura_tela // lado + 3
    linhas = altura_tela // lado + 3

    for linha in range(primeira_linha, primeira_linha + linhas):
        for coluna in range(primeira_coluna, primeira_coluna + colunas):
            tipo = mapa.em(coluna, linha)

            if tipo == mapa.PAREDE:
                sprite = tile_de("parede", lado)
            elif tipo == mapa.SAIDA:
                sprite = tile_de("saida", lado)
            else:
                sprite = tile_de("chao", lado)

            tela.blit(
                sprite,
                (coluna * lado - int(camera.x),
                 linha * lado - int(camera.y)),
            )


def limpar_cache() -> None:
    """Solta os tiles. Para quando o tamanho do tile mudar."""
    _cache.clear()