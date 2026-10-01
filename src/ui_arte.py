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


def contador_de_moeda(surface: pygame.Surface, faixa: pygame.Rect,
                      ouro: int) -> None:
    """O numero de ouro, em cima do contador que vem na arte do painel.

    `faixa` e a faixa de rodape do inventario, e nao o painel inteiro.
    O numero e desenhado dentro dela: a arte ja traz o desenho da
    moeda no rodape do painel, e o numero precisa cair em cima. Com uma
    caixa fixa na ultima linha, o numero saia abaixo do desenho e
    acabava em cima do mapa, fora do painel.
    """
    from . import theme

    x = faixa.x + int(faixa.width * _INVENTARIO_CONTADOR_X)
    y = faixa.y + int(faixa.height * _INVENTARIO_CONTADOR_TOPO)
    theme.text_tracked_at(surface, f"{ouro}", 13, (x, y), theme.GOLD)


# A grade de itens ocupa so esta fracao da altura do miolo. O resto e a
# faixa do rodape, onde moram o desenho do conjunto, o rotulo dele e o
# contador de ouro.
#
# Antes a grade usava o miolo INTEIRO e as tres coisas caíam no mesmo
# lugar: a ultima fileira ficava embaixo do desenho do heroi, o rotulo
# do conjunto caia em cima do heroi, e o contador caia em cima do
# rotulo. Na foto de 1008x720 o rodape saia uma massa embaralhada em
# que "Punhos / Sem espada" estava por cima do boneco e o "520" por
# cima do "q ou esc fecha".
_INVENTARIO_GRADE = 0.70
# o desenho do conjunto e encostado na direita da faixa
_INVENTARIO_CONJUNTO_LADO = 0.30
# o quanto o desenho fica acima do pe, para nao encostar na borda
_INVENTARIO_CONJUNTO_FOLGA = 4
# o rodape do painel tem um desenho de contador na propria arte, e o
# numero tem de cair em cima dele. A arte foi medida: o contador esta a
# 7% da altura do miolo acima da base, e comeca na esquerda. Antes o
# numero usava uma caixa fixa de 14px de altura na ultima linha do
# miolo, e com o rodape novo ele saia abaixo do desenho do contador,
# caindo fora do painel em cima do mapa.
_INVENTARIO_CONTADOR_TOPO = 0.72
_INVENTARIO_CONTADOR_X = 0.10


def _cabe(miolo: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect]:
    """`(grade, rodape)`: a parte dos itens e a faixa de baixo."""
    altura_grade = int(miolo.height * _INVENTARIO_GRADE)
    grade = pygame.Rect(miolo.x, miolo.y, miolo.width, altura_grade)
    rodape = pygame.Rect(
        miolo.x, grade.bottom, miolo.width, miolo.bottom - grade.bottom
    )
    return grade, rodape


def _caber(arte: pygame.Surface, altura: int) -> pygame.Surface:
    """A arte reduzida para caber em `altura`, sem esticar."""
    if arte.get_height() <= altura:
        return arte
    escala = max(1, altura // arte.get_height())
    if arte.get_height() * escala > altura:
        # nao cabe em inteiro: o ultimo passo e com filtro, e a arte e
        # grande demais para perder o pixel inteiro
        return pygame.transform.smoothscale(
            arte, (max(1, arte.get_width() * altura // arte.get_height()),
                   altura)
        )
    return pygame.transform.scale(
        arte, (arte.get_width() * escala, arte.get_height() * escala)
    )


def desenhar_inventario(
    surface: pygame.Surface,
    miolo: pygame.Rect,
    linhas: list[tuple],
    *,
    conjunto: pygame.Surface | None = None,
    rotulo: str = "",
    ouro: int = 0,
) -> None:
    """O conteudo do painel de inventario: grade, conjunto e ouro.

    As quatro cenas do mundo tinham cada uma a sua copia deste desenho,
    com a mesma conta e o mesmo defeito de layout. Aqui a conta e uma,
    e quem chama passa o que ja tinha calculado: o conjunto vem pronto
    das cenas, e nao de um import novo deste modulo, que e so layout.
    """
    from . import theme

    grade, rodape = _cabe(miolo)

    if not linhas:
        theme.text_tracked_at(
            surface, "Voce nao carrega nada", 16,
            (grade.centerx - 60, grade.centery - 8), theme.TEXT_DIM)
    else:
        COLUNAS = 5
        fileiras = 4
        cw = grade.width // COLUNAS
        ch = grade.height // fileiras
        for i, (_id, item, qtd) in enumerate(linhas[:COLUNAS * fileiras]):
            cx = grade.x + (i % COLUNAS) * cw
            cy = grade.y + (i // COLUNAS) * ch
            caixa = pygame.Rect(cx + 3, cy + 3, cw - 6, ch - 6)
            pygame.draw.rect(surface, theme.BACKGROUND_SOFT, caixa)
            pygame.draw.rect(surface, theme.HAIRLINE, caixa, 1)
            palavras = item.nome.split()
            theme.text_tracked_at(
                surface, palavras[0][:9], 13,
                (caixa.x + 4, caixa.y + 8), theme.TEXT)
            if len(palavras) > 1:
                theme.text_tracked_at(
                    surface, " ".join(palavras[1:])[:14], 11,
                    (caixa.x + 4, caixa.y + 26), theme.TEXT_DIM)
            theme.text_tracked_at(
                surface, f"x{qtd}", 12,
                (caixa.right - 26, caixa.bottom - 16), theme.GOLD)

    # a faixa de baixo: o conjunto em pe a direita, o rotulo a esquerda
    # dele, e o contador na linha de baixo, em cima do desenho do
    # contador que ja vem na arte do painel
    if conjunto is not None:
        altura_desenho = rodape.height - _INVENTARIO_CONJUNTO_FOLGA
        desenho = _caber(conjunto, altura_desenho)
        largura_reservada = int(rodape.width * _INVENTARIO_CONJUNTO_LADO)
        x = rodape.right - max(largura_reservada, desenho.get_width()) + 4
        surface.blit(desenho, desenho.get_rect(
            midbottom=(x, rodape.bottom - _INVENTARIO_CONJUNTO_FOLGA)))

    if rotulo:
        theme.text_tracked_at(
            surface, rotulo, 13,
            (rodape.x + 8, rodape.centery - 7), theme.GOLD)

    contador_de_moeda(surface, rodape, ouro)


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