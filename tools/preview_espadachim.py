import pathlib
import sys

import pygame

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import assets

pygame.init()
pygame.display.set_mode((8, 8))

ESC = 4
BASE = assets.HERO_BASE
estados = ["idle", "walk", "attack", "hit", "death"]
caixa = (BASE[0] * 6, BASE[1] * 6)

quadros_por_estado = {
    e: assets.carregar_animacao("sul", e, box=caixa, scale=ESC) for e in estados
}
colunas = max(len(q) for q in quadros_por_estado.values())
largura = colunas * caixa[0]
altura = len(estados) * caixa[1]
folha = pygame.Surface((largura, altura))
folha.fill((30, 30, 34))

y = 0
for estado in estados:
    x = 0
    for q in quadros_por_estado[estado]:
        folha.blit(q, (x, y))
        pygame.draw.rect(folha, (75, 75, 85), (x, y, q.get_width(), q.get_height()), 1)
        x += caixa[0]
    y += caixa[1]

pygame.image.save(folha, "preview_espadachim.png")
print(f"preview_espadachim.png {largura}x{altura} base={BASE} escala={ESC}")
for e in estados:
    print(f"  {e}: {len(quadros_por_estado[e])} quadros")
print("linhas de cima para baixo:", ", ".join(estados))