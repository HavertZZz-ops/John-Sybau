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

# multiplicador global aplicado aos sprites, controlado pelas opcoes
_sprite_scale = 1


def get_sprite_scale() -> int:
    return _sprite_scale


def set_sprite_scale(value: int) -> None:
    """Muda a escala global dos sprites e limpa o cache.

    O cache precisa ser limpo porque as superficies ja escaladas no
    tamanho antigo ficariam erradas na tela.
    """
    global _sprite_scale
    value = max(1, int(value))
    if value == _sprite_scale:
        return
    _sprite_scale = value
    clear_cache()





def get_font(size: int) -> pygame.font.Font:
    """Fonte padrao. Usa o arquivo do projeto se existir.

    `pygame.font.init()` e chamado aqui porque da para carregar fonte
    depois de pygame.init() ter rodado; quem chama pode ter inicializado
    so o display. Sem isso, usar fonte estoura em "font not
    initialized".
    """
    if not pygame.font.get_init():
        pygame.font.init()

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


def _load_image(path) -> pygame.Surface:
    """Carrega um PNG, convertendo o formato quando ha display.

    `convert_alpha` acelera o desenho, mas exige display inicializado.
    Sem display (carregando asset antes de abrir a janela) ele falha,
    entao nesse caso devolve a imagem sem conversao.
    """
    image = pygame.image.load(str(path))
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return image.convert_alpha()
    return image


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


def fit_box(
    surface: pygame.Surface,
    box: Tuple[int, int],
    max_scale: int | None = None,
) -> pygame.Surface:
    """Ajusta a imagem para caber em `box`, preservando a proporcao.

    Dois tetos, e vale o menor dos dois:
      - `box`      : a area disponivel na tela
      - `max_scale` : o enlarge pedido nas opcoes

    Enlarge e sempre em escala inteira, porque e assim que pixel art
    fica nitido. Reduzir (sprite maior que a area) usa fracao, porque
    nesse caso nao ha como preservar a grade.
    """
    src_w, src_h = surface.get_size()
    if src_w <= 0 or src_h <= 0:
        return surface

    limit_w, limit_h = box
    if max_scale is not None and max_scale >= 1:
        limit_w = min(limit_w, src_w * max_scale)
        limit_h = min(limit_h, src_h * max_scale)

    factor = min(limit_w / src_w, limit_h / src_h)
    if factor >= 1.0:
        factor = float(int(factor))  # enlarge so em escala inteira

    target = (max(1, round(src_w * factor)), max(1, round(src_h * factor)))
    if target == (src_w, src_h):
        return surface
    return scale_nearest(surface, target)


def load_sprite(
    name: str,
    box: Tuple[int, int] | None = None,
    label: str | None = None,
    max_scale: int | None = None,
) -> pygame.Surface:
    """Carrega o sprite `name`, ou um placeholder se ele nao existir ainda.

    `box` e a area maxima na tela. A proporcao do sprite e sempre
    preservada. O resultado e cacheado por (nome, box) para nao reler o
    disco a cada frame.
    """
    if box is None:
        box = (settings.TILE_SIZE * 2, settings.TILE_SIZE * 3)
    if max_scale is None:
        max_scale = _sprite_scale

    key = f"{name}@{box[0]}x{box[1]}@{max_scale}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    path = sprite_path(name)
    if path.is_file():
        try:
            image = _load_image(path)
            image = fit_box(image, box, max_scale=max_scale)
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
# proporcao do quadro do heroi (largura / altura), usada para caber na tela
HERO_ASPECT = 32.0 / 38.0


def load_animation(
    direction: str,
    box: Tuple[int, int] | None = None,
    max_scale: int | None = None,
) -> list[pygame.Surface]:
    """Carrega os quadros de `direction` do heroi, ja escalados.

    A escala global configurada nas opcoes e aplicada aqui. Devolve
    lista vazia se a pasta de animacao nao existir, para o jogo
    continuar funcionando com o placeholder.
    """
    if direction not in HERO_DIRECTIONS:
        raise ValueError(f"direcao invalida: {direction!r}")
    if box is None:
        box = (settings.TILE_SIZE * 2, settings.TILE_SIZE * 3)
    if max_scale is None:
        max_scale = _sprite_scale

    if not HERO_DIR.is_dir():
        return []

    frames = []
    for path in sorted(HERO_DIR.glob(f"hero_{direction}_*.png")):
        try:
            image = _load_image(path)
            frames.append(fit_box(image, box, max_scale=max_scale))
        except (pygame.error, OSError) as exc:
            print(f"[assets] falha ao carregar {path}: {exc}")
    return frames


def has_animation(direction: str = "sul") -> bool:
    """True se existe ao menos um quadro da animacao pedida."""
    if not HERO_DIR.is_dir():
        return False
    return any(HERO_DIR.glob(f"hero_{direction}_*.png"))

