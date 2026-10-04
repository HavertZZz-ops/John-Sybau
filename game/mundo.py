"""O mundo: onde ficam as salas, os baus e os inimigos.

O arquivo `mapas/mundo.txt` e o desenho. O arquivo `mapas/salas.txt` e
a LISTA de salas, e os dois sao produzidos por `tools/gerar_mapa.py`, que
ja sabe onde cada sala esta porque as desenhou.

Por que a lista e um arquivo e nao uma busca no mapa:

**Um tile de porta e indistinguivel de um tile de chao.** As salas se
ligam por portas de um tile, entao qualquer busca por "chao ligado"
atravessa a porta e encontra uma regiao so. Foi o que aconteceu: um mapa
com tres salas aparecia com uma, e o bau do meio caia em cima da porta.
Tentar adivinhar a sala a partir da arte e um palpite; o gerador sabe a
resposta, e por isso ele a escreve.

**Um arquivo que o gerador produz e o jogo consome e um contrato.** O
gerador muda a sala e o arquivo muda junto, sem ninguem lembrar de
atualizar nada. Um algoritmo que deduz a sala nao tem essa garantia.
"""
from __future__ import annotations

from pathlib import Path

import combat as C
from player import Mapa

# O tile de bau no mapa, e o sprite que o desenha.
BAU = "P"
BAU_FECHADO = "cenario/bau_fechado"
BAU_ABERTO = "cenario/bau_aberto"


def caminho_dos_mapas() -> Path:
    return Path(__file__).parent / "mapas"


def carregar_salas(mapa: Mapa) -> list[tuple[int, int, int, int, int]]:
    """Le as salas do arquivo. Vazio se o arquivo nao existir.

    Cada linha e `coluna linha largura altura inimigos`.

    O arquivo ausente devolve lista vazia em vez de erro: um mundo sem
    salas declarada ainda da para andar, so nao tem bau. Um jogo que nao
    abre por causa de um arquivo de dados e pior do que um jogo sem
    bau — o jogador ainda anda, e a falha aparece como "nao achei bau",
    que e um sintoma compreensivel, e nao um traceback na partida.
    """
    caminho = caminho_dos_mapas() / "salas.txt"
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError:
        return []

    salas: list[tuple[int, int, int, int, int]] = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        partes = linha.split()
        if len(partes) < 4:
            # linha pela metade: e melhor pular do que derrubar o jogo,
            # e o numero da linha no comentario faz o problema ser
            # localiza em vez de adivinhado
            continue
        salas.append(tuple(int(p) for p in partes[:5]))  # type: ignore[arg-type]
    return salas


class Mundo:
    """O mapa e as salas, com os baus ja posicionados."""

    def __init__(self, mapa: Mapa) -> None:
        self.mapa = mapa
        self.salas = carregar_salas(mapa)

        # Quais salas ja usaram o bau. Um bau por sala: depois de
        # escolher, ele fica vazio, e o jogador tem de achar outro.
        # Bau que renasce a cada visita faz da escolha uma decoracao.
        self.baus_usados: set[int] = set()

        # O indice de celula para numero de sala. Montado uma vez: sem
        # ele, `numero_da_sala` varreria a lista de salas a cada chamada,
        # e ela e chamada a cada quadro em que o jogador se mexe.
        self._sala_de: dict[tuple[int, int], int] = {}
        for numero, (c0, l0, largura, altura, _) in enumerate(self.salas):
            for linha in range(l0, l0 + altura):
                for coluna in range(c0, c0 + largura):
                    self._sala_de[(coluna, linha)] = numero

        # A posicao do bau de cada sala, calculada uma vez. O bau fica
        # num quarto da largura da sala, e nao no centro: no centro
        # exato, o bau da sala do meio cai em cima da porta entre as
        # duas de cima. A posicao nao e decorativa — e o que impede o
        # bau de cair num corredor sem dono.
        self._bau_de: dict[int, tuple[int, int]] = {
            numero: (c0 + largura // 4, l0 + altura // 2)
            for numero, (c0, l0, largura, altura, _) in enumerate(self.salas)
        }

    # --- salas ---------------------------------------------------------

    def numero_da_sala(self, coluna: int, linha: int) -> int | None:
        """Qual sala e esta celula, pelo indice. `None` se nao e sala."""
        return self._sala_de.get((coluna, linha))

    def celula_do_bau(self, coluna: int, linha: int) -> tuple[int, int] | None:
        """O bau de quem esta em (coluna, linha), se ele nao usou ainda."""
        numero = self.numero_da_sala(coluna, linha)
        if numero is None or numero in self.baus_usados:
            return None
        return self._bau_de.get(numero)

    def marcar_bau_usado(self, coluna: int, linha: int) -> bool:
        """Marca o bau daquela sala como usado. True se marcou."""
        numero = self.numero_da_sala(coluna, linha)
        if numero is None or numero in self.baus_usados:
            return False
        self.baus_usados.add(numero)
        return True

    def inimigos_da_sala(self, coluna: int, linha: int) -> int:
        """Quantos inimigos tem na sala. Serve para o bau mostrar a escala."""
        numero = self.numero_da_sala(coluna, linha)
        if numero is None:
            return 0
        c0, l0, largura, altura, _ = self.salas[numero]
        total = 0
        for linha in range(l0, l0 + altura):
            for coluna in range(c0, c0 + largura):
                if self.mapa.em(coluna, linha) == Mapa.INIMIGO:
                    total += 1
        return total

    def tipos_disponiveis(self) -> tuple[C.Perfil, ...]:
        """Os tipos que o bau pode oferecer."""
        return (
            C.PERFIL_ESQUELETO,
            C.PERFIL_GUARDIAN,
            C.PERFIL_SACERDOTE,
            C.PERFIL_LOBISOMEM,
        )