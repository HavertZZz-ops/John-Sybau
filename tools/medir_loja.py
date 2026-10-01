"""Mede onde os slots e os botoes BUY ficam na arte da loja.

Em vez de chutar fracao da altura, o script procura na imagem: os slots
sao as caixas ESCURAS dentro do painel e os botoes BUY sao as faixas
DOURADAS. Devolve as fracoes em relacao ao miolo, que e o que o jogo
usa para desenhar o conteudo.
"""

import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))
from src import ui_arte  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

img = ui_arte.carregar(ui_arte.PAINEL_LOJA)
if img is None:
    raise SystemExit("painel da loja ausente")
w, h = img.get_size()
print(f"{ui_arte.PAINEL_LOJA}: {w}x{h}")

# o miolo que o jogo usa
fator = 1
miolo_x = int(w * 0.06)
topo = int(h * 0.24)
base = int(h * 0.90)
miolo = pygame.Rect(miolo_x, topo, w - 2 * miolo_x, max(10, base - topo))
print(f"miolo: x={miolo.x} y={miolo.y} {miolo.width}x{miolo.height}")

# varre a coluna do meio e classifica cada linha: escuro (slot), claro
# (madeira) ou dourado (botao BUY)
col = w // 2
linhas = []
for y in range(h):
    r, g, b, _ = img.get_at((col, y))
    if r > 150 and g > 110 and b < 110:
        linhas.append(("ouro", y))
    elif r < 70 and g < 70 and b < 70:
        linhas.append(("escuro", y))
    else:
        linhas.append(("madeira", y))

# agrupa sequencias iguais
grupos = []
for tipo, y in linhas:
    if grupos and grupos[-1][0] == tipo:
        grupos[-1][2] = y
    else:
        grupos.append([tipo, y, y])
print("\nfaixas na coluna do meio:")
for tipo, y0, y1 in grupos:
    print(f"  {tipo:8s} y {y0:3d}..{y1:3d}")

# onde a base dos botoes dourados esta, e onde os slots comecam
ouro = [g for g in grupos if g[0] == "ouro"]
escuro = [g for g in grupos if g[0] == "escuro"]
if ouro:
    topo_ouro = ouro[0][1]
    base_ouro = ouro[-1][2]
    print(f"\nprimeira faixa dourada: y={topo_ouro}  ultima: y={base_ouro}")
if escuro:
    print(f"faixa escura: y={escuro[0][1]}..{escuro[-1][2]}")

# duas linhas de slots: a grade de 3 colunas x 2 linhas cabe entre o
# topo da area util e a primeira faixa dourada
print("\nfracoes em relacao ao miolo (para o jogo usar):")
if ouro:
    print(f"  area dos slots:  y de {topo / miolo.y if False else 0.0:.2f}")
    print(f"  borda de ouro em y={topo_ouro}  -> "
          f"fracao do miolo = {(topo_ouro - miolo.y) / miolo.height:.3f}")
    print(f"  base do miolo em y={miolo.y + miolo.height}  -> 1.000")
    print(f"  -> area dos slots vai de 0.00 ate "
          f"{(topo_ouro - miolo.y) / miolo.height:.3f}")