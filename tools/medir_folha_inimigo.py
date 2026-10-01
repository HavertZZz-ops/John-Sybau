"""A grade real da folha de esqueleto, medida pelo conteudo.

O importador fatia em 16x32. Se a folha for de 32x32, cada quadro corta
dois esqueletos ao meio — e era exatamente o que aparecia na tela: um
manto roxo sem cabeca, e um cogumelo creme.
"""

import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))

pygame.init()
pygame.display.set_mode((8, 8))

folhas = sorted(
    (RAIZ / "assets" / "raw" / "skeletons").rglob(
        "Skeleton_*-Sheet-NoOutline.png"
    )
)
for caminho in folhas:
    img = pygame.image.load(caminho).convert_alpha()
    w, h = img.get_size()

    # linhas e colunas que tem conteudo
    cols = [x for x in range(w)
            if any(img.get_at((x, y))[3] > 8 for y in range(h))]
    linhas = [y for y in range(h)
              if any(img.get_at((x, y))[3] > 8 for x in range(w))]

    print(f"\n{caminho.name}  {w}x{h}")
    if not cols or not linhas:
        print("   vazia")
        continue
    print(f"   conteudo em x {cols[0]}..{cols[-1]}   "
          f"y {linhas[0]}..{linhas[-1]}")

    # a altura do desenho e um forte indicio do tamanho da celula
    alturas = []
    for y in range(linhas[0], linhas[-1] + 1):
        n = sum(1 for x in range(w) if img.get_at((x, y))[3] > 8)
        if n:
            alturas.append(n)
    print(f"   pixels por linha: min {min(alturas)} max {max(alturas)}")

    # onde comeca cada linha de quadro: a linha que fica vazia entre
    # duas linhas com conteudo e uma divisa de celula
    print("   linhas vazias (divisas) em y:",
          [y for y in range(linhas[0], linhas[-1] + 1)
           if all(img.get_at((x, y))[3] <= 8 for x in range(w))][:24])