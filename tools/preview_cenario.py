"""Desenha uma sala de teste com autotiling de Wang.

Serve para olhar a arte antes de plugar no jogo: mostra o tileset com
as bordas montadas, para dar pra ver se o padrao fecha.
"""
import pathlib
import sys

import pygame

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import cenarios, wang

pygame.init()
pygame.display.set_mode((8, 8))

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TILES = RAIZ / "assets" / "tiles"

# exercita quina, borda reta, ponta e interior
LINHAS = [
    "##########",
    "#........#",
    "#..##....#",
    "#..##....#",
    "#........#",
    "#...##...#",
    "#...##...#",
    "#........#",
    "##########",
]


def montar(prefixo: str, escala: int) -> pygame.Surface:
    tabela, lado = wang.carregar_tileset_wang(
        TILES / f"{prefixo}.png", TILES / f"{prefixo}.json"
    )
    grade = wang.GradeWang([list(l) for l in LINHAS], tabela=tabela)
    larg = len(LINHAS[0]) * lado * escala
    alt = len(LINHAS) * lado * escala
    img = pygame.Surface((larg, alt))
    img.fill((18, 20, 24))
    alvo = (lado * escala, lado * escala)
    for y, linha in enumerate(LINHAS):
        for x, c in enumerate(linha):
            if c == "#":
                continue
            img.blit(
                pygame.transform.scale(grade.tile(x, y), alvo),
                (x * lado * escala, y * lado * escala),
            )
    return img


for c in cenarios.CENARIOS:
    img = montar(c.tileset, 1)
    saida = RAIZ / f"preview_cenario_{c.tileset}.png"
    pygame.image.save(img, saida)
    print(f"{saida.name}  {img.get_width()}x{img.get_height()}  tile de 1x")