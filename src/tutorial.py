"""Aulas que aparecem jogando, sem tela de texto para pular.

O tutorial nao e um manual nem um painel: cada dica entra na hora em que
ela vale, some sozinha quando o jogador faz a coisa, e nunca bloqueia o
controle. Quem joga sem ler o tutorial ve as mesmas frases passando.

Cada `Aula` e uma frase, um gatilho (a acao que ela ensina) e um tempo
de vida. O `Tutorial` guarda a ordem e diz qual esta na tela.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Aula:
    """Uma dica, e o que a faz desaparecer."""

    texto: str
    # acao do mapa de teclas que "cumpre" a aula
    gatilho: str = ""
    # segundos que a dica fica se nao houver gatilho
    duracao: float = 5.0
    # texto pequeno embaixo, opcional
    detalhe: str = ""


@dataclass
class Tutorial:
    """Sequencia de aulas, uma por vez."""

    aulas: tuple[Aula, ...]
    indice: int = -1
    tempo: float = 0.0
    concluidas: list[str] = field(default_factory=list)

    @property
    def atual(self) -> Aula | None:
        """A aula na tela, ou None se ja acabaram."""
        if 0 <= self.indice < len(self.aulas):
            return self.aulas[self.indice]
        return None

    @property
    def ativo(self) -> bool:
        return self.atual is not None

    @property
    def terminou(self) -> bool:
        return self.indice >= len(self.aulas)

    def comecar(self) -> None:
        """Abre a primeira aula que ainda falta."""
        self.indice = 0
        self.tempo = 0.0
        while (
            self.indice < len(self.aulas)
            and self.aulas[self.indice].texto in self.concluidas
        ):
            self.indice += 1

    def mostrar(self, texto: str) -> None:
        """Puxa a aula do texto, para display atrasado de uma etapa."""
        for i, aula in enumerate(self.aulas):
            if aula.texto == texto:
                self.indice = i
                self.tempo = 0.0
                return

    def update(self, dt: float, acao_cumprida: str | None = None) -> str | None:
        """Avanca. Devolve o texto de quem acabou de ser concluida.

        `acao_cumprida` e a acao do mapa de teclas que o jogador fez
        neste quadro, ou None. E o que fecha a aula.
        """
        self.tempo += dt
        aula = self.atual
        if aula is None:
            return None

        # so fecha depois de um pouco de tempo na tela: uma dica que some
        # no mesmo quadro em que acende nao e lida por ninguem
        if self.tempo > 0.6:
            if aula.gatilho and acao_cumprida == aula.gatilho:
                return self._concluir(aula.texto)
            # aula sem gatilho e so informative: expira sozinha
            if not aula.gatilho and self.tempo >= aula.duracao:
                return self._concluir(aula.texto)
        return None

    def _concluir(self, texto: str) -> str | None:
        if texto not in self.concluidas:
            self.concluidas.append(texto)
        if self.indice < len(self.aulas):
            self.indice += 1
            self.tempo = 0.0
        return texto

    def forcar(self, texto: str) -> str | None:
        """Fecha a aula atual na hora, para quando o passo e obvious."""
        aula = self.atual
        if aula is None or aula.texto != texto:
            return None
        return self._concluir(texto)

    def resetar(self) -> None:
        self.indice = -1
        self.tempo = 0.0
        self.concluidas.clear()


# O roteiro do comeco. A ordem importa: cada aula so faz sentido depois
# da anterior, e a aula de combate so aparece quando o esqueleto ja
# apareceu na tela.
TUTORIAL_CATACUMBAS = Tutorial(aulas=(
    Aula(
        "Voce acordou dentro de um caixao",
        detalhe="as catacumbas ficam embaixo da Parish of the Undead",
        duracao=4.5,
    ),
    Aula(
        "Use as setas para andar",
        gatilho="mover_direita",
        detalhe="o medidor de tempo comecou a encher",
        duracao=7.0,
    ),
    Aula(
        "F5 salva o jogo",
        gatilho="salvar",
        detalhe="sair da masmorra tambem salva",
        duracao=7.0,
    ),
    Aula(
        "Esc volta para o menu",
        gatilho="voltar",
        detalhe="de onde voce foi",
        duracao=7.0,
    ),
    Aula(
        "O esqueleto acordou",
        detalhe="quando ele tocar em voce, a luta comeca",
        duracao=4.5,
    ),
    Aula(
        "O medidor enche com o tempo",
        detalhe="cada um age quando o dele enche",
        duracao=5.0,
    ),
    Aula(
        "Escolha Atacar quando a sua vez chegar",
        gatilho="confirmar",
        detalhe="Defender corta o dano pela metade, Habilidade bate mais forte",
        duracao=9.0,
    ),
))