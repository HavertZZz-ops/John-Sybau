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


def load_sprite(
    name: str,
    size: Tuple[int, int] | None = None,
    label: str | None = None,
) -> pygame.Surface:
    """Carrega o sprite `name`, ou um placeholder se ele nao existir ainda.

    O resultado e cacheado por (nome, tamanho) para nao reler o disco
    a cada frame.
    """
    if size is None:
        size = (settings.TILE_SIZE * 2, settings.TILE_SIZE * 3)

    key = f"{name}@{size[0]}x{size[1]}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    path = sprite_path(name)
    if path.is_file():
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            image = pygame.transform.scale(image, size)
        except (pygame.error, OSError) as exc:
            print(f"[assets] falha ao carregar {path}: {exc}")
            image = make_placeholder(size, label or name)
    else:
        image = make_placeholder(size, label or name)

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
