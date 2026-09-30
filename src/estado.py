"""O estado do jogo entre as cenas: vida, ouro e a ultima fogueira.

A vida do heroi e o ouro moravam dentro da cena de combate e sumiam
quando ela acabava. Descansar numa fogueira e sair para a proxima luta
precisa dos doiscontinuando, entao eles passam a morar aqui, no estado do
gerenciador, que atravessa as cenas.

Ficar no estado do gerenciador e o que faz o descanso ter efeito: o
combate recria o heroi do zero a cada luta, e um descanso que so
existisse durante a cena da masmorra seria esquecido na luta seguinte.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Estado:
    """O que o jogador carrega de uma cena para a outra."""

    vida: int = 60
    vida_max: int = 60
    ouro: int = 0
    # a ultima fogueira usada, para saber onde o jogador renasce
    fogueira: str = ""

    def curar(self, valor: int) -> int:
        antes = self.vida
        self.vida = min(self.vida_max, self.vida + valor)
        return self.vida - antes

    @property
    def vida_fracao(self) -> float:
        if self.vida_max <= 0:
            return 0.0
        return max(0.0, min(1.0, self.vida / self.vida_max))

    @property
    def esta_vivo(self) -> bool:
        return self.vida > 0

    def descansar(self, pocoes: int = 1) -> None:
        """Descanso de fogueira: vida cheia e pocoes repostas."""
        self.vida = self.vida_max
        # as pocoes vao pelo inventario do progresso, e nao aqui, para
        # nao haver duas listas de itens que podem discordar
        self.pocoes_repor = pocoes

    def para_extra(self) -> dict:
        return {
            "vida": self.vida,
            "vida_max": self.vida_max,
            "ouro": self.ouro,
            "fogueira": self.fogueira,
        }

    @classmethod
    def de_extra(cls, bruto) -> "Estado":
        padrao = cls()
        if not isinstance(bruto, dict):
            return padrao
        vida_max = bruto.get("vida_max", padrao.vida_max)
        if not isinstance(vida_max, int) or vida_max <= 0:
            vida_max = padrao.vida_max
        vida = bruto.get("vida", padrao.vida)
        if not isinstance(vida, int):
            vida = padrao.vida
        # vida acima do max vem de um save com max antigo
        vida = max(0, min(vida, vida_max))
        ouro = bruto.get("ouro", 0)
        if not isinstance(ouro, int) or ouro < 0:
            ouro = 0
        fogueira = bruto.get("fogueira", "")
        if not isinstance(fogueira, str):
            fogueira = ""
        return cls(vida=vida, vida_max=vida_max, ouro=ouro, fogueira=fogueira)


def do_gerenciador(manager) -> Estado:
    """Pega o estado do gerenciador, criando se ainda nao existir."""
    estado = manager.ui_state.get("estado")
    if estado is None:
        estado = Estado()
        manager.ui_state["estado"] = estado
    return estado

