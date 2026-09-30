"""Combate por turnos, com medidor de tempo (estilo Chrono Trigger).

A regra central do Chrono Trigger e o ATB: todo mundo tem uma barra que
enche com o tempo, e age sozinho quando ela chega no fim. O jogador
nao escolhe a ordem, escolhe o QUE fazer quando a vez dele chega. E o
que torna a batalha demonstravel sem virar um puzzle de fila.

Aqui:
  - `Combatente` e qualquer um com vida e uma barra de tempo
  - `Barra` e o medidor, com a escala de tempo da acao
  - `Batalha` e a maquina: enche as barras, resolve os turnos, aplica
    os efeitos

De proposito nao ha "vez do jogador" rigido: a barra do heroi e
rapida, a do esqueleto e lenta, e a batalha avanca pelos dois ao
mesmo tempo. Defender custa tempo, por isso da para escolher a hora de
se proteger.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class Estado(Enum):
    """Onde cada combatente esta na batalha."""

    VIVO = "vivo"
    ATACANDO = "atacando"
    FERIDO = "ferido"
    MORTO = "morto"


class Acao(Enum):
    """O que o jogador pode escolher quando a vez chega."""

    ATACAR = "Atacar"
    DEFENDER = "Defender"
    HABILIDADE = "Habilidade"


@dataclass
class Barra:
    """Medidor de tempo: enche, e o dono age quando chega no fim."""

    valor: float = 0.0
    limite: float = 100.0
    # quanto tempo a barra enche por segundo
    velocidade: float = 12.0

    @property
    def cheia(self) -> bool:
        return self.valor >= self.limite

    @property
    def fracao(self) -> float:
        """0 a 1, para desenhar."""
        if self.limite <= 0:
            return 1.0
        return max(0.0, min(1.0, self.valor / self.limite))

    def avancar(self, dt: float) -> float:
        """Avanca a barra e devolve quanto transbordou.

        O transbordo importa: uma barra rapida pode dar mais de uma
        volta em um unico quadro, e esse excedente precisa sobrar em
        vez de ser jogado fora. Quem chama reassina o valor com o que
        sobrou.
        """
        self.valor += self.velocidade * dt
        if self.valor < self.limite:
            return 0.0
        excesso = self.valor - self.limite
        self.valor = 0.0
        return excesso

    def gastar(self, custo: float) -> None:
        """Desconta o tempo de barra que a acao consumiu.

        O custo nunca deixa a barra negativa: se o jogador esperou
        menos do que a acao custa, ele age antes de encher de novo. Sem
        o piso em zero, a barra passaria de menos um para cima aos
        poucos e a vez seguinte demoraria mais do que devia.
        """
        self.valor = max(0.0, self.valor - custo)

    def zerar(self) -> None:
        self.valor = 0.0


@dataclass
class Combatente:
    """Alguem que luta."""

    nome: str
    vida: int
    vida_max: int
    velocidade_barra: float
    forca: int
    defesa: int = 0
    estado: Estado = Estado.VIVO
    barra: Barra = field(init=False)
    defendendo: bool = False
    # quanto de tempo de barra cada acao consome
    custo_ataque: float = 25.0
    custo_defesa: float = 15.0
    custo_habilidade: float = 40.0

    def __post_init__(self) -> None:
        self.barra = Barra(velocidade=self.velocidade_barra)

    @property
    def vivo(self) -> bool:
        return self.estado is not Estado.MORTO

    @property
    def fracao_vida(self) -> float:
        if self.vida_max <= 0:
            return 0.0
        return max(0.0, self.vida / self.vida_max)

    def receber(self, dano: int) -> int:
        """Aplica dano. Defender reduz pela metade."""
        if not self.vivo:
            return 0
        mitigado = self.defesa
        if self.defendendo:
            mitigado += max(1, mitigado // 2)
        real = max(1, dano - mitigado)
        self.vida = max(0, self.vida - real)
        if self.vida == 0:
            self.estado = Estado.MORTO
        else:
            self.estado = Estado.FERIDO if self.vida < self.vida_max else Estado.VIVO
        self.defendendo = False
        return real

    def curar(self, valor: int) -> int:
        if not self.vivo:
            return 0
        antes = self.vida
        self.vida = min(self.vida_max, self.vida + valor)
        return self.vida - antes


@dataclass
class Evento:
    """Algo que aconteceu e o jogo mostra na tela."""

    texto: str
    tipo: str = "info"  # info | dano | cura | morte


@dataclass
class Batalha:
    """A batalha em si: barras, turnos e efeitos."""

    heroi: Combatente
    inimigos: list[Combatente] = field(default_factory=list)
    eventos: list[Evento] = field(default_factory=list)
    turno_heroi: bool = False
    concluida: bool = False
    vencida: bool = False
    sorteio: random.Random = field(default_factory=random.Random)

    # --- estado ------------------------------------------------------
    @property
    def todos(self) -> list[Combatente]:
        return [self.heroi, *self.inimigos]

    @property
    def vivos(self) -> list[Combatente]:
        return [c for c in self.todos if c.vivo]

    def inimigos_vivos(self) -> list[Combatente]:
        return [c for c in self.inimigos if c.vivo]

    def alvo_aleatorio(self) -> Combatente | None:
        """Escolhe um inimigo vivo para o golpe acertar."""
        vivos = self.inimigos_vivos()
        if not vivos:
            return None
        return self.sorteio.choice(vivos)

    # --- acoes do jogador --------------------------------------------
    def acao_do_heroi(self, acao: Acao) -> list[Evento]:
        """Executa a acao escolhida. Devolve os eventos gerados.

        Devolve lista vazia quando a vez ainda nao e do jogador: quem
        chama (a cena) decide se mostra o menu ou nao.
        """
        if not self.turno_heroi or self.concluida or not self.heroi.vivo:
            return []

        ditos: list[Evento] = []

        if acao is Acao.DEFENDER:
            self.heroi.defendendo = True
            self.heroi.barra.gastar(self.heroi.custo_defesa)
            ditos.append(Evento(f"{self.heroi.nome} se defende", "info"))
            self._encerrar_turno_heroi()
            return ditos

        if acao is Acao.ATACAR:
            ditos.extend(self._golpe(self.heroi, self.alvo_aleatorio()))
            self.heroi.barra.gastar(self.heroi.custo_ataque)
            self._encerrar_turno_heroi()
            return ditos

        if acao is Acao.HABILIDADE:
            # por enquanto a habilidade e um golpe mais forte, que custa
            # mais tempo de barra. Defender e barato; o forte e caro
            # defender (barato) e o golpe forte (caro, mas machuca mais)
            ditos.extend(self._golpe(self.heroi, self.alvo_aleatorio(), forte=True))
            self.heroi.barra.gastar(self.heroi.custo_habilidade)
            self._encerrar_turno_heroi()
            return ditos

        return ditos

    def _golpe(
        self,
        quem: Combatente,
        alvo: Combatente | None,
        forte: bool = False,
    ) -> list[Evento]:
        if alvo is None or not alvo.vivo:
            return [Evento("Nao ha alvo", "info")]
        dano = quem.forca * (2 if forte else 1)
        real = alvo.receber(dano)
        eventos = [Evento(f"{quem.nome} acerta {alvo.nome} por {real}", "dano")]
        if forte:
            eventos.append(Evento(f"{quem.nome} usou Golpe Contundente", "info"))
        if not alvo.vivo:
            eventos.append(Evento(f"{alvo.nome} caiu", "morte"))
        return eventos

    def _encerrar_turno_heroi(self) -> None:
        self.turno_heroi = False
        # defender limpa a pose depois de resolver o golpe inimigo, nao
        # antes: senao o inimigo acerta o heroi sem a mitigacao
        self.heroi.defendendo = False

    # --- loop ---------------------------------------------------------
    def avancar(self, dt: float) -> list[Evento]:
        """Enche as barras e dispara quem encheu.

        O heroi entra em modo de espera quando a barra dele estoura e o
        jogador ainda nao escolheu. Inimigos agem na hora.
        """
        novos: list[Evento] = []
        if self.concluida:
            return novos

        # --- heroi ---
        if not self.turno_heroi and self.heroi.vivo:
            excesso = self.heroi.barra.avancar(dt)
            if excesso > 0:
                self.turno_heroi = True
                # o transbordo vira o novo valor: quem age duas vezes no
                # mesmo quadro nao espera a barra encher de novo
                self.heroi.barra.valor = excesso

        # --- inimigos ---
        for inimigo in self.inimigos_vivos():
            excesso = inimigo.barra.avancar(dt)
            if excesso > 0:
                inimigo.barra.valor = excesso
                novos.extend(self._acao_inimigo(inimigo))

        if self.heroi.vivo and not self.inimigos_vivos():
            self.concluida = True
            self.vencida = True
            novos.append(Evento("Vitoria", "info"))
        elif not self.heroi.vivo:
            self.concluida = True
            self.vencida = False
            novos.append(Evento("O heroi caiu", "morte"))

        self.eventos.extend(novos)
        return novos

    def _acao_inimigo(self, inimigo: Combatente) -> list[Evento]:
        """O que o esqueleto faz quando a barra dele estoura."""
        if not self.heroi.vivo:
            return []
        if self.sorteio.random() < 0.25:
            inimigo.defendendo = True
            inimigo.barra.gastar(inimigo.custo_defesa)
            return [Evento(f"{inimigo.nome} se defende", "info")]
        dano = max(1, inimigo.forca + self.sorteio.randint(-1, 2))
        real = self.heroi.receber(dano)
        ditos = [Evento(f"{inimigo.nome} acerta o heroi por {real}", "dano")]
        if not self.heroi.vivo:
            ditos.append(Evento("O heroi caiu", "morte"))
        return ditos

    # --- resumo -------------------------------------------------------
    def texto_status(self) -> str:
        partes = [f"{self.heroi.nome} {self.heroi.vida}/{self.heroi.vida_max}"]
        for i in self.inimigos_vivos():
            partes.append(f"{i.nome} {i.vida}/{i.vida_max}")
        return "   ".join(partes)


# --- fabricas de combatentes -------------------------------------------

def novo_heroi(vida: int = 60, forca: int = 9) -> Combatente:
    """O heroi: barra rapida, golpes certeiros."""
    return Combatente(
        nome="John", vida=vida, vida_max=vida,
        velocidade_barra=26.0, forca=forca, defesa=2,
    )


def novo_esqueleto(indice: int = 0) -> Combatente:
    """Inimigo de catacumba: barra lenta e vida curta, o oposto do heroi.

    O nome segue o sprite. O ghoul do pacote gfx tem corpo de verdade e
    e o inimigo principal; o esqueleto do Skeletons Pack e uma arte de
    6px de largura por 21 de altura, que le como um palito ao lado do
    jogador, e fica como a variante mais fraca.
    """
    nomes = ("Cavador", "Ossario", "Guardiao de Ossos", "Sentinela")
    vida = 26 + indice * 8
    return Combatente(
        nome=nomes[indice % len(nomes)],
        vida=vida, vida_max=vida,
        velocidade_barra=9.0 + indice * 1.5,
        forca=5 + indice * 2, defesa=1 + indice,
    )
