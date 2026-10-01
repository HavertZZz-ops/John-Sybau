"""Mostra os quadros de ANDAR de cada direcao, lado a lado.

A folha de idle esta certa. O que o jogador ve andando vem de outra
imagem da folha, e e a que precisa ser conferida.
"""
import pathlib
import sys

import pygame

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import assets  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))

DIRS = ("sul", "norte", "leste", "oeste")
ESTADO = sys.argv[1] if len(sys.argv) > 1 else "walk"

ESC = 4
fonte = pygame.font.Font(None, 22)
cel = assets.HERO_BASE[0] * ESC
alt = assets.HERO_BASE[1] * ESC
n = max(len(assets.carregar_animacao(d, ESTADO, scale=ESC)) for d in DIRS)

img = pygame.Surface((n * cel + 70, len(DIRS) * (alt + 30)))
img.fill((26, 27, 31))

for linha, d in enumerate(DIRS):
    y = linha * (alt + 30)
    rotulo = fonte.render(d, True, (240, 200, 120))
    img.blit(rotulo, (4, y + alt // 2))
    for col, quad in enumerate(assets.carregar_animacao(d, ESTADO, scale=ESC)):
        img.blit(quad, (70 + col * cel, y))
        pygame.draw.rect(img, (80, 80, 100),
                         (70 + col * cel, y, cel, alt), 1)

pygame.image.save(img, str(RAIZ / f"preview_{ESTADO}_dirs.png"))
print(f"preview_{ESTADO}_dirs.png {img.get_size()}")
print(f"estado={ESTADO}  linhas: {', '.join(DIRS)}")
print("Lendo: SUL tem rosto. NORTE tem nuca. LESTE tem nariz para a")
print("direita da tela. OESTE tem nariz para a esquerda.")