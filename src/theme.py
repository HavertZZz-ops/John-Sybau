"""Tema visual no estilo Dark Souls.

Fundo quase preto, texto em cinza-quente, selecao em dourado palido e
tipografia com espacamento largo. A ideia e o contrario do painel
colorido: nada de caixas, nada de bordas, so texto sobre o escuro, com
o item selecionado respirando em dourado.
"""
from __future__ import annotations

import pygame

# --- cores ---
BACKGROUND = (10, 9, 8)
BACKGROUND_SOFT = (16, 14, 12)
TEXT_DIM = (118, 110, 100)
TEXT = (176, 168, 156)
TEXT_BRIGHT = (208, 200, 186)
GOLD = (198, 168, 102)
GOLD_BRIGHT = (228, 202, 138)
HAIRLINE = (44, 40, 36)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Interpola duas cores. `t` de 0 a 1."""
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def pulse(t: float, speed: float = 1.6) -> float:
    """Valor entre 0 e 1 que respira, para o item selecionado."""
    import math

    return 0.5 + 0.5 * math.sin(t * speed * math.tau)


class Fonts:
    """Fontes do tema, carregadas uma vez.

    O jogo nao embute fonte; usa a padrao do pygame com espacamento
    manual entre letras, que e o que da o ar de titulo antigo.
    """

    _cache: dict[int, pygame.font.Font] = {}

    @classmethod
    def reset(cls) -> None:
        """Esquece as fontes em cache.

        `pygame.quit()` destroi o subsistema de fonte, mas os objetos
        Font do cache continuam apontando para memoria liberada. Usar
        um deles depois causa acesso invalido. Por isso o cache e
        limpo sempre que o pygame e reiniciado.
        """
        cls._cache.clear()

    @classmethod
    def get(cls, size: int) -> pygame.font.Font:
        """Fonte do tamanho pedido, com o tamanho blindado.

        `pygame.font.Font` causa acesso invalido de memoria com tamanho
        zero ou negativo, e os tamanhos aqui sao calculados em
        proporcao a janela: em uma janela muito baixa, `int(h * 0.02)`
        chega a zero. O piso de 8 evita o crash sem mudar o visual.
        """
        if not pygame.font.get_init():
            pygame.font.init()
            cls.reset()  # cache pode ter Font de antes do quit
        size = max(8, int(size))
        font = cls._cache.get(size)
        if font is None:
            try:
                font = pygame.font.Font(None, size)
            except Exception:
                # pygame pode recusar tamanhos absurdos; o 16 sempre
                # funciona e ainda da para ler
                font = pygame.font.Font(None, 16)
                size = 16
            cls._cache[size] = font
        return font


def text_tracked(
    surface: pygame.Surface,
    text: str,
    size: int,
    center: tuple[int, int],
    color: tuple[int, int, int],
    tracking: int = 2,
) -> pygame.Rect:
    """Desenha texto com espacamento entre letras, centrado.

    O pygame nao tem espacamento entre letras; desenhar caractere por
    caractere e o jeito de conseguir aquele ar de placa antiga.
    """
    font = Fonts.get(size)
    glyphs = [font.render(ch, True, color) for ch in text]
    if not glyphs:
        return pygame.Rect(0, 0, 0, 0)
    width = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
    height = max(g.get_height() for g in glyphs)

    x = center[0] - width // 2
    y = center[1] - height // 2
    box = pygame.Rect(x, y, width, height)
    for g in glyphs:
        surface.blit(g, (x, y))
        x += g.get_width() + tracking
    return box


def text_tracked_at(
    surface: pygame.Surface,
    text: str,
    size: int,
    pos: tuple[int, int],
    color: tuple[int, int, int],
    tracking: int = 2,
) -> pygame.Rect:
    """Igual a `text_tracked`, mas com o canto superior esquerdo em pos."""
    font = Fonts.get(size)
    glyphs = [font.render(ch, True, color) for ch in text]
    if not glyphs:
        return pygame.Rect(0, 0, 0, 0)
    width = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
    height = max(g.get_height() for g in glyphs)
    box = pygame.Rect(pos[0], pos[1] - height // 2, width, height)
    x = pos[0]
    y = pos[1] - height // 2
    for g in glyphs:
        surface.blit(g, (x, y))
        x += g.get_width() + tracking
    return box


def text_tracked_right(
    surface: pygame.Surface,
    text: str,
    size: int,
    right_x: int,
    center_y: int,
    color: tuple[int, int, int],
    tracking: int = 2,
) -> pygame.Rect:
    """Texto alinhado pela direita, com a linha central em center_y.

    `text_tracked_at` alinha pela esquerda, entao alinhar pela direita
    exige medir a largura antes de desenhar.
    """
    font = Fonts.get(size)
    glyphs = [font.render(ch, True, color) for ch in text]
    if not glyphs:
        return pygame.Rect(0, 0, 0, 0)
    width = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
    height = max(g.get_height() for g in glyphs)

    x = right_x - width
    y = center_y - height // 2
    box = pygame.Rect(x, y, width, height)
    for g in glyphs:
        surface.blit(g, (x, y))
        x += g.get_width() + tracking
    return box


def hairline(
    surface: pygame.Surface,
    x1: int,
    y: int,
    x2: int,
    color: tuple[int, int, int] = HAIRLINE,
) -> None:
    """Fina linha horizontal, para separar blocos sem usar caixa."""
    pygame.draw.line(surface, color, (x1, y), (x2, y), 1)


def fade_surface(
    surface: pygame.Surface,
    alpha: int,
    color: tuple[int, int, int] = BACKGROUND,
) -> None:
    """Cobre a tela com uma cor translucida, para transicoes."""
    if alpha <= 0:
        return
    veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    veil.fill(color + (min(255, alpha),))
    surface.blit(veil, (0, 0))
