"""Sarcofago de pedra, desenhado por codigo.

Nenhum dos pacotes de sprite tem um tumulo, e um sprite pronto
resolveria so a metade do problema: a tampa precisa deslizar para o
personagem sair, e isso e animacao. Desenhar aqui deixa a tampa ser
uma peca movel de verdade.

O desenho e um sarcofago visto de cima: ombros largos na cabeca e nos
pes, cintura estreita no meio, canto chanfrado e um plinto mais escuro
na base. E o contorno, e nao a cor, que faz a peca ler como tumulo em
vez de caixa.

As pecas:
  - a base, fixa no chao, com o interior escuro
  - a tampa, que desliza para o sul quando o jogador acorda
"""
from __future__ import annotations

import random
from functools import lru_cache

import pygame

# medidas em pixels de 1x; a cena multiplica pela escala dos sprites
COFFIN_W = 40
COFFIN_H = 56
LID_W = COFFIN_W
LID_H = 16
LID_SLIDE = 46  # quanto a tampa anda para o sul ao abrir

# paleta de pedra: cinza frio, com a junta mais escura
STONE = (74, 76, 84)
STONE_LIGHT = (108, 112, 122)
STONE_HI = (132, 136, 146)
STONE_DARK = (46, 48, 55)
STONE_EDGE = (26, 27, 31)
INTERIOR = (14, 13, 12)
PLINTH = (40, 41, 47)

def _sorteio(n: int, seed: int) -> list[float]:
    """Lista de `n` numeros de 0 a 1, sempre igual.

    Fixo de proposito: se o desgaste fosse sorteado a cada quadro, a
    pedra mudava de desenho sessenta vezes por segundo e o caixao
    piscava.
    """
    return [random.Random(seed * 1000 + i).random() for i in range(n)]


def _contorno(
    w: int,
    h: int,
    aperto: int = 0,
    corte: int | None = None,
) -> list[tuple[int, int]]:
    """Contorno do sarcofago: ombros largos, cintura estreita, base reta.

    `aperto` encolhe a peca, para o interior sair da propria silhueta.
    `corte` e o chanfro dos cantos, em pixels.

    O chanfro precisa ser independente do `aperto`. Quando ele crescia
    junto, o interior recuava um terco da largura e o buraco do caixao
    saia com o topo em ogiva, parecendo uma capela.
    """
    if corte is None:
        corte = max(2, w // 8)
    corte = max(1, min(corte, h // 2, w // 2))
    meia = max(2.0, w / 2 - aperto)
    ombro = max(2.0, meia - corte)

    esquerda: list[tuple[int, int]] = []
    direita: list[tuple[int, int]] = []
    for y in range(h):
        if y < corte:
            largura = ombro + (y / corte) * corte
        elif y > h - corte:
            largura = ombro + ((h - y) / corte) * corte
        else:
            largura = meia
        esquerda.append((w / 2 - max(2.0, largura), y))
        direita.append((w / 2 + max(2.0, largura), y))
    return esquerda + list(reversed(direita))


def _preencher_forma(
    img: pygame.Surface, contorno: list[tuple[int, int]], cor: tuple[int, int, int]
) -> None:
    pygame.draw.polygon(img, cor, contorno)


def _borda_luz(
    img: pygame.Surface,
    contorno: list[tuple[int, int]],
    cor: tuple[int, int, int],
    largura: int = 2,
) -> None:
    """Luz na aresta de cima, sombra embaixo: o que da volume."""
    topo = sorted(contorno[: len(contorno) // 2], key=lambda p: p[1])
    pygame.draw.lines(img, cor, False, [(int(x), int(y)) for x, y in topo], largura)


def _manchas(img: pygame.Surface, w: int, h: int, seed: int, quantidade: int) -> None:
    """Pitting e desgaste. Deixa a pedra imperfecta, sem virar ruido."""
    for u, v in zip(_sorteio(quantidade, seed), _sorteio(quantidade, seed + 1)):
        x = int(u * (w - 2)) + 1
        y = int(v * (h - 2)) + 1
        cor = STONE_DARK if (x + y) % 3 else STONE_LIGHT
        pygame.draw.rect(img, cor, pygame.Rect(x, y, 1, 1))


def _desenhar_cruz(img: pygame.Surface, center: tuple[int, int], tamanho: int) -> None:
    """Cruz entalhada, o detalhe que faz ler como tumulo."""
    x, y = center
    bra = max(1, tamanho // 10)
    pygame.draw.line(img, STONE_DARK, (x - tamanho, y), (x + tamanho, y), bra)
    pygame.draw.line(img, STONE_DARK, (x, y - tamanho), (x, y + tamanho), bra)
    pygame.draw.line(
        img, STONE_LIGHT, (x - tamanho, y - bra), (x + tamanho, y - bra), 1
    )


def _desenhar_cabeca(img: pygame.Surface, w: int, h: int, x: int, y: int) -> None:
    """Cranio entalhado na tampa.

    O raio e sobre a MENOR dimensao da tampa: com a medida pelo maior
    lado o cranio saia do tamanho de um rebite e a tampa perdia o
    assunto.
    """
    r = max(2, min(w, h) // 4)
    pygame.draw.circle(img, STONE_DARK, (x, y), r)
    pygame.draw.circle(img, STONE_EDGE, (x, y), r, 1)
    # orbitas fundas
    for sinal in (-1, 1):
        pygame.draw.circle(
            img, INTERIOR, (x + sinal * max(1, r // 2), y - r // 5),
            max(1, r // 3),
        )
    # dentes
    dentes = max(2, r // 2)
    pygame.draw.rect(img, INTERIOR, (x - dentes, y + r // 3, dentes * 2, max(1, r // 4)))
    pygame.draw.line(
        img, STONE_HI, (x - r + 1, y - r // 2), (x + r - 1, y - r // 2), 1
    )


@lru_cache(maxsize=16)
def _stone_body(width: int, height: int) -> pygame.Surface:
    """Bloco de pedra: contorno chanfrado, plinto e juntas.

    Cacheado por tamanho. O sarcofago nao se mexe sozinho: redesenhar
    o poligono, as juntas e as manchas sessenta vezes por quadro custou
    100 fps da masmorra (318 -> 216) para produzir a mesma imagem.
    """
    img = pygame.Surface((width, height), pygame.SRCALPHA)
    img.fill((0, 0, 0, 0))

    plinto_h = max(2, height // 7)
    contorno = _contorno(width, height)
    _preencher_forma(img, contorno, STONE)
    _borda_luz(img, contorno, STONE_LIGHT, 2)
    pygame.draw.lines(img, STONE_EDGE, True, [(int(x), int(y)) for x, y in contorno], 1)

    # plinto: a base e um degrau mais largo e mais escuro
    pygame.draw.rect(
        img,
        PLINTH,
        pygame.Rect(0, height - plinto_h, width, plinto_h),
    )
    pygame.draw.line(
        img, STONE_EDGE, (0, height - plinto_h), (width, height - plinto_h), 1
    )

    # faixas de bloco na face, para nao parecer um retangulo liso
    bloco = max(3, (height - plinto_h) // 4)
    for y in range(0, height - plinto_h, bloco):
        pygame.draw.line(img, STONE_DARK, (1, y), (width - 2, y), 1)
        x = (y // bloco) % 2 * (width // 3)
        pygame.draw.line(img, STONE_DARK, (x, y), (x, y + bloco), 1)

    _manchas(img, width, height - plinto_h, seed=3, quantidade=width // 3)
    return img


@lru_cache(maxsize=16)
def _base_completa(w: int, h: int) -> pygame.Surface:
    """Sarcofago com o buraco cavado. Montado uma vez por tamanho."""
    # copia: o buraco e a sombra sao desenhados por cima, e mexer na
    # superficie do cache estragaria a proxima chamada
    base = _stone_body(w, h).copy()

    # interior: a mesma silhueta, encolhida e deslocada para baixo,
    # deixando a parede grossa na cabeca. Retangulo dentro de contorno
    # chanfrado deixava uma quina de pedra aparecendo no vazio.
    vao = _contorno(
        w,
        h - max(3, h // 14),
        aperto=max(2, w // 9),
        corte=max(2, w // 10),
    )
    vao = [(x, y + max(2, h // 18)) for x, y in vao]
    _preencher_forma(base, vao, INTERIOR)
    pygame.draw.lines(
        base, STONE_EDGE, True, [(int(x), int(y)) for x, y in vao], 1
    )

    # sombra interna na parede de cima, dando profundidade ao buraco
    sombra = pygame.Surface((w, max(2, h // 7)), pygame.SRCALPHA)
    sombra.fill((0, 0, 0, 150))
    base.blit(sombra, (0, 0))

    # limo e po no fundo, para a pedra nao parecer lavada
    _manchas(base, w, h // 3, seed=11, quantidade=w // 4)

    return base


@lru_cache(maxsize=16)
def _sombra(largura: int, altura: int, alpha: int) -> pygame.Surface:
    """Mancha de sombra reutilizavel, so com o tamanho variando."""
    sombra = pygame.Surface((max(1, largura), max(1, altura)), pygame.SRCALPHA)
    sombra.fill((0, 0, 0, alpha))
    return sombra


def draw_coffin(
    surface: pygame.Surface,
    center: tuple[int, int],
    open_progress: float = 0.0,
    scale: int = 1,
) -> pygame.Rect:
    """Desenha o caixao e devolve o retangulo ocupado no chao."""
    s = max(1, int(scale))
    w, h = COFFIN_W * s, COFFIN_H * s
    cx, cy = center

    base = _base_completa(w, h)
    rect = base.get_rect(center=(cx, cy))

    # sombra propria no chao
    sombra_chao = _sombra(w, max(3, h // 10), 110)
    surface.blit(
        sombra_chao,
        sombra_chao.get_rect(centerx=cx, bottom=rect.bottom - h // 12),
    )
    surface.blit(base, rect)
    return rect


@lru_cache(maxsize=16)
def _tampa(w: int, h: int) -> pygame.Surface:
    """Tampa pronta: pedra, cranio, cruz e bisel. Cacheada como um todo."""
    tampa = _stone_body(w, h).copy()
    _desenhar_cabeca(tampa, w, h, w // 2, h // 3)
    _desenhar_cruz(tampa, (w // 2, int(h * 0.74)), min(w, h) // 5)

    # bisel: linha clara no alto, escura embaixo
    pygame.draw.line(tampa, STONE_HI, (w // 6, 1), (w - w // 6, 1), 1)
    pygame.draw.line(tampa, STONE_EDGE, (1, h - 2), (w - 2, h - 2), max(1, h // 32))

    contorno = _contorno(w, h)
    pygame.draw.lines(
        tampa, STONE_EDGE, True, [(int(x), int(y)) for x, y in contorno], 1
    )
    return tampa


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

    tampa = _tampa(w, h)

    rect = tampa.get_rect(center=(cx, cy + deslocamento))
    # sombra da tampa no chao, para ela nao parecer colada
    if deslocamento:
        sombra = _sombra(w, max(3, h // 3), 90)
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