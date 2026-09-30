"""O que o jogador leva nas maos.

O jogo COMECA com as maos enroladas em panos e ninguem na mao: o
heroi e um brigador, e a primeira coisa que ele aprende a fazer e
socar. A arma vem depois, comprada do Estranho na aldeia.

Sao seis conjuntos:

    punho   so escudo   espada   maça   espada+escudo   maça+escudo

O conjunto muda o desenho do heroi no mapa e, a partir das animacoes
do PixelLab, tambem o soco e a caminhada. A habilidade especial e um
SUPER SOCO em qualquer conjunto: e o golpe do(personagem desarmado, e
continua sendo o que ele faz mesmo depois de achar uma espada.
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
        return SEM_NADA

    @property
    def rotulo(self) -> str:
        if not self.arma and not self.escudo:
            return "Punhos / Sem escudo"
        arma = {"espada": "Espada", "maca": "Maca"}.get(self.arma, "Punhos")
        escudo = "Escudo" if self.escudo else "Sem escudo"
        return f"{arma} / {escudo}"

    @property
    def e_desarmado(self) -> bool:
        return self.arma is None


PADRAO = Conjunto(arma=None, escudo=None)

# o nome do arquivo e do PixelLab, entao o conjunto sem nada e `punho`,
# e nao uma chave montada no codigo
SEM_NADA = "punho"

DESENHOS = {
    SEM_NADA,
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
    """Os seis conjuntos, na ordem em que o menu oferece.

    O punho vem primeiro porque e o comeco do jogo.
    """
    return [
        Conjunto(None, None),
        Conjunto("espada", None),
        Conjunto("maca", None),
        Conjunto(None, "escudo"),
        Conjunto("espada", "escudo"),
        Conjunto("maca", "escudo"),
    ]
