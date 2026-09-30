"""Gera uma copia anotada do tileset, com a grade visivel.

Sem indice visual nao da para escolher tile por coordenada no olho.
Salva em assets/tiles/_anotado.png (ignorado pelo git).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame

pygame.init()

src = pygame.image.load(ROOT / "assets" / "tiles" / "dungeon_tileset.png")
T = 16
cols = src.get_width() // T
rows = src.get_height() // T

zoom = 4
big = pygame.transform.scale(
    src, (src.get_width() * zoom, src.get_height() * zoom)
)
canvas = pygame.Surface(big.get_size(), pygame.SRCALPHA)

# fundo claro para o alpha do tileset aparecer
fundo = pygame.Surface(big.get_size())
fundo.fill((60, 60, 72))
canvas.blit(fundo, (0, 0))
canvas.blit(big, (0, 0))

fonte = pygame.font.SysFont("consolas", 11)
for y in range(rows):
    for x in range(cols):
        pygame.draw.rect(
            canvas, (255, 80, 80, 220),
            pygame.Rect(x * T * zoom, y * T * zoom, T * zoom, T * zoom),
            1,
        )
        rot = fonte.render(f"{x},{y}", True, (255, 255, 0))
        canvas.blit(rot, (x * T * zoom + 2, y * T * zoom + 1))

out = ROOT / "assets" / "tiles" / "_anotado.png"
pygame.image.save(canvas, out)
print("grade %dx%d de %dpx" % (cols, rows, T))
print("salvo:", out)
pygame.quit()