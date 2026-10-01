"""Luz: a masmorra tem que ter escuro e uma tocha, senao e um retangulo.

O mapa era desenhado com a luz cheia da tela: todo tile com a mesma
claridade, todas as paredes com o mesmo tom, e o resultado e uma laje
marrom uniforme. Nao ha lugar nenhum para o olho se apoiar e nao ha
motivo para a fogueira existir — ela e um desenho, nao uma luz.

Aqui a cena e desenhada normalmente e depois escurecida por uma
 mascara, com um circle de luz desenhado em cada ponto que emite:
o heroi, a fogueira, as tochas da sala. O que fica fora e escuro.

O gradiente radial e caro de fazer a cada quadro, entao e desenhado
UMA VEZ num buffer do tamanho da luz e depois copiado. Sem isso a
mascara custaria mais que o mapa inteiro.
"""
from __future__ import annotations

import pygame

# o quanto o ambiente e escurecido. Nem preto — um preto puro faz a
# borda da tela virar um buraco; 0.62 ainda da para ler a pedra longe.
AMBIENTE = (74, 70, 84)
# O heroi NAO carrega luz. Ele caiu no mundo medieval sem nada, entao
# nao tem tocha na mao, lampiao ou magical: o round dele no escuro e o
# que ele tem. Por isso nao existe cor de luz do heroi aqui.
#
# A luz da masmorra vem das tochas da parede e da fogueira, e so isso.
# Fora da masmorra e de dia e nao ha mascara nenhuma.
# a tocha da parede: amarelada, e menor que a fogueira
LUZ_TOCHA = (255, 196, 120)
# a fogueira e maior e mais quente
LUZ_FOGUEIRA = (255, 186, 108)

_cache: dict[tuple[int, int], pygame.Surface] = {}


def _gradiente(raio: int) -> pygame.Surface:
    """O circulo de luz, em aneis, do centro para fora."""
    chave = (raio, 0)
    if chave in _cache:
        return _cache[chave]
    g = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
    passos = 26
    for i in range(passos, 0, -1):
        t = i / passos
        r = int(raio * t)
        alfa = int(215 * (1.0 - t) ** 1.7)
        pygame.draw.circle(g, (255, 255, 255, alfa), (raio, raio), r)
    _cache[chave] = g
    return g


class Luz:
    """A mascara de luz da cena."""

    def __init__(self) -> None:
        self.ponto_de_luz: list[tuple[int, int, int, tuple[int, int, int]]] = []

    def add(self, x: int, y: int, raio: int,
            cor: tuple[int, int, int] = LUZ_TOCHA) -> None:
        self.ponto_de_luz.append((int(x), int(y), int(raio), cor))

    def aplicar(self, surface: pygame.Surface) -> None:
        """Escurece a cena e abre a luz em cada ponto."""
        w, h = surface.get_size()
        mascara = pygame.Surface((w, h), pygame.SRCALPHA)
        mascara.fill(AMBIENTE + (255,))

        for x, y, raio, cor in self.ponto_de_luz:
            g = _gradiente(max(8, raio))
            tingido = pygame.Surface(g.get_size(), pygame.SRCALPHA)
            tingido.fill(cor + (0,))
            tingido.blit(g, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            mascara.blit(tingido, (x - raio, y - raio),
                         special_flags=pygame.BLEND_RGBA_ADD)

        # multiplicar escurece o que ja esta desenhado e mantem a cor
        # das coisas iluminadas
        surface.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)


def vinhete(w: int, h: int) -> pygame.Surface:
    """A borda escura, puxando o olho para o centro."""
    chave = (w, h)
    if chave in _cache:
        return _cache[chave]
    toldo = max(30, min(w, h) // 5)
    v = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(toldo):
        alfa = int(150 * (1.0 - i / toldo) ** 2.2)
        pygame.draw.rect(v, (0, 0, 0, alfa),
                         pygame.Rect(i, i, w - 2 * i, h - 2 * i), 1)
    _cache[chave] = v
    return v