import pathlib
import sys

import pygame

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import coffin

pygame.init()

ESC = 4
ABERTOS = [0.0, 0.25, 0.5, 0.75, 1.0]
w, h = coffin.COFFIN_W * ESC, coffin.COFFIN_H * ESC
folha = pygame.Surface((w * len(ABERTOS) + 20, h + 30))
folha.fill((24, 25, 30))

x = 10
for progresso in ABERTOS:
    pygame.draw.rect(
        folha, (44, 46, 54), pygame.Rect(x - 4, 10, w + 8, h), 1
    )
    coffin.draw_coffin(folha, (x + w // 2, 10 + h // 2), progresso, ESC)
    coffin.draw_lid(folha, (x + w // 2, 10 + h // 2 - coffin.COFFIN_H * ESC // 4),
                    progresso, ESC)
    pygame.draw.line(folha, (200, 170, 90), (x, h + 18), (x + w, h + 18), 1)
    x += w + 10

pygame.image.save(folha, "preview_caixao.png")
print(f"preview_caixao.png {folha.get_width()}x{folha.get_height()} escala={ESC}")
print("colunas da esquerda para a direita: tampa em",
      ", ".join(f"{int(p * 100)}%" for p in ABERTOS), "de abertura")