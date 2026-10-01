"""A massa solida do mapa, que antes ficava preta.

O mapa e gerado cheio de `PAREDE`: pedra, mato, o interior de uma
colina. A grade de tiles so desenha o CHAO andavel, entao cada celula
de parede ficava com a cor do fundo, `(10, 9, 8)`, que e quase preto.

A tela mostrava a aldeia como um retangulo de pedra cercado de um
buraco negro. Nao e um buraco: e o mapa inteiro, e o jogador so
enxergava a parte caminhavel dele. Pior, o preto era indistinguivel de
arte que falhou de carregar, entao o defeito se lia como bug e nao
como lugar.

A parede vira uma cor solida, alguns canais acima do fundo. E so.

Duas temptacoes, e as duas foram tentadas antes de a pedra ficar como
esta:

  - dar textura. Um degrade dentro do tile se repete a cada 48 pixels
    e a parede ganha listras horizontais; grao tirado de hash de duas
    coordenadas sai como hachura diagonal; e uma fissura por variante
    virou marca d'agua, a mesma diagonal repetida em toda pedra.
  - dar variacao de tom entre as pedras, para a massa nao ser uma cor
    so. Com tres tons separados por tres canais, as pedras vizinhas
    viraram faixas de varias celulas de uma tonalidade so, e num mapa
    escuro, onde os tons vivem entre 24 e 33, seis canais de diferenca
    sao 20% de mudanca relativa: bem visivel. A parede ficou listrada.

Nenhuma das duas. A pedra e chapada e e a luz da cena, que ja escurece
o que esta longe, que faz o resto do trabalho.
"""

from __future__ import annotations

import pygame

# o tom da pedra. Um passo acima do fundo: o suficiente para o olho
# ler como solido, e nao tanto que a parede dispute atencao com o chao
BASE = (28, 25, 21)

_cache: dict[int, pygame.Surface] = {}


def tile(lado: int) -> pygame.Surface:
    """Um quadrado de pedra de `lado` pixels, cacheado por tamanho."""
    achada = _cache.get(lado)
    if achada is not None:
        return achada

    pedra = pygame.Surface((lado, lado))
    pedra.fill(BASE)
    _cache[lado] = pedra
    return pedra


def celula(lado: int, x: int = 0, y: int = 0) -> pygame.Surface:
    """A pedra da celula (x, y).

    `x` e `y` nao mudam nada: ficam na assinatura porque a chamada e
    feita dentro do laco da grade, e um nome de celula ali ja diz que
    a parede e a mesma pedra em qualquer lugar do mapa. Se um dia a
    pedra voltar a ter desenho, e este o lugar onde a celula entra.
    """
    return tile(lado)


def limpar_cache() -> None:
    """Solta as pedras. Util quando a escala global muda."""
    _cache.clear()