"""Caixao de pedra, desenhado por codigo.

Nenhum dos pacotes de sprite tem um sarcofago, e um sprite pronto
resolveria so a metade do problema: a tampa precisa deslizar para o
personagem sair, e isso e animacao. Desenhar aqui deixa a tampa ser
uma peca movel de verdade.

O caixao tem duas pecas:
  - a base, fixa no chao, com o interior escuro
  - a tampa, que desliza para o lado quando o jogador acorda
"""
from __future__ import annotations

import pygame

# medidas em pixels de 1x; a cena multiplica pela escala dos sprites
COFFIN_W = 40
COFFIN_H = 56
LID_W = COFFIN_W
LID_H = 16
LID_SLIDE = 46  # quanto a tampa anda para o sul ao abrir

# paleta de pedra: cinza frio, com a junta mais escura
STONE = (74, 76, 84)
STONE_LIGHT = (96, 99, 108)
STONE_DARK = (46, 48, 55)
STONE_EDGE = (30, 31, 36)
INTERIOR = (16, 15, 14)


def _stone_body(width: int, height: int) -> pygame.Surface:
    """Corpo do caixao, com a pedra em faixas e junta marcada."""
    img = pygame.Surface((width, height), pygame.SRCALPHA)

    pygame.draw.rect(img, STONE, img.get_rect())
    # faixas horizontais de blocos, para nao parecer um retangulo liso
    altura_bloco = max(4, height // 7)
    for y in range(0, height, altura_bloco):
        pygame.draw.line(img, STONE_DARK, (0, y), (width, y), 1)
    # blocos alternados, dando a junta vertical
    for y in range(0, height, altura_bloco * 2):
        x = (y // altura_bloco) % 2 * (width // 3)
        pygame.draw.line(img, STONE_DARK, (x, y), (x, y + altura_bloco), 1)

    # luz de cima e sombra de baixo, dando volume
    pygame.draw.line(img, STONE_LIGHT, (0, 0), (width, 0), 2)
    pygame.draw.line(img, STONE_LIGHT, (0, 0), (0, height), 2)
    pygame.draw.line(img, STONE_EDGE, (0, height - 1), (width, height - 1), 2)
    pygame.draw.line(img, STONE_EDGE, (width - 1, 0), (width - 1, height), 2)
    return img


def _desenhar_cruz(img: pygame.Surface, center: tuple[int, int], tamanho: int) -> None:
    """Cruz entalhada, o detalhe que faz ler como tumba."""
    x, y = center
    bra = max(1, tamanho // 12)
    pygame.draw.line(img, STONE_DARK, (x - tamanho, y), (x + tamanho, y), bra)
    pygame.draw.line(img, STONE_DARK, (x, y - tamanho), (x, y + tamanho), bra)
    pygame.draw.line(
        img, STONE_LIGHT,
        (x - tamanho, y - bra), (x + tamanho, y - bra), 1,
    )


def draw_coffin(
    surface: pygame.Surface,
    center: tuple[int, int],
    open_progress: float = 0.0,
    scale: int = 1,
) -> pygame.Rect:
    """Desenha o caixao e devolve o retangulo ocupado no chao.

    `open_progress` vai de 0 (tampa fechada) a 1 (tampa toda para o
    lado). A tampa e desenhada depois do heroi quando ela esta fechando
    o suficiente para esconder, e antes quando esta aberta, entao quem
    chama decide a ordem pelo valor.
    """
    s = max(1, int(scale))
    w, h = COFFIN_W * s, COFFIN_H * s
    cx, cy = center

    # --- base com o interior escuro, para o personagem "dentro" dela
    base = _stone_body(w, h)
    # moldura: a borda de pedra fica mais larga embaixo e nas laterais,
    # e o miolo e o vazio onde o heroi estava deitado
    lateral = max(3, w // 6)
    cabeca = max(4, h // 8)
    vao = pygame.Rect(lateral, cabeca, w - 2 * lateral, h - cabeca - lateral // 2)
    pygame.draw.rect(base, INTERIOR, vao)
    pygame.draw.rect(base, STONE_EDGE, vao, 1)
    # sombra interna no alto, dando profundidade ao buraco
    sombra = pygame.Surface((vao.width, max(2, vao.height // 4)), pygame.SRCALPHA)
    sombra.fill((0, 0, 0, 120))
    base.blit(sombra, (vao.x, vao.y))

    rect = base.get_rect(center=(cx, cy))
    surface.blit(base, rect)
    return rect


def draw_lid(
    surface: pygame.Surface,
    center: tuple[int, int],
    open_progress: float = 0.0,
    scale: int = 1,
) -> pygame.Rect:
    """Desenha a tampa, deslocada conforme `open_progress`."""
    s = max(1, int(scale))
    w, h = LID_W * s, LID_H * s
    deslocamento = int(LID_SLIDE * s * max(0.0, min(1.0, open_progress)))
    cx, cy = center

    tampa = _stone_body(w, h)
    _desenhar_cruz(tampa, (w // 2, h // 2), min(w, h) // 3)
    pygame.draw.rect(tampa, STONE_EDGE, tampa.get_rect(), 1)

    rect = tampa.get_rect(center=(cx, cy + deslocamento))
    # sombra da tampa no chao, para ela nao parecer colada
    if deslocamento:
        sombra = pygame.Surface((w, max(3, h // 3)), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 90))
        surface.blit(
            sombra,
            sombra.get_rect(centerx=cx, top=rect.top + h - sombra.get_height() // 3),
        )
    surface.blit(tampa, rect)
    return rect


def coffin_size(scale: int = 1) -> tuple[int, int]:
    """Tamanho do caixao escalado, para a cena reservar o espaco."""
    s = max(1, int(scale))
    return COFFIN_W * s, COFFIN_H * s


def scale_for_sprites(sprite_scale: int) -> int:
    """Traduz a escala de sprites do jogo para a do caixao.

    A escala das opcoes e 1x a 4x sobre um quadro de 32px. O caixao foi
    desenhado em 1x com 40px de largura, entao a mesma escala do jogo
    deixa tudo com o mesmo tamanho relativo.
    """
    return max(1, int(sprite_scale))