"""Carregamento de assets com suporte a placeholders.

O jogo roda inteiro sem nenhum arquivo de arte. Para cada sprite
esperado, o sistema procura `assets/sprites/<nome>.png`; se o arquivo
nao existir, devolve um retangulo rotulado no lugar. Assim da para
programar o jogo antes de os sprites estarem prontos, e eles entram
sozinhos quando voce adicionar os PNGs na pasta.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pygame

from . import settings

# nomes de sprites que o jogo espera encontrar
SPRITE_PROTAGONIST = "protagonista"
SPRITE_STRANGER = "estranho"
SPRITE_MYSTERY_WOMAN = "mulher_misteriosa"
SPRITE_KING_MAGE = "rei_mago"

Cache = Dict[str, pygame.Surface]
_cache: Cache = {}


def get_font(size: int) -> pygame.font.Font:
    """Fonte padrao. Usa o arquivo do sistema se existir."""
    path = settings.FONTS_DIR / "default.ttf"
    if path.is_file():
        return pygame.font.Font(str(path), size)
    return pygame.font.Font(None, size)


def sprite_path(name: str) -> Path:
    """Caminho esperado para o arquivo PNG de um sprite."""
    return settings.SPRITES_DIR / f"{name}.png"


def has_sprite(name: str) -> bool:
    """True se o PNG do sprite ja existe na pasta de assets."""
    return sprite_path(name).is_file()


def make_placeholder(
    size: Tuple[int, int],
    label: str = "",
    color: Tuple[int, int, int] | None = None,
) -> pygame.Surface:
    """Retangulo com borda e nome, usado no lugar de um sprite ausente."""
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((color or settings.COLOR_PLACEHOLDER) + (255,))

    pygame.draw.rect(
        surface,
        settings.COLOR_PLACEHOLDER_EDGE,
        surface.get_rect(),
        width=2,
    )

    if label:
        # encolhe a fonte ate o texto caber na largura do placeholder
        size = 18
        while size > 9:
            text = get_font(size).render(label, True, settings.COLOR_TEXT_DIM)
            if text.get_width() <= width - 8:
                break
            size -= 1
        text_rect = text.get_rect(center=surface.get_rect().center)
        surface.blit(text, text_rect)

    return surface


def scale_nearest(surface: pygame.Surface, size: Tuple[int, int]) -> pygame.Surface:
    """Escala por vizinho mais proximo, sem interpolacao.

    Existe para garantir o comportamento de pixel art independente da
    versao do pygame. Testado em 2.6.1: `transform.scale` tambem mantem
    as cores sem misturar, mas `transform.smoothscale` interpola e
    borra. Fazer isso na mao deixa o comportamento explicito e fixo.
    So roda uma vez por sprite (o resultado fica em cache), entao o
    custo nao importa.
    """
    src_w, src_h = surface.get_size()
    dst_w, dst_h = size
    if src_w <= 0 or src_h <= 0:
        return surface

    result = pygame.Surface((dst_w, dst_h), pygame.SRCALPHA)
    for y in range(dst_h):
        src_y = (y * src_h) // dst_h
        for x in range(dst_w):
            src_x = (x * src_w) // dst_w
            result.set_at((x, y), surface.get_at((src_x, src_y)))
    return result


def fit_box(surface: pygame.Surface, box: Tuple[int, int]) -> pygame.Surface:
    """Reduz a imagem para caber em `box` preservando a proporcao.

    Um sprite 32x32 dentro de uma area 78x110 vira 78x78 (quadrado
    mantido), nunca 78x110 esticado. Quando a enlarger cabe em escala
    inteira, usa escala inteira, que e o visual correto para pixel art.
    """
    src_w, src_h = surface.get_size()
    if src_w <= 0 or src_h <= 0:
        return surface

    factor = min(box[0] / src_w, box[1] / src_h)
    if factor >= 1.0:
        whole = int(factor)
        if whole * src_w <= box[0] and whole * src_h <= box[1]:
            factor = float(whole)

    target = (max(1, round(src_w * factor)), max(1, round(src_h * factor)))
    if target == (src_w, src_h):
        return surface
    return scale_nearest(surface, target)


def load_sprite(
    name: str,
    box: Tuple[int, int] | None = None,
    label: str | None = None,
) -> pygame.Surface:
    """Carrega o sprite `name`, ou um placeholder se ele nao existir ainda.

    `box` e a area maxima na tela. A proporcao do sprite e sempre
    preservada. O resultado e cacheado por (nome, box) para nao reler o
    disco a cada frame.
    """
    if box is None:
        box = (settings.TILE_SIZE * 2, settings.TILE_SIZE * 3)

    key = f"{name}@{box[0]}x{box[1]}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    path = sprite_path(name)
    if path.is_file():
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            image = fit_box(image, box)
        except (pygame.error, OSError) as exc:
            print(f"[assets] falha ao carregar {path}: {exc}")
            image = make_placeholder(box, label or name)
    else:
        image = make_placeholder(box, label or name)

    _cache[key] = image
    return image


def clear_cache() -> None:
    """Limpa o cache. Util para recarregar sprites em tempo de execucao."""
    _cache.clear()


def list_expected_sprites() -> Tuple[str, ...]:
    """Lista os sprites que o jogo espera, na ordem de criacao."""
    return (
        SPRITE_PROTAGONIST,
        SPRITE_STRANGER,
        SPRITE_MYSTERY_WOMAN,
        SPRITE_KING_MAGE,
    )


# --- animacoes ----------------------------------------------------
HERO_DIR = settings.SPRITES_DIR / "hero"
HERO_DIRECTIONS: Tuple[str, ...] = ("norte", "sul", "leste", "oeste")
HERO_FPS = 6


def load_animation(
    direction: str,
    box: Tuple[int, int] | None = None,
) -> list[pygame.Surface]:
    """Carrega os quadros de `direction` do heroi, ja escalados.

    Devolve lista vazia se a pasta de animacao nao existir, para o jogo
    continuar funcionando com o placeholder.
    """
    if direction not in HERO_DIRECTIONS:
        raise ValueError(f"direcao invalida: {direction!r}")
    if box is None:
        box = (settings.TILE_SIZE * 2, settings.TILE_SIZE * 3)

    if not HERO_DIR.is_dir():
        return []

    frames = []
    for path in sorted(HERO_DIR.glob(f"hero_{direction}_*.png")):
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            frames.append(fit_box(image, box))
        except (pygame.error, OSError) as exc:
            print(f"[assets] falha ao carregar {path}: {exc}")
    return frames


def has_animation(direction: str = "sul") -> bool:
    """True se existe ao menos um quadro da animacao pedida."""
    if not HERO_DIR.is_dir():
        return False
    return any(HERO_DIR.glob(f"hero_{direction}_*.png"))

