"""Cacos, barris e sacos espalhados no chao da masmorra.

A sala era uma laje marrom vazia. Nao havia nada no chao: nem um osso,
nem um barril caindo. Em um lugar called "Parish of the Undead" o
chao e o que conta, e um chao liso nao conta nada.

Aqui a mesma folha de pequenos itens do pacote de interiores — que a
taverna ja usava para copo e garrafa — e fatiada de novo em Pecas de
cenario: osso, osso partido, barril, barril aberto, saco, pote, e o
monte de ossos. A distribuicao e FIXA por semente: o mesmo mapa gera
sempre a mesma sala, e um caco nao muda de lugar entre duas visitas.

Nenhuma peca bloqueia o caminho. Sao enfeite, e um enfeite que barra o
jogador e um bug de jogabilidade, nao um obstaculo.
"""

from __future__ import annotations

import pathlib
import random
import sys

import pygame

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CELULA = 16
DESTINO = RAIZ / "assets" / "sprites" / "cenario"
FONTE = RAIZ / "assets" / "interior" / "fontes" / "TopDownHouse_SmallItems.png"

# nome, coluna, linha. Medidas na folha com a grade de 16 rotulada.
PECAS = (
    ("osso_monte", 0, 0, 1, 2),
    ("osso", 0, 2, 1, 1),
    ("barril_chao", 4, 4, 1, 1),
    ("barril_aberto", 6, 4, 1, 1),
    ("saco", 1, 5, 1, 1),
    ("pote_roxo", 5, 3, 1, 1),
    ("pote_branco", 6, 3, 1, 1),
    ("panela", 1, 2, 1, 1),
    ("livro", 0, 3, 1, 1),
)


def fatiar(forcar: bool = False) -> dict[str, pygame.Surface]:
    """Recorta os enfeites para `assets/sprites/cenario`.

    SO roda com o jogo fechado, ou quando os arquivos ja existem e nao
    ha janela. A regra de ouro: NENHUMA funcao deste modulo chamada em
    tempo de execucao pode mexer no modo de video. O
    `set_mode((1, 1))` de antes rodava com o jogo ABERTO — a masmorra
    chama `distribuir` no `__init__` — e trocava a janela do jogador
    por uma de um pixel. Todas as fotos de tela sairam de 1x1.
    """
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_init() and pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))

    faltando = [p for p in PECAS
                if forcar or not (DESTINO / f"{p[0]}.png").is_file()]
    if not faltando:
        return {}

    DESTINO.mkdir(parents=True, exist_ok=True)
    folha = pygame.image.load(str(FONTE)).convert_alpha()
    arte = {}
    for nome, col, lin, cols, lins in faltando:
        peca = pygame.Surface((cols * CELULA, lins * CELULA), pygame.SRCALPHA)
        peca.blit(folha, (0, 0), pygame.Rect(
            col * CELULA, lin * CELULA, cols * CELULA, lins * CELULA))
        pygame.image.save(peca, str(DESTINO / f"{nome}.png"))
        arte[nome] = peca
    return arte


def distribuir(mapa, quantos: int, semente: int) -> list[tuple[int, int, str]]:
    """Sorteia as pecas em celulas andaveis, longe do caixao.

    Devolve [(x, y, nome)] em COORDENADAS DE CELULA. Nao fatia: os
    PNG ja estao no repositorio e a cena so precisa do nome.
    """
    nomes = [p[0] for p in PECAS]
    rng = random.Random(semente * 7919 + 13)
    caixao = tuple(mapa.caixao)
    saida = tuple(getattr(mapa, "saida", caixao))
    escolhidos: list[tuple[int, int, str]] = []
    ocupado: set[tuple[int, int]] = set()
    tentativas = 0
    while len(escolhidos) < quantos and tentativas < quantos * 60:
        tentativas += 1
        x = rng.randrange(1, max(2, mapa.largura - 1))
        y = rng.randrange(1, max(2, mapa.altura - 1))
        if not mapa.andavel(x, y):
            continue
        if (x, y) in ocupado:
            continue
        # longe do caixao e da saida: o jogador nao acorda em cima de
        # um barril e a saida nao fica escondida atras de um
        if abs(x - caixao[0]) + abs(y - caixao[1]) < 4:
            continue
        if abs(x - saida[0]) + abs(y - saida[1]) < 3:
            continue
        ocupado.add((x, y))
        escolhidos.append((x, y, rng.choice(nomes)))
    return escolhidos


_enfeite_cache: dict[tuple[str, int], pygame.Surface | None] = {}


def carregar_enfeite(nome: str, lado: int) -> pygame.Surface | None:
    """Um enfeite ja cortado, no tamanho pedido.

    Compartilhado com a cena de combate, que desenha os mesmos barris e
    ossos da sala numa faixa atras dos lutadores. O cache e por tamanho:
    a luta usa meia altura de tile e o mapa inteiro.
    """
    chave = (nome, lado)
    if chave in _enfeite_cache:
        return _enfeite_cache[chave]
    caminho = DESTINO / f"{nome}.png"
    if not caminho.is_file():
        _enfeite_cache[chave] = None
        return None
    try:
        original = pygame.image.load(str(caminho)).convert_alpha()
    except (pygame.error, OSError):
        _enfeite_cache[chave] = None
        return None
    escala = max(1, lado // max(1, original.get_height()))
    arte = pygame.transform.scale(
        original,
        (max(1, original.get_width() * escala),
         max(1, original.get_height() * escala)),
    )
    _enfeite_cache[chave] = arte
    return arte


def desenhar(surface: pygame.Surface, mapa, pecas, tile: int,
             camera: pygame.Vector2, janela: tuple[int, int]) -> None:
    """Desenha os enfeites. Sem colisao: sao cacos no chao.

    O enfeite tem a altura de UM TILE. Com metade disso ele saia com 16px
    num chao de 48px e virava um pontinho que o jogador nao via e nao
    entendia — enfeite pequeno demais e o mesmo que enfeite nenhum.
    """
    _cache: dict[tuple[str, int], pygame.Surface] = {}
    for x, y, nome in pecas:
        img = _cache.get((nome, tile))
        if img is None:
            original = pygame.image.load(
                str(DESTINO / f"{nome}.png")
            ).convert_alpha()
            # um tile de altura; a largura acompanha a proporcao da arte
            escala = max(1, tile // max(1, original.get_height()))
            img = pygame.transform.scale(
                original,
                (max(1, original.get_width() * escala),
                 max(1, original.get_height() * escala)),
            )
            _cache[(nome, tile)] = img
        px = x * tile - camera.x + janela[0] // 2
        py = y * tile - camera.y + janela[1] // 2
        surface.blit(img, img.get_rect(midbottom=(px, py + tile // 3)))


if __name__ == "__main__":
    # o preview entra AQUI, e nao no topo: la ele montaria o jogo, que
    # importa a masmorra, que importa este modulo — e o pacote entraria
    # pela metade, com `cenario` valendo None dentro da masmorra.
    sys.path.insert(0, str(RAIZ / "tools"))
    from preview_real import abrir  # noqa: E402

    janela, ger, config = abrir()
    from src.estado import Estado  # noqa: E402
    from src.progresso import Progresso  # noqa: E402

    ger.ui_state.clear()
    ger.ui_state["progresso"] = Progresso()
    ger.ui_state["estado"] = Estado(vida=30, ouro=0)
    ger.switch("dungeon")
    cena = ger.active
    cena.on_enter()
    pecas = distribuir(cena.mapa, 26, 3)
    print(f"{len(pecas)} enfeites em um mapa de {cena.mapa.largura}x{cena.mapa.altura}")
    for _ in range(int(7.0 / 60)):
        ger.update(1 / 60)
    ger.draw()
    desenhar(ger.window, cena.mapa, pecas, cena.tile,
             cena.camera, cena.size)
    pygame.image.save(ger.window, str(RAIZ / "preview_decoracao.png"))
    print("preview_decoracao.png")