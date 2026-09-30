"""Testes da autotilagem de Wang e do registro de cenarios.

A autotilagem escolhe o tile pelos quatro VERTICES que a celula toca.
Um canto trocado de lugar nao da erro nenhum: o jogo continua rodando,
a borda simplesmente fecha do lado errado. Por isso os casos aqui sao
sobre a ESCOLHA do tile, e nao sobre se a tela desenhou.
"""
from __future__ import annotations

import pathlib
import sys

import pygame

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import cenarios, settings, wang  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))

FALHOU = 0


def checa(condicao: bool, mensagem: str) -> None:
    global FALHOU
    if condicao:
        print(f"[ok] {mensagem}")
    else:
        FALHOU += 1
        print(f"[FALHOU] {mensagem}")


def parede(c) -> bool:
    return c == "#"


# --- os tilesets de verdade, para o teste pegar arte faltando -------
for cenario in cenarios.CENARIOS:
    png = settings.TILES_DIR / cenario.png
    meta = settings.TILES_DIR / cenario.json
    tem_ambos = png.is_file() and meta.is_file()
    checa(tem_ambos, f"{cenario.nome}: tileset presente ({cenario.png})")
    if not tem_ambos:
        continue

    tabela, lado = wang.carregar_tileset_wang(png, meta)
    checa(len(tabela) == 16,
          f"{cenario.nome}: 16 tiles, veio {len(tabela)}")
    chaves_esperadas = {
        tuple((n >> b) & 1 == 1 for b in range(4)) for n in range(16)
    }
    # as 16 combinacoes de canto existem, em qualquer rotacao
    cobertura = {
        (a, b, c, d)
        for a in (False, True) for b in (False, True)
        for c in (False, True) for d in (False, True)
    }
    checa(set(tabela) == cobertura,
          f"{cenario.nome}: as 16 combinacoes de canto estao presentes")

    # --- a escolha do tile depende dos vertices, nao do miolo -------
    # Um vertice conta como parede quando QUALQUER das celulas em volta
    # dele e parede. Uma celula andavel cercada de parede e um poco:
    # os quatro vertices tocam parede.
    celulas = [
        ["#", "#", "#"],
        ["#", ".", "#"],
        ["#", "#", "#"],
    ]
    g = wang.GradeWang(celulas, parede=parede, tabela=tabela)
    isolada = g.tile_e_chave(1, 1)[0]
    checa(isolada == (True, True, True, True),
          f"celula cercada de parede e um poco, veio {isolada}")

    # Agora o caso que distingue os cantos: uma unica parede no canto
    # superior esquerdo de um chao aberto. So o vertice NO daquela
    # celula toca parede. Se NW e NE trocassem de lugar na tabela, este
    # teste passaria errado e a borda fecharia virada.
    canto = [["." for _ in range(3)] for _ in range(3)]
    canto[0][0] = "#"
    g_canto = wang.GradeWang(canto, parede=parede, tabela=tabela)
    so_no = g_canto.tile_e_chave(1, 1)[0]
    checa(so_no == (True, False, False, False),
          f"parede no canto NO marca so o canto NO, veio {so_no}")

    canto_esp = [list(reversed(linha)) for linha in canto]
    g_esp = wang.GradeWang(canto_esp, parede=parede, tabela=tabela)
    so_ne = g_esp.tile_e_chave(1, 1)[0]
    checa(so_ne == (False, True, False, False),
          f"espelhado: parede no canto NE marca so o NE, veio {so_ne}")
    checa(so_no != so_ne,
          "os cantos nao sao genericos: espelhar muda a chave")

    # 5x5 todo aberto: o miolo e o unico com os 4 vertices livres
    abertas = [["." for _ in range(5)] for _ in range(5)]
    g2 = wang.GradeWang(abertas, parede=parede, tabela=tabela)
    meio = g2.tile_e_chave(2, 2)[0]
    checa(meio == (False, False, False, False),
          f"miolo de sala aberta e o chao puro, veio {meio}")

    # a borda tem de dar um canto de parede, senao a borda nao fecha
    borda = g2.tile_e_chave(2, 0)[0]
    checa(any(borda), f"borda superior tem canto de parede, veio {borda}")
    quina = g2.tile_e_chave(0, 0)[0]
    checa(sum(quina) >= 2, f"quina tem 2 ou mais cantos de parede, veio {quina}")

    # fora do mapa e parede: o mapa nao pode ter borda vazia
    fora = g2._vertice_parede(99, 99)
    checa(fora is True, "vertice fora do mapa conta como parede")

    # a mesma celula devolve sempre a mesma chave
    a = g2.tile_e_chave(1, 1)
    b = g2.tile_e_chave(1, 1)
    checa(a[0] == b[0], "a escolha do tile e estavel entre chamadas")

    # a memoria devolve a MESMA imagem, para o cache do desenho valer
    g3 = wang.GradeWang(abertas, parede=parede, tabela=tabela)
    checa(
        g3.tile(2, 2) is tabela[(False, False, False, False)],
        "a celula devolve a imagem da propria chave",
    )


# --- o registro de cenarios -----------------------------------------
checa(len(cenarios.CENARIOS) >= 2, "ha pelo menos dois cenarios")
nomes = [c.nome for c in cenarios.CENARIOS]
checa(len(nomes) == len(set(nomes)), "os nomes dos cenarios sao unicos")
tilesets = [c.tileset for c in cenarios.CENARIOS]
checa(len(tilesets) == len(set(tilesets)), "cada cenario tem seu tileset")

primeiro = cenarios.CENARIOS[0]
checa(cenarios.primeiro() is primeiro, "primeiro() devolve o primeiro cenario")
checa(cenarios.seguinte(primeiro.nome) is cenarios.CENARIOS[1],
      "a saida do primeiro leva ao segundo")
checa(cenarios.seguinte(cenarios.CENARIOS[-1].nome) is primeiro,
      "a saida do ultimo fecha o ciclo no primeiro")
checa(cenarios.seguinte("cenario que nao existe") is primeiro,
      "cenario desconhecido devolve o primeiro")

# as sementes precisam ser diferentes, senao os cenarios sao o mesmo
# mapa com outro tileset
sementes = [c.semente for c in cenarios.CENARIOS]
checa(len(sementes) == len(set(sementes)),
      "cada cenario sorteia um mapa diferente")

# o cenario de partida e o unico que comeca no caixao
com_caixao = [c for c in cenarios.CENARIOS if c.tem_caixao]
checa(len(com_caixao) == 1,
      "exatamente um cenario comeca no caixao")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) de Wang falharam")
    sys.exit(1)
print("\nwang: tudo certo")
