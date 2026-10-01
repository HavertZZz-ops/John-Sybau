"""Combate por TURNOS: um age por vez, e o jogador escolhe o que fazer.

Antes era ATB, no estilo Chrono Trigger: todo mundo tinha uma barra que
enchia com o tempo e agia sozinho quando ela transbordava. O jogador
nao controlava a ordem, so o QUE fazer, e o medidor corria sem parar
enquanto ele pensava.

A foto do jogador mostrou o resultado na tela: as barras de tempo como
riscos dourados soltos no chao, com a etiqueta "TEMPO", e nada
indicando de quem era a vez. E a leitura de um jogo de briga nao pode
depender de o jogador estar cronometrando.

Aqui:
  - `Combatente` e alguem com vida, forca e defesa. Nada de barra.
  - `Batalha` tem uma FILA: a ordem de quem age, montada por
    velocidade. O heroi age, a fila anda, cada inimigo age por vez, e a
    fila se refaz quando todo mundo ja agiu.
  - O jogo PARA enquanto o jogador escolhe. Nao ha contagem regressiva:
    o tempo parado e o que torna a decisao uma decisao.

A ordem se refaz a cada volta, e nao e fixa. Com velocidades iguais
ninguem ganha vez para sempre: quem agiu por ultimo volta a ir depois
de quem foi na frente. Uma fila que nunca muda e uma fila injusta.
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
    """O que o jogador pode escolher quando e a vez dele."""

    ATACAR = "Atacar"
    DEFENDER = "Defender"
    HABILIDADE = "Habilidade"
    ITEM = "Usar item"
    FUGIR = "Fugir"


@dataclass
class Combatente:
    """Alguem que luta.

    `velocidade` e a INICIATIVA: decide a ordem da fila, e nao um
    medidor que corre. Um esqueleto mais rapido age antes, uma vez por
    volta. Nao existe barra nenhuma.
    """

    nome: str
    vida: int
    vida_max: int
    forca: int
    velocidade: float = 10.0
    defesa: int = 0
    estado: Estado = Estado.VIVO
    defendendo: bool = False

    def __post_init__(self) -> None:
        # o desempate da fila: sem ele, dois inimigos com a mesma
        # velocidade trocam de posicao toda volta e a ordem vira
        # loteria. Com ele, a ordem e estavel.
        self._ordem = 0.0

    @property
    def vivo(self) -> bool:
        return self.estado is not Estado.MORTO

    @property
    def fracao_vida(self) -> float:
        if self.vida_max <= 0:
            return 0.0
        return max(0.0, min(1.0, self.vida / self.vida_max))

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
    """A batalha em si: a fila de quem age, e os efeitos."""

    heroi: Combatente
    inimigos: list[Combatente] = field(default_factory=list)
    eventos: list[Evento] = field(default_factory=list)
    concluida: bool = False
    vencida: bool = False
    # o jogador escolheu sair da luta em vez de ganhar
    fugiu: bool = False
    # item que a cena escolheu no inventario
    item_escolhido: str | None = None
    sorteio: random.Random = field(default_factory=random.Random)

    # a fila de quem age, nesta volta. Montada por velocidade na ordem
    # em que os combatentes entraram, e refaca quando acaba a volta.
    fila: list[Combatente] = field(default_factory=list, init=False)
    # posicao na fila de quem age agora
    cursor: int = 0
    # quantas voltas de fila ja deram
    volta: int = 0
    # quem ja agiu nesta volta, para nao refazer a fila com o mesmo
    # heroi duas vezes
    _agiu: set[int] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self._montar_fila()

    # --- estado ------------------------------------------------------
    @property
    def todos(self) -> list[Combatente]:
        return [self.heroi, *self.inimigos]

    @property
    def vivos(self) -> list[Combatente]:
        return [c for c in self.todos if c.vivo]

    def inimigos_vivos(self) -> list[Combatente]:
        return [c for c in self.inimigos if c.vivo]

    @property
    def turno_heroi(self) -> bool:
        """E a vez do heroi agora?"""
        if self.concluida or not self.heroi.vivo:
            return False
        if not self.fila:
            return False
        return self.fila[self.cursor] is self.heroi

    @property
    def de_quem_e_a_vez(self) -> Combatente | None:
        """Quem age agora, ou None se a batalha ja acabou."""
        if self.concluida or not self.fila:
            return None
        return self.fila[self.cursor]

    def alvo_aleatorio(self) -> Combatente | None:
        """Escolhe um inimigo vivo para o golpe acertar."""
        vivos = self.inimigos_vivos()
        if not vivos:
            return None
        return self.sorteio.choice(vivos)

    def _montar_fila(self) -> None:
        """Monta a ordem de quem age, do mais rapido para o mais lento.

        A ordem NAO e fixa. Quem ageu por ultimo na volta passada vai
        depois nesta: e o que impede o heroi de estar sempre primeiro e
        o chefe de estar sempre atras. O desempate e a ordem de entrada,
        entao a fila e estavel dentro da mesma volta.
        """
        # O desempate do empate: quem agiu por ULTIMO na volta passada
        # vai PRIMEIRO nesta. E a rotacao que impede a vitoria: com a
        # ordem anterior preservada, tres inimigos com a mesma
        # velocidade ficavam sempre na mesma posicao, e o heroi levava
        # dos tres antes de poder agir, toda volta, sem chance de
        # responder. Invertendo o desempate, o grupo roda.
        atras = {id(c): i for i, c in enumerate(self.fila)}
        ordem = {id(c): i for i, c in enumerate(self.todos)}
        vivos = [c for c in self.todos if c.vivo]
        self.fila = sorted(
            vivos,
            # mais rapido primeiro; empate resolvido por quem ficou mais
            # atras: o sinal negativo e o que inverte o desempate
            key=lambda c: (
                -c.velocidade,
                -atras.get(id(c), ordem[id(c)]),
            ),
        )
        self.cursor = 0
        self._agiu = set()

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
            ditos.append(Evento(f"{self.heroi.nome} se defende", "info"))
            self._encerrar_turno_heroi()
            return ditos

        if acao is Acao.ATACAR:
            ditos.extend(self._golpe(self.heroi, self.alvo_aleatorio()))
            self._encerrar_turno_heroi()
            return ditos

        if acao is Acao.HABILIDADE:
            # O SUPER SOCO. E a habilidade do heroi brigador, e ele
            # continua socando mesmo depois de achar uma espada: e o
            # golpe dele, nao um poder da arma.
            ditos.extend(self._golpe(self.heroi, self.alvo_aleatorio(), forte=True))
            ditos.append(Evento(f"{self.heroi.nome} solta um SUPER SOCO", "dano"))
            self._encerrar_turno_heroi()
            return ditos

        if acao is Acao.ITEM:
            # A cena abre o inventario antes de chamar isto. Aqui so
            # chega o item ja escolhido, com o id no `acao`. Devolver
            # a lista vazia quando nao ha item impede o turno de passar
            # com o jogador sem ter feito nada.
            item_id = getattr(acao, "item_id", None) or self.item_escolhido
            if not item_id:
                return ditos
            from . import itens as itens_mod

            curado = itens_mod.usar(item_id, self.heroi)
            nome = (itens_mod.obter(item_id) or itens_mod.Item("", "item", "")).nome
            if curado <= 0:
                ditos.append(Evento(f"{self.heroi.nome} ja esta com a vida cheia", "info"))
                return ditos
            self.item_escolhido = None
            ditos.append(Evento(f"{self.heroi.nome} usou {nome} e curou {curado}", "cura"))
            self._encerrar_turno_heroi()
            return ditos

        if acao is Acao.FUGIR:
            # Fugir nao e uma acao como as outras: nao machuca ninguem
            # e nao da tempo de o inimigo revidar. A luta acaba na hora,
            # com o heroi como esta.
            self.fugiu = True
            self.concluida = True
            ditos.append(Evento(f"{self.heroi.nome} foge da luta", "info"))
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
        # o heroi agiu: a fila avanca para o proximo
        self._agiu.add(id(self.heroi))
        # defender limpa a pose depois de resolver o golpe inimigo, nao
        # antes: senao o inimigo acerta o heroi sem a mitigacao
        self._avancar_cursor()

    def _avancar_cursor(self) -> None:
        """Passa a fila para quem age agora. Refaz a volta se acabou."""
        self.cursor += 1
        # pula quem ja agiu nesta volta: nao vale a pena o heroi agir
        # duas vezes antes de todo mundo ter agido uma
        while self.cursor < len(self.fila) and id(self.fila[self.cursor]) in self._agiu:
            self.cursor += 1
        # se ninguem mais tem vez nesta volta, abre a proxima
        if self.cursor >= len(self.fila):
            self.volta += 1
            self._montar_fila()
            self._checar_fim()

    # --- loop ---------------------------------------------------------
    def avancar(self, dt: float) -> list[Evento]:
        """Acoes dos inimigos, uma de cada vez.

        Nao enche nada com o tempo: um inimigo age quando o jogador ja
        agiu, e age SO. Cada inimigo age, e a fila anda. O `dt` fica
        para a cena animar, e nao para decidir quem age.

        O heroi age quando o jogador escolhe, em `acao_do_heroi`. Nao
        existe espera: entre a escolha do jogador e a vez do proximo da
        fila, o jogo para e mostra o que aconteceu.
        """
        novos: list[Evento] = []
        if self.concluida:
            return novos

        # na vez do heroi, o jogo PARA: quem age e o jogador, pelo menu. Sem
        # este return, a fila andava a procura do heroi e o proximo
        # inimigo batia antes de o menu aparecer na tela.
        if not self.fila or self.fila[self.cursor] is self.heroi:
            self._checar_fim()
            self.eventos.extend(novos)
            return novos

        if self.cursor < len(self.fila):
            inimigo = self.fila[self.cursor]
            novos.extend(self._acao_inimigo(inimigo))
            self._agiu.add(id(inimigo))
            self._avancar_cursor()

        self._checar_fim()
        self.eventos.extend(novos)
        return novos

    def _acao_inimigo(self, inimigo: Combatente) -> list[Evento]:
        """O que o esqueleto faz quando chega a vez dele."""
        if not self.heroi.vivo:
            return []
        if self.sorteio.random() < 0.25:
            inimigo.defendendo = True
            return [Evento(f"{inimigo.nome} se defende", "info")]
        dano = max(1, inimigo.forca + self.sorteio.randint(-1, 2))
        real = self.heroi.receber(dano)
        ditos = [Evento(f"{inimigo.nome} acerta o heroi por {real}", "dano")]
        if not self.heroi.vivo:
            ditos.append(Evento("O heroi caiu", "morte"))
        return ditos

    def _checar_fim(self) -> None:
        if self.heroi.vivo and not self.inimigos_vivos():
            self.concluida = True
            self.vencida = True
            self.eventos.append(Evento("Vitoria", "info"))
        elif not self.heroi.vivo:
            self.concluida = True
            self.vencida = False
            self.eventos.append(Evento("O heroi caiu", "morte"))

    # --- resumo -------------------------------------------------------
    def texto_status(self) -> str:
        partes = [f"{self.heroi.nome} {self.heroi.vida}/{self.heroi.vida_max}"]
        for i in self.inimigos_vivos():
            partes.append(f"{i.nome} {i.vida}/{i.vida_max}")
        return "   ".join(partes)


# --- fabricas de combatentes -------------------------------------------

def novo_heroi(vida: int = 60, forca: int = 9) -> Combatente:
    """O heroi: rapido na iniciativa, golpes certeiros."""
    return Combatente(
        nome="John", vida=vida, vida_max=vida,
        velocidade=18.0, forca=forca, defesa=2,
    )


def novo_esqueleto(indice: int = 0, fraco: bool = False) -> Combatente:
    """Inimigo de catacumba: lento na iniciativa e vida curta.

    O nome segue o sprite. O esqueleto do Skeletons Pack e a variante
    mais fraca.

    `fraco` existe para a PRIMEIRA sala, que tem que ensinar o golpe sem
    matar quem esta aprendendo. Sem esse caminho o primeiro esqueleto
    tinha exatamente os mesmos numeros dos outros.
    """
    nomes = ("Cavador", "Ossario", "Guardiao de Ossos", "Sentinela")
    vida = 26 + indice * 8
    forca = 5 + indice * 2
    defesa = 1 + indice
    init = 11.0 - indice * 1.5
    if fraco:
        # mais lento que o heroi: da vez ao jogador antes de levar o
        # contra-ataque, que e a aula da sala 1
        vida = 12
        forca = 3
        defesa = 0
        init = 8.0
    return Combatente(
        nome=nomes[indice % len(nomes)],
        vida=vida, vida_max=vida,
        velocidade=init, forca=forca, defesa=defesa,
    )


def novo_chefe() -> Combatente:
    """O chefe da ultima sala: forte demais para se puzzling.

    A INITIATIVA dele e rapida, nao a barra: ele age cedo na volta. A
    vida e a defesa sao altas de proposito. Ele nao e matavel no
    encontro: a aula e saber que fugir existe.
    """
    return Combatente(
        nome="O Cobrador",
        vida=180, vida_max=180,
        velocidade=16.0,
        forca=17, defesa=5,
    )