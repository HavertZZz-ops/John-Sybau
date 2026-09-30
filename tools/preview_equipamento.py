"""Mostra as armas e os conjuntos do heroi lado a lado."""
import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))

pygame.init()
pygame.display.set_mode((8, 8))

ESC = 3
ARMAS = ["espada", "maca", "escudo"]
HEROES = ["espada", "maca", "escudo", "espada_escudo", "maca_escudo"]

celula = 64 * ESC
linhas = len(ARMAS) + len(HEROES)
img = pygame.Surface((64 * ESC * 3, linhas * celula + 30))
img.fill((26, 27, 31))

fonte = pygame.font.Font(None, 22)


def linha(rotulo, caminhos, y):
    for x, caminho in enumerate(caminhos):
        if caminho is None:
            continue
        p = pathlib.Path(caminho)
        if not p.is_file():
            continue
        s = pygame.image.load(str(p)).convert_alpha()
        img.blit(pygame.transform.scale(s, (celula, celula)),
                 (x * celula, y))
    t = fonte.render(rotulo, True, (220, 200, 140))
    img.blit(t, (6, y + 4))


a = RAIZ / "assets" / "sprites" / "armas"
h = RAIZ / "assets" / "sprites" / "heroi_equipado"
linha("ARMAS", [a / f"{n}.png" for n in ARMAS], 20)
linha("HEROI", [h / f"{n}.png" for n in HEROES[:3]], 20 + celula)
linha("HEROI", [h / f"{n}.png" for n in HEROES[3:]] + [None], 20 + celula * 2)

pygame.image.save(img, str(RAIZ / "preview_equipamento.png"))
print("preview_equipamento.png", img.get_size())
print("linhas: ARMAS, HEROI (espada/maca/escudo), HEROI (combinacoes)")