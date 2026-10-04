"""Testes do movimento e da colisao.

Rodar sem pygame e sem janela: e possivel porque nada aqui depende de
desenho, so de matematica de caixa. E por isso que estes testes sao
confiaveis — eles nao medem tempo, medem posicao, e posicao tem valor
exato.

    python tools/testar_player.py

Cada teste verifica uma regra do modulo `player`. Os casos nao sao
escolhidos ao acaso: cada um deles e um defeito que ja aconteceu em jogo
2D, e o comentario diz qual.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((64, 64))  # o pygame exige um display antes de Rect

import player as P  # noqa: E402

FALHAS: list[str] = []


def checar(descricao: str, condicao: bool, detalhe: str = "") -> None:
    """Registra o resultado de uma verificacao."""
    if condicao:
        print(f"  [ok]   {descricao}")
    else:
        print(f"  [FALHA] {descricao} {detalhe}")
        FALHAS.append(descricao)


MAPA_BASICO = """
    ####################
    #..................#
    #..................#
    #..................#
    #..................#
    #..................#
    #..................#
    #..................#
    ####################
"""


def main() -> int:
    print("=" * 62)
    print("testes de movimento e colisao")

    # --- o mapa ------------------------------------------------------
    print("\nMapa")
    mapa = P.Mapa.de_texto(MAPA_BASICO)
    # O esperado vem do proprio literal, e nao de um numero escrito a mao.
    # Escrever `altura == 8` aqui seria um segundo lugar para errar: se o
    # mapa acima mudar de tamanho, o teste passa a reprovar por um numero
    # que ninguem atualizou — e o operador vai culpar o codigo, que esta
    # certo.
    linhas_do_texto = [linha for linha in MAPA_BASICO.splitlines()
                       if linha.strip()]
    esperado_largura = len(linhas_do_texto[0].strip())
    esperado_altura = len(linhas_do_texto)

    checar("le a largura", mapa.largura == esperado_largura,
           f"({mapa.largura}, esperado {esperado_largura})")
    checar("le a altura", mapa.altura == esperado_altura,
           f"({mapa.altura}, esperado {esperado_altura})")
    checar("parede nao e andavel", not mapa.andavel(0, 0))
    checar("chao e andavel", mapa.andavel(1, 1))
    checar("fora do mapa e parede", mapa.em(-1, 0) == P.Mapa.PAREDE)
    checar("fora do mapa e parede (baixo)", mapa.em(0, 999) == P.Mapa.PAREDE)

    # Mapa retangular: linhas de tamanhos diferentes tem de ser recusado
    try:
        P.Mapa(["####", "#..", "#...."])
        checar("recusa mapa nao retangular", False, "aceitou")
    except ValueError:
        checar("recusa mapa nao retangular", True)

    # --- a caixa dos pes ----------------------------------------------
    print("\nCaixa dos pes")
    j = P.Jogador(1, 1)
    caixa = j.caixa_no_mundo
    checar("caixa menor que um tile", caixa.width < 32 and caixa.height < 32,
           f"({caixa.width}x{caixa.height})")
    checar("caixa ancorada no chao", caixa.bottom == int(j.posicao.y))
    checar("caixa dentro do chao andavel", P.caixa_livre(caixa, mapa))

    # --- colisao -----------------------------------------------------
    print("\nColisao")
    parede = pygame.Rect(0, 0, 32, 32)
    checar("parede nao passa", not P.caixa_livre(parede, mapa))

    # Uma caixa maior que um tile toca quatro celulas. Se o teste olhasse
    # so o canto, esta caixa passaria pela parede do canto.
    grande = pygame.Rect(0, 0, 60, 60)
    checar("caixa grande e barrada", not P.caixa_livre(grande, mapa))

    # --- mover -------------------------------------------------------
    print("\nMover")

    # Direita: anda
    j = P.Jogador(1, 1)
    inicio = j.posicao.copy()
    j.posicao = P.mover(j.posicao, pygame.Vector2(150, 0), 1 / 60, mapa, j.caixa_no_mundo)
    checar("anda para a direita", j.posicao.x > inicio.x,
           f"({inicio.x:.0f} -> {j.posicao.x:.0f})")

    # Direita ate a parede: para, e nao atravessa
    j = P.Jogador(18, 1)
    for _ in range(300):
        j.posicao = P.mover(
            j.posicao, pygame.Vector2(150, 0), 1 / 60, mapa, j.caixa_no_mundo
        )
    checar("para na parede da direita", j.posicao.x < 20 * 32,
           f"({j.posicao.x:.0f}, parede em 640)")

    # Cima ate a parede: para
    j = P.Jogador(1, 7)
    for _ in range(300):
        j.posicao = P.mover(
            j.posicao, pygame.Vector2(0, -150), 1 / 60, mapa, j.caixa_no_mundo
        )
    checar("para na parede de cima", j.posicao.y > 0,
           f"({j.posicao.y:.0f})")

    # --- o defeito do eixo unico (o mais importante) ------------------
    print("\nEscorregar na parede (o defeito do eixo unico)")

    # Empurra na diagonal contra o canto superior direito. Com colisao de
    # eixo unico o heroi PARARIA; com eixo separado ele sobe.
    j = P.Jogador(18, 2)
    diagonal = pygame.Vector2(150, -150).normalize() * 150
    antes_y = j.posicao.y
    for _ in range(60):
        j.posicao = P.mover(
            j.posicao, diagonal, 1 / 60, mapa, j.caixa_no_mundo
        )
    checar("sobe renteando a parede", j.posicao.y < antes_y,
           f"(y {antes_y:.0f} -> {j.posicao.y:.0f})")

    # --- velocidade ---------------------------------------------------
    print("\nVelocidade")
    teclas = pygame.key.get_pressed()
    j = P.Jogador(1, 1)
    v = j.velocidade_desejada(teclas)
    checar("parado nao anda", v.length() == 0, f"({v.length():.1f})")

    # Normalizacao da diagonal: a magnitude nao pode passar de 1.
    mag = pygame.Vector2(1, 1).normalize().length()
    checar("diagonal normalizada", abs(mag - 1.0) < 0.001, f"({mag})")

    # --- inventario ---------------------------------------------------
    print("\nInventario")
    j = P.Jogador()
    checar("comeca vazio", j.inventario == [])
    checar("pega", j.pegar("espada"))
    chegar = sum(j.pegar(f"item{i}") for i in range(50))
    checar("respeita o limite", len(j.inventario) == 10,
           f"({len(j.inventario)} itens, {chegar} recusados)")
    checar("larga", j.largar("espada"))
    checar("nao larga o que nao tem", not j.largar("nao-existe"))

    # --- resumo -------------------------------------------------------
    print("=" * 62)
    if FALHAS:
        print(f"{len(FALHAS)} verificacao(oes) falharam:")
        for f in FALHAS:
            print(f"  - {f}")
        return 1

    print("tudo certo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())