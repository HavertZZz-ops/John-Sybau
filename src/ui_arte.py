"""Os paineis de UI vindos do pacote do CraftPix, na paleta do jogo.

A estrutura dos menus vem da arte: moldura, titulo, os botoes BUY da
loja e os contadores de moeda. O CONTEUDO continua sendo desenhado pelo
codigo, porque o jogo tem duas pocas e uma moeda, e a arte do pacote
mostra item generico.

Os paineis sao pequenos (de 110x85 a 123x149) e o jogo roda em
qualquer resolucao. Por isso sao ampliados por um fator INTEIRO: meio
pixel de arte de pixel fica com cara de borra, e o jogo inteiro foi
construido em pixel art limpa.
"""
from __future__ import annotations

import pathlib
from functools import lru_cache

import pygame

UI_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "ui"

# qual painel usar em cada lugar. Os numeros sao os que o
# `tools/fatiar_ui.py` gerou, por ordem de coluna na folha.
PAINEL_INVENTARIO = "inventory_1"   # 110x101, com INVENTORY e contadores
PAINEL_LOJA = "shop_3"              # 123x149, SHOP com os seis BUY
PAINEL_EQUIPAMENTO = "equipment_0"  # 160x85, com a silhueta do heroi
# o menu de combate e a fileira de slots da folha Action_panel, cortada
# na mao por `tools/fatiar_acao.py`: o detector automatico achava zero
# paineis nessa folha, que e solta e nao tem grade regular
PAINEL_ACAO_BAR = "action_bar"        # 168x18, dez slots de madeira
PAINEL_ACAO_HEADER = "action_header"  # 164x17, a faixa dourada

_cache: dict[str, pygame.Surface] = {}
_cache_icones: dict[str, pygame.Surface] = {}


def carregar(nome: str) -> pygame.Surface | None:
    """O painel como esta no disco, sem ampliar."""
    if nome in _cache:
        return _cache[nome]
    caminho = UI_DIR / f"{nome}.png"
    if not caminho.is_file():
        return None
    try:
        img = pygame.image.load(str(caminho)).convert_alpha()
    except (pygame.error, OSError) as exc:
        print(f"[ui] painel ausente: {nome} ({exc})")
        return None
    _cache[nome] = img
    return img


def fator_de_escala(base: int) -> int:
    """Quantas vezes ampliar o painel, em inteiro.

    A arte e de 110 a 160px. Numa tela 1920 isso daria 18% da largura e
    um painel minusculo; o fator inteiro evita o meio pixel que
    desfaz a pixel art.
    """
    if base >= 2200:
        return 7
    if base >= 1600:
        return 6
    if base >= 1280:
        return 5
    return 4


def desenhar(
    surface: pygame.Surface,
    nome: str,
    centro: tuple[int, int],
    largura_alvo: int,
    topo_rel: float = 0.24,
    base_rel: float = 0.90,
) -> pygame.Rect | None:
    """Desenha o painel ampliado e devolve o retangulo do miolo.

    O miolo e o painel sem a moldura: e onde o conteudo entra. A
    margem e medida em fracao da altura, porque a moldura do pacote
    tem 6px de um total de 101.

    `topo_rel` e `base_rel` existem porque cada painel tem a barra de
    titulo em um lugar diferente: na loja os slots comecam em 10% da
    altura, e nao nos 24% que serve para o inventario.
    """
    img = carregar(nome)
    if img is None:
        return None

    fator = max(1, min(8, largura_alvo // img.get_width()))
    alvo = (img.get_width() * fator, img.get_height() * fator)
    if img.get_size() != alvo:
        img = pygame.transform.scale(img, alvo)

    rect = img.get_rect(center=centro)
    surface.blit(img, rect)

    # o miolo: tira a moldura e a barra de titulo de cima, e a barra
    # dos contadores de baixo
    margem_x = int(img.get_width() * 0.06)
    topo = int(img.get_height() * topo_rel)
    base = int(img.get_height() * base_rel)
    miolo = pygame.Rect(
        rect.x + margem_x,
        rect.y + topo,
        rect.width - 2 * margem_x,
        max(10, base - topo),
    )
    return miolo


def _frac(miolo: pygame.Rect, x: float, y: float,
          larg: float, alt: float) -> pygame.Rect:
    """Um retangulo por fracao do miolo."""
    return pygame.Rect(
        int(miolo.x + miolo.width * x),
        int(miolo.y + miolo.height * y),
        int(miolo.width * larg),
        int(miolo.height * alt),
    )


# A geometria da folha SHOP foi medida com `tools/medir_loja.py`: tres
# colunas, duas fileiras de slots e um botao BUY embaixo de cada slot.
# Sao frações do miolo, e nao pixels, para acompanhar o painel ampliado.
_LOJA_X = 0.092
_LOJA_LARGURA_COLUNA = 0.263
_LOJA_Y = 0.017
_LOJA_ALTURA = 0.170
_LOJA_PASSO_Y = 0.455
_LOJA_BOTAO_Y = 0.294
_LOJA_BOTAO_ALTURA = 0.094
_LOJA_BOTAO_PASSO_Y = 0.472


def slots_da_loja(miolo: pygame.Rect, total: int = 6) -> list[pygame.Rect]:
    """Os seis slots da vitrine, na ordem em que a arte os desenhou."""
    return [
        _frac(
            miolo,
            _LOJA_X + (i % 3) * _LOJA_LARGURA_COLUNA,
            _LOJA_Y + (i // 3) * _LOJA_PASSO_Y,
            _LOJA_LARGURA_COLUNA,
            _LOJA_ALTURA,
        )
        for i in range(total)
    ]


def botao_da_loja(miolo: pygame.Rect, indice: int) -> pygame.Rect | None:
    """O botao BUY de um slot, para acender junto com o item."""
    if indice < 0 or indice > 5:
        return None
    return _frac(
        miolo,
        _LOJA_X + (indice % 3) * _LOJA_LARGURA_COLUNA,
        _LOJA_BOTAO_Y + (indice // 3) * _LOJA_BOTAO_PASSO_Y,
        _LOJA_LARGURA_COLUNA,
        _LOJA_BOTAO_ALTURA,
    )


def slot(
    surface: pygame.Surface,
    miolo: pygame.Rect,
    indice: int,
    total: int,
    tam: int = 14,
) -> pygame.Rect:
    """O retangulo do item `indice`, em uma fileira de `total`."""
    largura = total * tam + (total - 1) * 6
    x = miolo.centerx - largura // 2
    y = miolo.centery - tam // 2
    return pygame.Rect(x + indice * (tam + 6), y, tam, tam)


def contador_de_moeda(surface: pygame.Surface, rect: pygame.Rect,
                      ouro: int) -> None:
    """O numero de ouro, alinhado com o contador do painel.

    O pacote traz o desenho do contador no rodape do painel. O
    numero e desenhado em cima dele, e nao em um canto solto, senao
    o jogador nao sabe a que o numero se refere.
    """
    from . import theme

    caixa = pygame.Rect(rect.x + 8, rect.bottom - 14, 90, 14)
    theme.text_tracked_at(
        surface, f"{ouro}", 13, (caixa.x + 12, caixa.y), theme.GOLD)


def icone(nome: str) -> pygame.Surface | None:
    """Um icone solto de `assets/ui/icones`, como esta no disco."""
    if nome in _cache_icones:
        return _cache_icones[nome]
    caminho = UI_DIR / "icones" / f"icone_{nome}.png"
    if not caminho.is_file():
        return None
    try:
        img = pygame.image.load(str(caminho)).convert_alpha()
    except (pygame.error, OSError) as exc:
        print(f"[ui] icone ausente: {nome} ({exc})")
        return None
    _cache_icones[nome] = img
    return img


def slots_da_barra(
    rect: pygame.Rect, quantos: int, total: int = 5
) -> list[pygame.Rect]:
    """Os slots do `action_bar`, da esquerda para a direita.

    A folha foi cortada em cinco slots, e o jogo tem cinco acoes, entao
    o padrao e um slot por acao.
    """
    total = max(1, total)
    largura = rect.width / total
    return [
        pygame.Rect(
            int(rect.x + i * largura),
            rect.y,
            int(largura),
            rect.height,
        )
        for i in range(min(quantos, total))
    ]