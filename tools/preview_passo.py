"""Filme do passo do heroi: uma faixa com os quadros do ciclo.

Nao e um numero de quadros por segundo: e o desenho como o jogador ve,
com o passo, a sombra e a arma. Se o passo nao ler na imagem, nao le na
tela.
"""

import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))

from src import animacao, assets  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

CHAVE = sys.argv[1] if len(sys.argv) > 1 else "punho"
MOVENDO = "--parado" not in sys.argv
ESCALA = 2

arte = assets.equipado_na_tela(CHAVE, ESCALA)
if arte is None:
    raise SystemExit(f"sem desenho para o conjunto {CHAVE}")

# o chao e do tamanho do desenho: e assim que a sombra sai com a
# proporcao certa, e o passo fica com a escala de um passo de verdade
TILE = arte.get_height()
Q = 10  # quadros por linha
linhas = 3
alt = arte.get_height() + 26
larg = arte.get_width()

surf = pygame.Surface((larg * Q, alt * linhas))
surf.fill((28, 24, 22))
f = pygame.font.SysFont("consolas", 13)

passo = animacao.Passo()
n = 0
for linha in range(linhas):
    for i in range(Q):
        n += 1
        x0 = i * larg
        y0 = linha * alt
        centro = (x0 + larg // 2, y0 + alt - 12)
        pygame.draw.line(surf, (52, 45, 40), (x0, y0 + alt - 12),
                         (x0 + larg, y0 + alt - 12))
        animacao.desenhar_heroi(
            surf, arte, passo, centro,
            direcao="leste", movendo=MOVENDO, tile=TILE,
        )
        surf.blit(f.render(f"{n:02d}", True, (210, 190, 150)), (x0 + 3, y0 + 2))
        for _ in range(4):
            passo.advance(1 / 60, MOVENDO)

pygame.image.save(surf, str(RAIZ / f"preview_passo_{CHAVE}.png"))
print(f"preview_passo_{CHAVE}.png  "
      f"({Q * linhas} quadros, "
      f"{'andando' if MOVENDO else 'parado'})")