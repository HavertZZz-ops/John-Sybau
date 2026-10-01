"""Mostra as folhas de UI ampliadas, com a grade por cima.

As folhas do CraftPix vem com varios paineis colados. Sem saber onde
comeca e onde acaba cada um, qualquer corte e chute. Este script mostra
a folha com uma grade de 16px para medir em vez de adivinhar.
"""
import pathlib
import sys

import pygame

STAGE = pathlib.Path(
    r"C:\Users\jhnnl\AppData\Local\Temp\opencode\pacotes"
)
UI = STAGE / "craftpix-net-255216-free-basic-pixel-art-ui-for-rpg" / "PNG"
SAIDA = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

pygame.init()
pygame.display.set_mode((8, 8))

NOMES = sys.argv[1:] or ["Inventory", "Shop", "Equipment", "Action_panel"]

for nome in NOMES:
    caminho = UI / f"{nome}.png"
    if not caminho.is_file():
        print(f"{nome}: ausente")
        continue
    img = pygame.image.load(str(caminho)).convert_alpha()
    ESC = 3
    w, h = img.get_size()
    tela = pygame.Surface((w * ESC, h * ESC + 18))
    tela.fill((48, 48, 56))
    tela.blit(pygame.transform.scale(img, (w * ESC, h * ESC)), (0, 18))

    fonte = pygame.font.Font(None, 15)
    for gx in range(0, w + 1, 16):
        pygame.draw.line(tela, (90, 90, 110),
                         (gx * ESC, 18), (gx * ESC, 18 + h * ESC))
    for gy in range(0, h + 1, 16):
        pygame.draw.line(tela, (90, 90, 110),
                         (0, 18 + gy * ESC), (w * ESC, 18 + gy * ESC))
    t = fonte.render(f"{nome}  {w}x{h}", True, (255, 230, 150))
    tela.blit(t, (2, 2))

    saida = SAIDA / f"preview_ui_{nome}.png"
    pygame.image.save(tela, str(saida))
    print(f"{saida.name}  folha {w}x{h}  (grade de 16px)")