"""Fatia o pacote Top-Down Retro Interior nas pecas que a taverna usa.

O pacote vem em seis folhas soltas, sem indice. Este script recorta
pelas CELULAS da grade de 16px, que e a grade com que as folhas foram
desenhadas, e salva cada peca com um nome que o jogo consegue ler.

As folhas originais vao para `assets/interior/fontes` para que o corte
seja reproduzivel sem o zip. As coordenadas sao (coluna, linha) na
grade de 16.
"""

from __future__ import annotations

import pathlib

import pygame

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "assets" / "interior"
FONTES = DESTINO / "fontes"
CELULA = 16

# as folhas que o jogo usa, e o que cada uma e
FOLHAS = {
    "paredes": "TopDownHouse_FloorsAndWalls.png",
    "moveis1": "TopDownHouse_FurnitureState1.png",
    "moveis2": "TopDownHouse_FurnitureState2.png",
    "itens": "TopDownHouse_SmallItems.png",
    "portas": "TopDownHouse_DoorsAndWindows.png",
}

# nome, folha, coluna, linha, colunas, linhas  (a peca pode ter 2x3)
#
# As coordenadas foram lidas de `preview_int_rotulado.png`, que e a
# folha com a grade de 16 rotulada. A primeira versao adivinhou a
# partir de uma imagem sem grade e errou metade: o que era mesa virou
# sofa, o que era balcao virou banco, e dois "barris" eram pedaco de
# tapete.
PECAS: tuple[tuple[str, str, int, int, int, int], ...] = (
    # --- salao da taverna ------------------------------------------
    ("balcao", "moveis1", 6, 12, 7, 3),     # o balcao longo do fundo
    ("adega", "moveis1", 2, 3, 3, 1),       # prateleira de garrafas
    ("estante", "moveis1", 2, 4, 2, 2),     # estante de livros
    ("estante2", "moveis1", 4, 4, 3, 2),    # estante grande
    ("armario", "moveis1", 0, 12, 2, 2),    # armario alto
    ("mesa", "moveis1", 1, 10, 3, 1),       # mesa redonda de madeira
    ("sofa", "moveis1", 4, 10, 2, 2),       # sofa de duas poltronas
    ("poltrona", "moveis1", 11, 7, 2, 3),   # poltrona
    ("banco", "moveis1", 2, 16, 2, 1),      # mesa pequena
    ("cadeira", "moveis1", 7, 16, 1, 2),    # cadeira
    ("relogio", "moveis1", 4, 7, 1, 3),     # relogio de parede
    ("luminaria", "moveis1", 6, 7, 1, 3),   # luminaria de pe
    ("espelho", "moveis1", 7, 7, 2, 3),     # espelho alto
    ("lareira", "moveis1", 10, 7, 1, 3),    # lareira
    ("vaso", "moveis1", 0, 10, 1, 2),       # vaso com planta
    ("tapete", "moveis1", 7, 2, 2, 2),      # tapete de palha
    ("tapete2", "moveis1", 10, 3, 3, 2),    # tapete vermelho
    ("bau", "moveis1", 11, 17, 2, 1),      # bau
    # --- piso e parede ----------------------------------------------
    # as cores foram lidas da folha, nao adivinhadas: o que fica em
    # (6,1) e tijolo laranja e nao creme, e o que fica em (9,3) e creme
    # e nao tijolo. A primeira versao trocou os tres e a sala saia com
    # parede da mesma cor do chao.
    ("piso_terra", "paredes", 4, 3, 1, 1),     # (125,104,18) oliva
    ("piso_claro", "paredes", 9, 3, 1, 1),     # (232,198,157) creme
    ("parede_tijolo", "paredes", 6, 1, 1, 1),  # (194,96,18) laranja
    # --- porta ------------------------------------------------------
    # so a porta aberta entra: e a saida do salao, e a unica peca
    # desta folha que a taverna usa.
    ("porta_aberta", "portas", 1, 0, 1, 1),
)


def carregar(folhas: dict[str, pygame.Surface]) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    FONTES.mkdir(parents=True, exist_ok=True)
    for chave, arquivo in FOLHAS.items():
        origem = FONTES / arquivo
        if not origem.is_file():
            raise SystemExit(
                f"folha ausente: {origem}\n"
                "copie os PNG de Top-Down_Retro_Interior.zip para "
                "assets/interior/fontes"
            )
        folhas[chave] = pygame.image.load(str(origem)).convert_alpha()


def main() -> int:
    folhas: dict[str, pygame.Surface] = {}
    carregar(folhas)

    onde: dict[str, pathlib.Path] = {}
    for nome, folha, col, lin, cols, linhas in PECAS:
        img = folhas[folha]
        x, y = col * CELULA, lin * CELULA
        w, h = cols * CELULA, linhas * CELULA
        if x + w > img.get_width() or y + h > img.get_height():
            print(f"[aviso] {nome}: fora da folha {folha}")
            continue
        pedaco = pygame.Surface((w, h), pygame.SRCALPHA)
        pedaco.blit(img, (0, 0), pygame.Rect(x, y, w, h))
        saida = DESTINO / f"{nome}.png"
        pygame.image.save(pedaco, str(saida))
        onde[nome] = saida

    print(f"{len(onde)} pecas em {DESTINO}")
    for nome, caminho in sorted(onde.items()):
        img = pygame.image.load(str(caminho))
        print(f"  {nome:16s} {img.get_width():3d}x{img.get_height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())