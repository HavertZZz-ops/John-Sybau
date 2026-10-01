"""Mostra as 4 LINHAS CRUAS da folha do espadachim, com o numero da linha.

Carregar por nome de direcao nao adianta: os arquivos ja foram
gravados com a ordem que o codigo assumiu, entao o preview mostraria a
mesma imagem quatro vezes se o erro for uma rotacao. Aqui os arquivos
sao lidos pelo nome CRU, e a coluna e a posicao na folha.
"""
import pathlib
import sys

import pygame

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import assets  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))

# qual arquivo foi gravado a partir de cada LINHA da folha
LINHAS = ("sul", "oeste", "norte", "leste")

ESC = 5
fonte = pygame.font.Font(None, 24)
cel = assets.HERO_BASE[0] * ESC
alt = assets.HERO_BASE[1] * ESC
img = pygame.Surface((len(LINHAS) * cel, alt + 30))
img.fill((26, 27, 31))

for i, nome in enumerate(LINHAS):
    caminho = assets.HERO_DIR / f"hero_{nome}_idle_0.png"
    if not caminho.is_file():
        print(f"ausente: {caminho.name}")
        continue
    s = pygame.transform.scale(
        pygame.image.load(str(caminho)).convert_alpha(), (cel, alt)
    )
    img.blit(s, (i * cel, 24))
    pygame.draw.rect(img, (90, 90, 110), (i * cel, 24, cel, alt), 1)
    rotulo = fonte.render(f"linha {i} -> {nome}", True, (240, 200, 120))
    img.blit(rotulo, (i * cel + 2, 4))

pygame.image.save(img, str(RAIZ / "preview_direcoes.png"))
print("preview_direcoes.png", img.get_size())
print()
print("Como ler sem ambiguidade:")
print("  SUL    = rosto de frente, dois olhos visiveis")
print("  NORTE  = nuca, we see the back of the head, nenhum olho")
print("  LESTE  = perfil com o NARIZ apontando para a DIREITA da tela")
print("  OESTE  = perfil com o NARIZ apontando para a ESQUERDA")