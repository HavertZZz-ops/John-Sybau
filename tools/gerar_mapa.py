"""Gera o mapa do mundo e escreve em `game/mapas/mundo.txt`.

O mapa em texto dentro do codigo e desconfortavel para editar: alinhar
uma parede a olho e contar caractere ate fechar a linha e trabalho de
robô, e um caractere a mais numa linha derruba o jogo com um erro de
"mapa nao retangular" que nao diz onde.

Gerar o mapa resolve os dois problemas: as salas sao desenhadas como
retangulos, e o retangulo garante que a linha fecha.

    python tools/gerar_mapa.py

O mapa gerado e um arquivo de verdade, versionado, e o jogo o le.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "game"))

PAREDE = "#"
CHAO = "."
ITEM = "i"
INIMIGO = "b"
BAU = "P"
SAIDA = "E"

# O tamanho do mundo. Em tile de 32, 40x13 sao 1280x416 pixels — maior
# que a tela de 800x600 em largura, o que garante que a cameraTENHA o
# que acompanhar. Um mapa menor que a tela faria a camera centralizar e
# apareceria vazio nas bordas.
LARGURA = 40
ALTURA = 13

# As salas do mundo: (coluna, linha, largura, altura, quantos inimigos).
#
# A ordem e a ordem de leitura da tela: o jogador ve a primeira sala
# primeiro, entao e a primeira da lista.
#
# A largura de cada sala e a distanca entre elas mais a parede, e por isso
# que os numeros nao sao independentes: mudar a largura da primeira sala
# move a segunda. Este e o preco de um mapa escrito a mao — e a razao
# de ele ser GERADO e nao escrito.
# As salas do mundo: (coluna, linha, largura, altura, quantos inimigos).
#
# As tres salas de cima sao as que o jogador encontra primeiro; a grande
# de baixo tem a saida. Entre as de cima e a de baixo existe uma PAREDE
# com duas portas — e essa parede e o que faz delas salas separadas.
#
# Uma parede com porta e o que separa salas. Sem ela, as tres de cima
# viram um salao so e o bau do meio cai no corredor, longe das duas.
SALAS = (
    # coluna, linha, largura, altura, inimigos
    (1, 1, 11, 4, 2),    # sala do canto superior esquerdo
    (14, 1, 12, 4, 3),   # sala do canto superior direito
    (1, 6, 38, 6, 4),    # sala grande de baixo, com a saida
)


def construir() -> list[str]:
    """Monta o mapa como lista de linhas."""
    grade = [[PAREDE] * LARGURA for _ in range(ALTURA)]

    def abrir(c0: int, l0: int, largura: int, altura: int) -> None:
        for linha in range(l0, l0 + altura):
            for coluna in range(c0, c0 + largura):
                if 0 <= linha < ALTURA and 0 <= coluna < LARGURA:
                    grade[linha][coluna] = CHAO

    for c0, l0, largura, altura, _ in SALAS:
        abrir(c0, l0, largura, altura)

    # As portas: UM tile de chao dentro da parede, em cada coluna de
    # centro das salas de cima. Uma porta por sala, e nao uma porta
    # geral — porque e a porta que SEPARA as salas. Com uma porta so,
    # as tres salas de cima viram uma regiao so, e o bau do meio cai no
    # corredor.
    #
    # A posicao vem do CENTRO da sala, e nao e escrita a mao: mudar o
    # tamanho de uma sala move a porta junto, e a porta nunca acaba
    # apontando para uma parede por onde nao se passa.
    for c0, l0, largura, _altura, _inimigos in SALAS[:-1]:
        coluna = c0 + largura // 2
        linha = l0 + _altura  # a primeira linha depois da sala
        if 0 <= linha < ALTURA and 0 <= coluna < LARGURA:
            grade[linha][coluna] = CHAO

# O bau no centro de cada sala. O centro de um retangulo de chao e
    # sempre chao, entao o bau nunca cai dentro da parede - o que
    # aconteceria se a posicao fosse escrita a mao e a sala encolhesse.
    #
    # O bau e a ANCORA da busca de salas do jogo (ver `mundo.py`): o
    # jogo acha a sala andando a partir do bau ate bater na parede. Por
    # isso o bau tem de estar DENTRO da sala e nunca num corredor, e
    # por isso a geracao coloca um bau em CADA sala — sem ele, a busca
    # so acha a primeira e as outras salas ficam sem bau.
    for c0, l0, largura, altura, _ in SALAS:
        grade[l0 + altura // 2][c0 + largura // 2] = BAU

    # O bau da SALA DE BAIXO fica deslocado para a esquerda do centro.
    #
    # Com os tres baus no centro geometrico, o do meio cai exatamente
    # sobre a PORTA entre as duas salas de cima. A porta e chao como
    # qualquer outro, entao a busca do jogo andava da sala da esquerda,
    # passava pela porta e chegava na da direita: as tres salas viravam
    # uma, e aparecia um bau so no mundo inteiro.
    #
    # Deslocar o bau de baixo tira ele do caminho. O bau nao precisa
    # ficar no centro exato — precisa estar dentro da sala e
    # alcancavel, que e o que o deslocamento mantem.
    # (a tupla e desempacotada aqui porque `SALAS[-1]` e a sala de baixo,
    # e o bau precisa da largura e da altura dela)
    c0, l0, largura, altura, quantos = SALAS[-1]
    grade[l0 + altura // 2][c0 + largura // 4] = BAU

    # Os inimigos, espalhados dentro da sala e longe do bau e da
    # entrada. "Espalhado" semeia de verdade: uma posicao fixa por
    # sala deixa o inimigo sempre na mesma parede, e o jogador decora o
    # mapa em vez de jogar.
    semente = 12345

    def seguinte() -> int:
        nonlocal semente
        semente = (semente * 1103515245 + 12345) & 0x7FFFFFFF
        return semente

    for c0, l0, largura, altura, quantidade in SALAS:
        colocados = 0
        tentativas = 0
        while colocados < quantidade and tentativas < 200:
            tentativas += 1
            coluna = c0 + 1 + seguinte() % max(1, largura - 2)
            linha = l0 + 1 + seguinte() % max(1, altura - 2)
            if grade[linha][coluna] == CHAO:
                grade[linha][coluna] = INIMIGO
                colocados += 1

    # Os itens, tambem espalhados.
    for _ in range(4):
        for _tentativa in range(100):
            coluna = 1 + seguinte() % (LARGURA - 2)
            linha = 1 + seguinte() % (ALTURA - 2)
            if grade[linha][coluna] == CHAO:
                grade[linha][coluna] = ITEM
                break

    # A saida, no meio da parede de baixo da ultima sala.
    c0, l0, largura, altura, _ = SALAS[-1]
    grade[l0 + altura // 2][c0 + largura // 2] = SAIDA

    return ["".join(linha) for linha in grade]


def main() -> int:
    linhas = construir()

    # A verificacao que o jogo faz, feita aqui antes de gravar: um mapa
    # nao retangular so quebra quando o jogo ja esta rodando.
    largura = len(linhas[0])
    for numero, linha in enumerate(linhas, start=1):
        if len(linha) != largura:
            print(f"ERRO: a linha {numero} tem {len(linha)}, "
                  f"e a primeira tem {largura}")
            return 1

    pasta = RAIZ / "game" / "mapas"
    pasta.mkdir(exist_ok=True)
    destino = pasta / "mundo.txt"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    # As salas vao num arquivo do lado, e NAO sao descobertas pelo jogo.
    #
    # Descobrir.andando pelo mapa nao funciona: as salas se ligam por
    # portas de um tile, e um tile de porta e indistinguivel de um tile
    # de chao. Qualquer busca por "chao ligado" atravessa a porta e
    # encontra uma regiao so — e foi exatamente o que aconteceu: um
    # mapa com tres salas aparecia com uma so.
    #
    # A solucao e o gerador, que JA sabe onde as salas sao, escrever
    # essa informacao. O jogo le, e nao deduz. Um arquivo que o
    # proprio gerador produz e que o jogo consome e um contrato; um
    # algoritmo que tenta adivinhar a partir da arte e um palpite.
    salas_texto = "\n".join(
        f"{c0} {l0} {largura} {altura} {inimigos}"
        for c0, l0, largura, altura, inimigos in SALAS
    )
    (pasta / "salas.txt").write_text(salas_texto + "\n", encoding="utf-8")

    print(f"mapa escrito em {destino}")
    print(f"salas escritas em {pasta / 'salas.txt'}")
    print(f"  {largura} x {len(linhas)} tiles")
    print(f"  salas: {len(SALAS)}")
    print()
    for linha in linhas:
        print(f"  {linha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
