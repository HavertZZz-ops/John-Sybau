"""Fatia os paineis de UI e joga em assets/ui/.

Duas deteccoes, nenhuma medida no olho:

  - as COLUNAS vazias separam um painel do outro;
  - as LINHAS vazias separam o painel das pecas soltas do rodape
    (botoes BUY e fita de icones).

Cada painel e a intersecao de uma faixa de coluna com a PRIMEIRA
faixa de linha dele. Sem a segunda deteccao o recorte levava a fita de
icones junto e o painel saia com 240 de altura em vez de 160.
"""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(pathlib.Path(
    r"C:\Users\jhnnl\AppData\Local\Temp\opencode\pacotes")))

from recolorir_ui import converter  # noqa: E402

import pygame  # noqa: E402

UI = (pathlib.Path(
    r"C:\Users\jhnnl\AppData\Local\Temp\opencode\pacotes"
) / "craftpix-net-255216-free-basic-pixel-art-ui-for-rpg" / "PNG")
DESTINO = RAIZ / "assets" / "ui"
DESTINO.mkdir(parents=True, exist_ok=True)


def _faixas(vazia: list[bool], minimo: int = 2) -> list[tuple[int, int]]:
    """Faixas de [inicio, fim) com conteudo, pulando vaos >= minimo."""
    partes = []
    x = 0
    n = len(vazia)
    while x < n:
        if not vazia[x]:
            inicio = x
            buraco = 0
            while x < n:
                if vazia[x]:
                    buraco += 1
                    # um espaco de 1 coluna dentro do desenho e a
                    # propria borda do pixel, nao uma separacao
                    if buraco >= minimo:
                        break
                else:
                    buraco = 0
                x += 1
            fim = x - buraco + 1 if buraco else x
            if fim > inicio:
                partes.append((inicio, fim))
        x += 1
    return partes


def _vazias(img: pygame.Surface, eixo: str) -> list[bool]:
    w, h = img.get_size()
    out = []
    n = w if eixo == "coluna" else h
    for i in range(n):
        vazia = True
        for j in range(h if eixo == "coluna" else w):
            x, y = (i, j) if eixo == "coluna" else (j, i)
            if img.get_at((x, y))[3] > 8:
                vazia = False
                break
        out.append(vazia)
    return out


def fatiar(img: pygame.Surface) -> list[tuple[str, pygame.Surface]]:
    colunas = _faixas(_vazias(img, "coluna"))
    saida = []
    for ci, (x0, x1) in enumerate(colunas):
        if x1 - x0 < 16:
            continue
        # as linhas, so dentro deste painel
        recorte_x = img.subsurface(pygame.Rect(x0, 0, x1 - x0, img.get_height()))
        linhas = _faixas(_vazias(recorte_x, "linha"))
        if not linhas:
            continue
        y0, y1 = linhas[0]          # so a primeira: o painel
        if y1 - y0 < 40:
            continue
        saida.append((
            f"{x0},{y0},{x1 - x0},{y1 - y0}",
            recorte_x.subsurface(pygame.Rect(0, y0, x1 - x0, y1 - y0)).copy(),
        ))
    return saida


def main() -> int:
    pygame.init()
    pygame.display.set_mode((8, 8))

    total = 0
    for nome in ("Shop", "Inventory", "Equipment", "Action_panel",
                 "character_panel", "Main_menu"):
        caminho = UI / f"{nome}.png"
        if not caminho.is_file():
            print(f"{nome}: ausente")
            continue
        img = pygame.image.load(str(caminho)).convert_alpha()
        pedacos = fatiar(img)
        print(f"{nome}.png {img.get_size()}: {len(pedacos)} painel(is)")
        for i, (caixa, pedaco) in enumerate(pedacos):
            conv = converter(pedaco)
            saida = DESTINO / f"{nome.lower()}_{i}.png"
            pygame.image.save(conv, str(saida))
            total += 1
            print(f"  {saida.name}  {conv.get_size()}  origem {caixa}")

    print("\nno total:", total, "painéis em assets/ui")
    return 0


if __name__ == "__main__":
    sys.exit(main())