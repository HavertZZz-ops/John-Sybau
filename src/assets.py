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
    scale: int = 1,
) -> pygame.Surface:
    """Escala a imagem em `scale` vezes, limitada por `box`.

    Regra unica do jogo, para nao haver duvida de onde a escala entra:
      - `box`   e a area DISPONIVEL na tela (o teto)
      - `scale` e o enlarge das opcoes (1x a 4x)

    O enlarge e em escala inteira, para o pixel art ficar nitido. Se o
    resultado estourar a area, cai para a maior escala inteira que couber.
    """
    src_w, src_h = surface.get_size()
    if src_w <= 0 or src_h <= 0:
        return surface

    scale = max(1, int(scale))
    # a maior escala inteira que cabe na area
    wanted = scale
    while wanted > 1 and (src_w * wanted > box[0] or src_h * wanted > box[1]):
        wanted -= 1

    if wanted > 1:
        return scale_nearest(surface, (src_w * wanted, src_h * wanted))

    # wanted == 1: cabe na escala 1, ou sprite maior que a area
    if src_w > box[0] or src_h > box[1]:
        factor = min(box[0] / src_w, box[1] / src_h)
        return scale_nearest(
            surface,
            (max(1, int(src_w * factor)), max(1, int(src_h * factor))),
        )
    return surface


def load_sprite(
    name: str,
    box: Tuple[int, int] | None = None,
    label: str | None = None,
    scale: int | None = None,
) -> pygame.Surface:
    """Carrega o sprite `name`, ou um placeholder se ele nao existir.

    `box` e a area em tamanho 1x; `scale` (padrao: a das opcoes) e o
    enlarge. O resultado e cacheado por (nome, box, escala).
    """
    if box is None:
        box = (settings.TILE_SIZE * 2, settings.TILE_SIZE * 3)
    if scale is None:
        scale = _sprite_scale

    key = f"{name}@{box[0]}x{box[1]}@{scale}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    path = sprite_path(name)
    if path.is_file():
        try:
            image = _load_image(path)
            image = fit_box(image, box, scale=scale)
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
HERO_STATES: Tuple[str, ...] = (
    "idle", "walk", "pushing", "hit", "attack", "climbing",
    "shielded", "shielded_hit", "death", "falling",
)
# estados com uma tira so, que serve para qualquer direcao: sao as
# mortes e as quedas, que o personagem cai de lado em qualquerrum sentido
HERO_ANY_DIR: Tuple[str, ...] = ("death", "falling")
# a espada do golpe e maior que o corpo (32x32/32x48 contra 16x16), e
# entra POR CIMA do heroi, entao nao substitui a pose do personagem
HERO_EFEITO: Tuple[str, ...] = ("attack",)

HERO_FPS = 6
# FPS por estado: o golpe dura menos que o andar, senao a pausa na
# animacao de ataque parece travamento
HERO_FPS_ESTADO = {
    "idle": 5, "walk": 8, "attack": 14, "hit": 12, "death": 8,
}
EQUIP_DIR: Path = settings.SPRITES_DIR / "heroi_equipado"
ARMA_DIR: Path = settings.SPRITES_DIR / "armas"

_EQUIP_CACHE: dict[tuple[str, int], pygame.Surface] = {}
_ARMA_CACHE: dict[tuple[str, int], pygame.Surface] = {}


def _escala_de(img: pygame.Surface, escala: int) -> pygame.Surface:
    alvo = (img.get_width() * escala, img.get_height() * escala)
    return img if img.get_size() == alvo else pygame.transform.scale(img, alvo)


def carregar_equipado(conjunto: str, escala: int = 2) -> pygame.Surface | None:
    """O desenho do heroi com aquele conjunto nas maos."""
    if not EQUIP_DIR.is_dir():
        return None
    caminho = EQUIP_DIR / f"{conjunto}.png"
    if not caminho.is_file():
        return None
    chave = (conjunto, escala)
    pega = _EQUIP_CACHE.get(chave)
    if pega is not None:
        return pega
    try:
        img = _escala_de(_load_image(caminho), escala)
    except (pygame.error, OSError) as exc:
        print(f"[assets] conjunto ausente: {caminho.name} ({exc})")
        return None
    _EQUIP_CACHE[chave] = img
    return img


def carregar_arma(nome: str, escala: int = 2) -> pygame.Surface | None:
    """O desenho solto de uma arma, para o menu de equipamento."""
    if not ARMA_DIR.is_dir():
        return None
    caminho = ARMA_DIR / f"{nome}.png"
    if not caminho.is_file():
        return None
    chave = (nome, escala)
    pega = _ARMA_CACHE.get(chave)
    if pega is not None:
        return pega
    try:
        img = _escala_de(_load_image(caminho), escala)
    except (pygame.error, OSError) as exc:
        print(f"[assets] arma ausente: {caminho.name} ({exc})")
        return None
    _ARMA_CACHE[chave] = img
    return img


CASA_DIR: Path = settings.SPRITES_DIR / "casas"

_CASA_CACHE: dict[tuple[str, int], pygame.Surface] = {}


def carregar_casa(nome: str, escala: int = 2) -> pygame.Surface | None:
    """Desenha de um predio. A taverna e a casa do mercador.

    Predio e o mesmo problema do morador, em tamanho maior: o desenho
    vem do PixelLab, e se o arquivo nao existir a cena desenha um
    volume de madeira para o lugar nao sumir.
    """
    if not CASA_DIR.is_dir():
        return None
    caminho = CASA_DIR / f"{nome}.png"
    if not caminho.is_file():
        return None
    chave = (nome, escala)
    pega = _CASA_CACHE.get(chave)
    if pega is not None:
        return pega
    try:
        imagem = _load_image(caminho)
    except (pygame.error, OSError) as exc:
        print(f"[assets] predio ausente: {caminho.name} ({exc})")
        return None
    alvo = (imagem.get_width() * escala, imagem.get_height() * escala)
    if imagem.get_size() != alvo:
        imagem = pygame.transform.scale(imagem, alvo)
    _CASA_CACHE[chave] = imagem
    return imagem


# onde ficam os desenhos dos moradores da aldeia
MORADOR_DIR: Path = settings.SPRITES_DIR / "moradores"

_MORADOR_CACHE: dict[tuple[str, int], pygame.Surface] = {}


def carregar_morador(nome: str, escala: int = 2) -> pygame.Surface | None:
    """Carrega o desenho de um morador, ampliado e em cache.

    O morador e a mesma coisa andando e parado: ele nao tem animacao
    propria, e um desenho parado e melhor do que um retangulo de
    reserva. Se o arquivo nao existir, devolve None e a cena desenha o
    bloco colorido, que e o que fazia antes de os sprites existirem.
    """
    if not MORADOR_DIR.is_dir():
        return None
    caminho = MORADOR_DIR / f"{nome}.png"
    if not caminho.is_file():
        return None
    chave = (nome, escala)
    pega = _MORADOR_CACHE.get(chave)
    if pega is not None:
        return pega
    try:
        imagem = _load_image(caminho)
    except (pygame.error, OSError) as exc:
        print(f"[assets] morador ausente: {caminho.name} ({exc})")
        return None
    alvo = (imagem.get_width() * escala, imagem.get_height() * escala)
    if imagem.get_size() != alvo:
        imagem = pygame.transform.scale(imagem, alvo)
    _MORADOR_CACHE[chave] = imagem
    return imagem


def _medir_heroi() -> Tuple[int, int]:
    """Le do disco o tamanho de um quadro do heroi.

    A referencia de escala nao pode ser escrita a mao. O heroi ja foi
    trocado duas vezes (o sprite de 16x16 do Adventure Pack, depois o
    espadachim de 64x64 do pacote de mercado) e cada troca fazia o
    numero declarado divergir do arquivo, o que quebrava a caixa de
    escala e o teste de escala sem nenhum aviso.
    """
    if not HERO_DIR.is_dir():
        return (32, 32)
    for caminho in sorted(HERO_DIR.glob("hero_sul_idle_*.png")):
        try:
            imagem = pygame.image.load(caminho)
        except (pygame.error, OSError):
            continue
        return imagem.get_size()
    return (32, 32)


# tamanho do quadro do heroi como esta NO DISCO. As opcoes de escala
# multiplicam a partir daqui.
HERO_BASE: Tuple[int, int] = _medir_heroi()
# proporcao do quadro (largura / altura), usada para caber na tela
HERO_ASPECT = HERO_BASE[0] / HERO_BASE[1]


def fps_do_estado(estado: str) -> int:
    """Quadros por segundo da animacao `estado`."""
    return HERO_FPS_ESTADO.get(estado, HERO_FPS)


def carregar_animacao(
    direction: str,
    state: str = "walk",
    box: Tuple[int, int] | None = None,
    scale: int | None = None,
    prefixo: str = "hero",
    pasta: Path | None = None,
) -> list[pygame.Surface]:
    """Carrega os quadros de `direction` no `state` pedido, escalados.

    `state` distingue parado ("idle") de andando ("walk"): sem isso o
    heroi anda com a pose de caminhada mesmo parado, que e o jeito mais
    obvio de o sprite parecer errado.

    `box` e a area em tamanho 1x (o quanto o heroi ocupa na tela);
    `scale` e o enlarge das opcoes. Devolve lista vazia se a pasta de
    animacao nao existir, para o jogo continuar funcionando com o
    placeholder.
    """
    if direction not in HERO_DIRECTIONS:
        raise ValueError(f"direcao invalida: {direction!r}")
    if state not in HERO_STATES:
        raise ValueError(f"estado invalido: {state!r}")
    if box is None:
        # teto generoso: quem decide o tamanho final e a escala. A
        # cena que chama pode passar um teto menor se quiser limitar.
        box = (HERO_BASE[0] * 8, HERO_BASE[1] * 8)
    if scale is None:
        scale = _sprite_scale

    raiz = HERO_DIR if pasta is None else pasta
    if not raiz.is_dir():
        return []

    if state in HERO_ANY_DIR:
        padrao = f"{prefixo}_{state}_*.png"
    else:
        padrao = f"{prefixo}_{direction}_{state}_*.png"

    # Ordena pelo NUMERO do quadro, nao alfabeticamente. Com mais de
    # dez quadros, `sorted` entrega 0, 1, 10, 11, 2, 3... e a animacao
    # salta de um quadro para outro sem parar. O espadachim do pacote
    # de mercado tem 12 quadros de idle, que e exatamente onde isso
    # aparece.
    def numero(p: Path) -> tuple:
        digitos = p.stem.rsplit("_", 1)[-1]
        return (int(digitos),) if digitos.isdigit() else (10**9, p.name)

    frames = []
    for path in sorted(raiz.glob(padrao), key=numero):
        try:
            image = _load_image(path)
            frames.append(fit_box(image, box, scale=scale))
        except (pygame.error, OSError) as exc:
            print(f"[assets] falha ao carregar {path}: {exc}")
    return frames


def load_animation(
    direction: str,
    state: str = "walk",
    box: Tuple[int, int] | None = None,
    scale: int | None = None,
) -> list[pygame.Surface]:
    """Atalho para a animacao do heroi. Ver `carregar_animacao`."""
    return carregar_animacao(direction, state, box, scale)


def has_animation(direction: str = "sul", state: str = "walk") -> bool:
    """True se existe ao menos um quadro da animacao pedida."""
    return bool(carregar_animacao(direction, state, box=(1, 1), scale=1))


# --- inimigos ------------------------------------------------------
# Os esqueletos vem em folha de 16x32 (o corpo e esguio, nao quadrado
# como o do heroi), com um ciclo de andar e um de ataque por direcao.
FOE_DIR = settings.SPRITES_DIR / "inimigo"
# O ghoul vem do pacote gfx e tem corpo de verdade: bracos, pernas e
# sombra. O esqueleto do Skeletons Pack e uma arte de 6px de largura por
# 21 de altura, que mesmo normalizado sai com 30px de largura contra 96
# do jogador na escala 3x e le como um palito. Os dois continuam
# disponiveis: o ghoul e o inimigo principal, o esqueleto fica como
# variante mais fraca.
FOE_GHOUL = FOE_DIR / "ghoul"
FOE_SKELETON = FOE_DIR
FOE_KINDS: Tuple[str, ...] = ("ghoul", "ghoul", "skeleton_5", "ghoul")
FOE_STATES: Tuple[str, ...] = ("walk", "attack")
FOE_BASE: Tuple[int, int] = (32, 64)


def load_foe(
    kind: str,
    direction: str,
    state: str = "walk",
    box: Tuple[int, int] | None = None,
    scale: int | None = None,
) -> list[pygame.Surface]:
    """Quadros de um inimigo. Devolve vazio se o tipo nao existir."""
    if direction not in HERO_DIRECTIONS:
        raise ValueError(f"direcao invalida: {direction!r}")
    if state not in FOE_STATES:
        raise ValueError(f"estado de inimigo invalido: {state!r}")
    if box is None:
        box = (FOE_BASE[0] * 6, FOE_BASE[1] * 6)
    if scale is None:
        scale = _sprite_scale
    # o ghoul mora numa subpasta; o esqueleto, na raiz
    pasta = FOE_GHOUL if kind.startswith("ghoul") else FOE_SKELETON
    if not pasta.is_dir():
        return []
    return carregar_animacao(
        direction, "attack" if state == "attack" else "walk",
        box=box, scale=scale, prefixo=kind, pasta=pasta,
    )

