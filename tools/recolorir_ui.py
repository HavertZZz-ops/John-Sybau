"""Reescreve as folhas de UI do CraftPix na paleta do jogo.

O pacote e exatamente a estrutura que o jogo precisa: painel com
grade, botoes BUY, contador de ouro, icones de espada e escudo. Mas a
paleta e de RPG mobile: verde vivo no cabecalho, creme no papel,
icones saturados. Colado num jogo que e pedra cinza e dourado escuro,
fica com a cara de dois jogos na mesma tela.

A PRIMEIRA versao deste conversor mapeava cor por matiz e o resultado
saiu embolado: o cabecalho e o painel viraram o mesmo marrom e o
jogador nao sabia onde era o botao. Isso e o que acontece quando se
troca a matiz sem respeitar o valor.

Aqui a regra e por FAIXA DE LUMINANCIA, que e o que carrega a
estrutura de uma folha de pixel art: moldura clara, miolo escuro,
botao no meio. O matiz so entra para marcar os acentos de ouro.
"""
from __future__ import annotations

import pathlib
import sys

import pygame

# --- a paleta do jogo, em nomes --------------------------------------
FUNDO = (12, 11, 10)        # theme.BACKGROUND
MOLDURA = (58, 55, 50)      # a borda do painel
MOLDURA_CLARA = (92, 87, 79)
MOLHO = (30, 29, 27)        # o miolo do painel, o "papel"
SLOT = (44, 42, 38)         # o quadrado de cada item
OURO = (198, 168, 102)
OURO_FRACO = (146, 122, 74)
TEXTO = (176, 168, 156)


def lum(c: tuple[int, int, int]) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def sat(c: tuple[int, int, int]) -> float:
    mx, mn = max(c), min(c)
    return 0.0 if mx == 0 else (mx - mn) / mx


def misto(a: tuple[int, int, int], b: tuple[int, int, int], t: float
          ) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


# as faixas, do mais claro para o mais escuro. Os limites foram
# olhando as folhas, nao chutados: na folha do Inventory o papel creme
# fica entre 205 e 235, os slots entre 175 e 200, e a moldura entre
# 120 e 170.
FAIXAS = (
    (205, 255, MOLHO),        # miolo do painel
    (170, 205, SLOT),         # cada quadrado de item
    (120, 170, MOLDURA),      # a moldura
    (60, 120, MOLDURA),       # borda externa e detalhes
    (0, 60, FUNDO),
)


def converte(c: tuple[int, int, int]) -> tuple[int, int, int]:
    v = lum(c)
    s = sat(c)

    for baixo, alto, cor in FAIXAS:
        if baixo <= v < alto:
            t = (v - baixo) / max(1.0, alto - baixo)
            saida = misto(cor, _clarear(cor), t * 0.35)
            break
    else:
        saida = MOLHO

    # acentos: onde o original era verde ou dourado, o jogo usa ouro.
    # O verde saturado do cabecalho e do botao cai aqui.
    if c[1] > c[0] + 20 and c[1] > c[2] + 10 and s > 0.22:
        if v > 140:
            saida = OURO
        else:
            saida = OURO_FRACO
    return saida


def _clarear(cor: tuple[int, int, int]) -> tuple[int, int, int]:
    return misto(cor, MOLDURA_CLARA, 0.6)


def converter(img: pygame.Surface) -> pygame.Surface:
    saida = img.copy()
    w, h = saida.get_size()
    saida.fill((0, 0, 0, 0))
    for y in range(h):
        for x in range(w):
            r, g, b, a = img.get_at((x, y))
            if a == 0:
                continue
            saida.set_at((x, y), converte((r, g, b)) + (a,))
    return saida


def main() -> int:
    STAGE = pathlib.Path(
        r"C:\Users\jhnnl\AppData\Local\Temp\opencode\pacotes"
    )
    UI = STAGE / "craftpix-net-255216-free-basic-pixel-art-ui-for-rpg" / "PNG"
    SAIDA = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

    pygame.init()
    pygame.display.set_mode((8, 8))

    # a folha da loja e a que mais mostra o problema
    alvos = ["Shop", "Inventory", "Equipment"]
    ESC = 2
    fonte = pygame.font.Font(None, 20)
    img = pygame.image.load(str(UI / "Shop.png")).convert_alpha()
    conv = converter(img)
    w, h = img.get_size()
    tela = pygame.Surface((w * ESC * 2 + 24, h * ESC + 26))
    tela.fill((14, 14, 16))
    tela.blit(pygame.transform.scale(img, (w * ESC, h * ESC)), (4, 24))
    tela.blit(pygame.transform.scale(conv, (w * ESC, h * ESC)),
              (w * ESC + 16, 24))
    tela.blit(fonte.render("ORIGINAL", True, (230, 230, 230)), (4, 4))
    tela.blit(fonte.render("PALETA DO JOGO", True, (230, 200, 140)),
              (w * ESC + 16, 4))
    pygame.image.save(tela, str(SAIDA / "preview_ui_recolorida.png"))
    print("preview_ui_recolorida.png", tela.get_size())
    return 0


if __name__ == "__main__":
    sys.exit(main())