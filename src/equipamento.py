"""O que o jogador leva nas maos.

Uma arma e um escudo, nunca os dois sem uma delas. Sao cinco
conjuntos, e cada um tem o desenho do heroi ja pronto, gerado no
PixelLab:

    nenhuma   so o escudo   espada   maça   espada+escudo   maça+escudo

O conjunto muda o desenho do heroi no mapa. NO COMBATE ele nao muda:
as animacoes de ataque e caminhada vem do espadachim do pacote de
mercado, e elas nao tem variante por arma. Fingir que a maça golpeia
com o arco de corte da espada seria pior do que deixar a animacao
como esta.
"""
from __future__ import annotations

from dataclasses import dataclass

ARMAS = ("espada", "maca")
ESCUDOS = (None, "escudo")


@dataclass(frozen=True)
class Conjunto:
    arma: str | None
    escudo: str | None

    @property
    def chave(self) -> str:
        """O nome do arquivo, do jeito que os desenhos foram salvos.

        Sem arma e com escudo o arquivo e `escudo.png`, e nao
        `so_escudo`: o nome do arquivo foi o que o PixelLab gerou
        primeiro, e a regra do nome segue o arquivo, e nao o
        contrario. A primeira versao montava `espada_desarmado` e
        `so_escudo`, e nenhum dos dois arquivos existia.
        """
        if self.arma and self.escudo:
            return f"{self.arma}_{self.escudo}"
        if self.arma:
            return self.arma
        if self.escudo:
            return self.escudo
        return "espada"

    @property
    def rotulo(self) -> str:
        arma = {"espada": "Espada", "maca": "Maca"}.get(self.arma, "Desarmado")
        escudo = "Escudo" if self.escudo else "Sem escudo"
        return f"{arma} / {escudo}"


PADRAO = Conjunto(arma="espada", escudo=None)

# os conjuntos que tem desenho pronto. Um conjunto novo sem arquivo
# cai no desenho PADRAO, e nunca em um retangulo vazio.
DESENHOS = {
    "espada",
    "maca",
    "escudo",
    "espada_escudo",
    "maca_escudo",
}


def chave_de(arma: str | None, escudo: str | None) -> str:
    return Conjunto(arma, escudo).chave


def tem_desenho(arma: str | None, escudo: str | None) -> bool:
    return chave_de(arma, escudo) in DESENHOS


def chave_com_desenho(arma: str | None, escudo: str | None) -> str:
    """A chave do desenho, caindo no padrao quando falta arquivo."""
    chave = chave_de(arma, escudo)
    if chave in DESENHOS:
        return chave
    padrao = PADRAO.chave
    return padrao if padrao in DESENHOS else chave


def todos_os_conjuntos() -> list[Conjunto]:
    """Os cinco conjuntos, na ordem em que o menu oferece."""
    return [
        Conjunto("espada", None),
        Conjunto("maca", None),
        Conjunto(None, "escudo"),
        Conjunto("espada", "escudo"),
        Conjunto("maca", "escudo"),
    ]
