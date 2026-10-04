"""Combate por turnos.

Duas ideias sustentam tudo aqui, e elas sao a diferenca entre "uma fila
onde os lados se alternam" e "um jogo de turno de verdade":

**1. A volta e em BLOCOS, nao alternada.**
O heroi age, e so depois agem os inimigos. Nao e o heroi, inimigo, heroi,
inimigo. E o jogador ter uma decisao de verdade por rodada, com a tela
parada na sua frente, e so entao ver a resposta. Na fila alternada o
jogador fica trocando de lado a cada escolha e a pressao fica dividida.

A consequencia pratica e a mais importante: **defender vira uma decisao
real.** Se o jogador defender e o inimigo atacar logo depois, defender
foi certo. Na fila alternada, o heroi defenderia e o proximo a agir
seria ele de novo — a defesa nunca pagaria.

**2. O inimigo DECIDE, e cada tipo decide diferente.**
Cada inimigo tem um `Perfil` com pesos para atacar, defender, curar e
fugir. Um esqueleto ataca quase sempre; um guardiao se protege quando
esta ferido; um sacerdote se cura e foge; um lobisomem investe. O
jogador aprende a ler o tipo, que e o que faz o combate ter solucao em
vez de ser roleta.

O inimigo tambem **telegrafa**: a decisao e tomada no momento em que a
fase vira, e o que foi prometido e o que acontece. Um telegrafo que
mente nao serve para planejar, so para o jogador desconfiar de tudo.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class Fase(Enum):
    """De quem e a vez de agir AGORA."""

    HEROI = "heroi"
    INIMIGOS = "inimigos"


class AcaoHeroi(Enum):
    """O que o jogador pode escolher no turno dele."""

    ATACAR = "Atacar"
    DEFENDER = "Defender"
    FUGIR = "Fugir"


@dataclass
class Habilidade:
    """Uma habilidade que um inimigo pode usar no turno dele."""

    nome: str
    # o que ela faz: "dano" | "cura" | "defesa"
    efeito: str
    # quantas vezes o efeito e forcado: um golpe e 1x, a investida e 2x
    potencia: int = 1
    # de quantas rodadas em quantas ela volta. 1 = sempre
    recarga: int = 1


@dataclass
class Perfil:
    """O CARATER do inimigo: como ele pensa e no que ele e bom.

    Aqui moram as diferencas entre um esqueleto e um lobisomem. Sem isto,
    todo inimigo seria o mesmo esqueleto com numeros diferentes, e a "IA"
    seria um sorteio — o jogador nao teria nada para aprender.
    """

    nome: str
    vida: int
    forca: int
    defesa: int
    velocidade: float
    # o peso de cada opcao. O que o inimigo mais pesa e o que ele mais
    # faz de verdade. Os pesos sao RELATIVOS entre si: dobrar o peso de
    # ataque dobra a chance, e nao a soma.
    peso_ataque: float = 6.0
    peso_defesa: float = 2.0
    peso_cura: float = 0.0
    peso_fuga: float = 0.0
    # abaixo desta fracao de vida o inimigo comeca a se curar
    limiar_cura: float = 0.35
    # quanto ele cura por vez
    cura: int = 0
    habilidades: tuple[Habilidade, ...] = ()
    # quantas vezes seguidas ele pode se defender antes de ser OBRIGADO a
    # atacar. Sem isto, um inimigo pesado (defesa alta) passa a luta
    # inteira se defendendo e o golpe do heroi nunca entra: a luta nao
    # acaba, ela empaca.
    defesas_seguidas: int = 3
    descricao: str = ""


@dataclass
class Combatente:
    """Alguem que luta."""

    nome: str
    vida: int
    vida_max: int
    forca: int
    defesa: int = 0
    velocidade: float = 10.0
    defendendo: bool = False
    # o carater deste inimigo. O heroi nao tem: ele escolhe.
    perfil: Perfil | None = None

    def __post_init__(self) -> None:
        self._recargas: dict[str, int] = {}
        self._defesas_seguidas = 0

    @property
    def vivo(self) -> bool:
        return self.vida > 0

    @property
    def fracao_vida(self) -> float:
        if self.vida_max <= 0:
            return 0.0
        return max(0.0, min(1.0, self.vida / self.vida_max))

    @property
    def ferido(self) -> bool:
        """Esta com a vida abaixo do maximo?"""
        return self.vida < self.vida_max

    def receber(self, dano: int) -> int:
        """Aplica dano e devolve quanto saiu. Defender reduz pela metade.

        Defender NAO reduz o dano pela metade, e sim AUMENTA a mitigacao
        em metade. A diferenca importa com defesa alta: contra defesa 6,
        "metade do dano" seria 3 de reducao, enquanto "mitigacao + 3"
        seria 9 — e o segundo e o que faz a defesa valer a pena.
        """
        if not self.vivo:
            return 0

        mitigado = self.defesa
        if self.defendendo:
            mitigado += max(1, mitigado // 2)

        real = max(1, dano - mitigado)
        self.vida = max(0, self.vida - real)
        # A pose de defesa dura UM golpe. Sem limpar aqui, o inimigo ficaria
        # defendendo para sempre depois de uma unica escolha, que e o
        # estado mais impossivel de entender num combate.
        self.defendendo = False
        return real

    def curar(self, valor: int) -> int:
        """Cura e devolve quanto curou de verdade."""
        if not self.vivo:
            return 0
        antes = self.vida
        self.vida = min(self.vida_max, self.vida + valor)
        return self.vida - antes

    def pode_defender(self) -> bool:
        """Ainda pode se defender, ou ja se defendeu demais seguidas?"""
        limite = self.perfil.defesas_seguidas if self.perfil else 3
        return self._defesas_seguidas < limite

    def usar_habilidade(self, habilidade: Habilidade) -> None:
        self._recargas[habilidade.nome] = habilidade.recarga

    def habilidade_liberada(self, habilidade: Habilidade) -> bool:
        return self._recargas.get(habilidade.nome, 0) <= 0

    def girar_recargas(self) -> None:
        """Uma rodada passou: as recargas descem um."""
        for nome in list(self._recargas):
            self._recargas[nome] = max(0, self._recargas[nome] - 1)


@dataclass
class Evento:
    """Algo que aconteceu e o jogo mostra na tela."""

    texto: str
    tipo: str = "info"  # info | dano | cura | morte | defesa


# --- os inimigos -----------------------------------------------------------


PERFIL_ESQUELETO = Perfil(
    nome="esqueleto",
    vida=24, forca=6, defesa=1, velocidade=11.0,
    peso_ataque=9.0, peso_defesa=1.2,
    limiar_cura=0.3,
    descricao="lento e direto",
)

# A defesa e o que define este inimigo, e por isso nao pode ser alta
# demais. Com defesa 7 e o heroi batendo 9, cada golpe entra 2 e o
# guardiao levaria 27 golpes. O que faz um inimigo ser duro NAO e a
# defesa alta: e nao levar a vida toda de uma vez.
PERFIL_GUARDIAN = Perfil(
    nome="guardiao",
    vida=48, forca=7, defesa=4, velocidade=7.0,
    peso_ataque=4.0, peso_defesa=4.0, peso_cura=1.5,
    limiar_cura=0.4, cura=14,
    defesas_seguidas=2,
    descricao="duro de furar, se protege",
)

# O unico que foge de proposito: ele nao veio brigar.
PERFIL_SACERDOTE = Perfil(
    nome="sacerdote",
    vida=36, forca=7, defesa=2, velocidade=12.5,
    peso_ataque=3.5, peso_defesa=1.0, peso_cura=7.0, peso_fuga=4.5,
    limiar_cura=0.55, cura=18,
    habilidades=(Habilidade("Maldicao", "dano", potencia=2, recarga=2),),
    descricao="se cura e amaldicoa",
)

# Nao se defende e nao se cura: ele nao sabe. Quem bate forte nao precisa
# se proteger.
PERFIL_LOBISOMEM = Perfil(
    nome="lobisomem",
    vida=44, forca=11, defesa=3, velocidade=16.0,
    peso_ataque=8.0, peso_defesa=0.4,
    habilidades=(
        Habilidade("Investida", "dano", potencia=2, recarga=2),
        Habilidade("Uivo", "defesa", recarga=3),
    ),
    descricao="corre e investe",
)

PERFIL_COBRADOR = Perfil(
    nome="cobrador",
    vida=120, forca=15, defesa=5, velocidade=14.0,
    peso_ataque=7.0, peso_defesa=2.0, peso_cura=3.0,
    limiar_cura=0.45, cura=28,
    habilidades=(Habilidade("Cobranca", "dano", potencia=3, recarga=2),),
    descricao="nao larga",
)

PERFIS: tuple[Perfil, ...] = (
    PERFIL_ESQUELETO,
    PERFIL_GUARDIAN,
    PERFIL_SACERDOTE,
    PERFIL_LOBISOMEM,
    PERFIL_COBRADOR,
)

# O sprite de cada perfil. O nome vem do perfil, e nao da posicao na
# lista: antes era `FOE_KINDS[i % 4]`, e um guardiao acabava desenhado
# com a arte do esqueleto mais rapido, enquanto a barra de vida dizia
# "Guardiao".
SPRITE_DO_PERFIL: dict[str, str] = {
    "esqueleto": "inimigos/esqueleto",
    "guardiao": "inimigos/guardiao",
    "sacerdote": "inimigos/sacerdote",
    "lobisomem": "inimigos/lobisomem",
    "cobrador": "inimigos/cobrador",
}


def novo_inimigo(perfil: Perfil, indice: int = 0) -> Combatente:
    """Um inimigo a partir do perfil dele.

    `indice` escala os numeros DENTRO do perfil, sem trocar o
    personagem: dois esqueletos podem ter vidas diferentes e continuam
    sendo esqueletos. O que diferencia um inimigo de outro e o perfil.
    """
    vida = perfil.vida + indice * 6
    return Combatente(
        nome=perfil.nome.capitalize(),
        vida=vida,
        vida_max=vida,
        forca=perfil.forca + indice * 2,
        defesa=perfil.defesa,
        velocidade=perfil.velocidade,
        perfil=perfil,
    )


# --- a batalha -------------------------------------------------------------


class Batalha:
    """A luta: os dois lados, a fase, e o que cada um fez."""

    def __init__(self, heroi: Combatente, sorteio: random.Random | None = None):
        self.heroi = heroi
        self.inimigos: list[Combatente] = []
        self.sorteio = sorteio or random.Random()

        self.fase = Fase.HEROI
        self.rodada = 0
        # o que cada inimigo ANUNCIOU na virada de fase
        self._intencao: dict[int, str | Habilidade] = {}

        self.concluida = False
        self.vencida = False
        self.fugiu = False
        self.eventos: list[Evento] = []

    # --- estado --------------------------------------------------------

    def adicionar(self, *inimigos: Combatente) -> None:
        self.inimigos.extend(inimigos)

    @property
    def inimigos_vivos(self) -> list[Combatente]:
        return [i for i in self.inimigos if i.vivo]

    @property
    def heroi_vivo(self) -> bool:
        return self.heroi.vivo

    @property
    def turno_do_heroi(self) -> bool:
        """E a vez do jogador?"""
        return not self.concluida and self.fase is Fase.HEROI

    # --- a virada de fase ---------------------------------------------

    def _virar_para_inimigos(self) -> None:
        """O heroi agiu: agora e a vez de todo mundo do outro lado.

        O telegrafo e calculado AQUI, e nao quando o inimigo age. Se fosse
        depois, o jogador veria o efeito sem ter visto a intencao, e o
        telegrafo deixaria de servir para planejar.
        """
        self.fase = Fase.INIMIGOS
        self._intencao.clear()
        for inimigo in self.inimigos_vivos:
            self._intencao[id(inimigo)] = self._escolher(inimigo)

    def _virar_para_heroi(self) -> None:
        """Os inimigos acabaram: abre a rodada nova."""
        self.rodada += 1
        self.fase = Fase.HEROI
        self._intencao.clear()
        self._checar_fim()

    def intencao_de(self, inimigo: Combatente) -> str:
        """O que este inimigo vai fazer, em texto para a tela."""
        escolha = self._intencao.get(id(inimigo))
        if escolha is None:
            return "..."
        if isinstance(escolha, Habilidade):
            return escolha.nome
        return {
            "ataque": "atacar",
            "defesa": "se defender",
            "cura": "se curar",
            "fuga": "fugir",
        }.get(escolha, "...")

    def vai_fugir(self, inimigo: Combatente) -> bool:
        """Este inimigo anunciou que vai fugir?"""
        return self._intencao.get(id(inimigo)) == "fuga"

    # --- o turno do heroi ---------------------------------------------

    def acao_do_heroi(self, acao: AcaoHeroi) -> list[Evento]:
        """Executa a escolha do jogador e vira a fase.

        Devolve lista vazia se nao for a vez do jogador. Quem chama (a
        cena) decide se mostra o menu ou nao.
        """
        if not self.turno_do_heroi:
            return []

        ditos: list[Evento] = []

        if acao is AcaoHeroi.DEFENDER:
            self.heroi.defendendo = True
            ditos.append(Evento(f"{self.heroi.nome} se defende", "defesa"))

        elif acao is AcaoHeroi.ATACAR:
            ditos.extend(self._golpe_do_heroi())

        elif acao is AcaoHeroi.FUGIR:
            # Fugir acaba a luta na hora. E a unica acao que nao da tempo
            # de o inimigo revidar: o jogador que nao aguenta e sai, e o
            # jogo respeita.
            self.fugiu = True
            self.concluida = True
            ditos.append(Evento(f"{self.heroi.nome} foge da luta", "info"))

        else:
            return []

        self.eventos.extend(ditos)
        self._checar_fim()
        if not self.concluida:
            self._virar_para_inimigos()
        return ditos

    def _golpe_do_heroi(self) -> list[Evento]:
        """O golpe basico do heroi, no alvo mais fraco.

        Alvo mais fraco e nao aleatorio: num grupo de quatro, acertar o
        mais machucado derruba um a cada tres golpes, enquanto acertar
        aleatorio leva oito. O jogador nao espera escolher alvo na
        versao simples, e a escolha mais obvia que existe e a que menos
        frustraria.
        """
        vivos = self.inimigos_vivos
        if not vivos:
            return [Evento("Nao ha mais inimigos", "info")]

        alvo = min(vivos, key=lambda i: i.vida)
        real = alvo.receber(self.heroi.forca)
        ditos = [Evento(f"{self.heroi.nome} acerta {alvo.nome} por {real}", "dano")]
        if not alvo.vivo:
            ditos.append(Evento(f"{alvo.nome} caiu", "morte"))
        return ditos

    # --- o turno dos inimigos -----------------------------------------

    def jogada_inimiga(self) -> list[Evento]:
        """Todo mundo do outro lado age, um por vez.

        A ordem e do MAIS RAPIDO para o mais lento, montada uma vez por
        fase. A ordem muda a cada rodada porque os velocidades podem
        morrer e o jogador precisa ver que ninguem tem vez garantida.
        """
        if self.concluida or self.fase is not Fase.INIMIGOS:
            return []

        ditos: list[Evento] = []
        for inimigo in self._ordem_dos_inimigos():
            if not inimigo.vivo or not self.heroi_vivo:
                continue
            ditos.extend(self._agir(inimigo))

        self.eventos.extend(ditos)
        self._virar_para_heroi()
        return ditos

    def _ordem_dos_inimigos(self) -> list[Combatente]:
        """Os inimigos vivos, do mais rapido para o mais lento."""
        return sorted(self.inimigos_vivos, key=lambda i: -i.velocidade)

    def _agir(self, inimigo: Combatente) -> list[Evento]:
        """Um inimigo age: consome o que prometeu, ou escolhe agora.

        Consome o telegrafo para que a promessa seja o ato. Se nao houver
        promessa (o inimigo entrou na fase depois), escolhe agora — o
        turno dele nunca pode passar sem fazer nada.
        """
        perfil = inimigo.perfil or PERFIL_ESQUELETO
        inimigo.girar_recargas()

        escolha = self._intencao.pop(id(inimigo), None)
        if escolha is None:
            escolha = self._escolher(inimigo)

        nome = inimigo.nome

        if escolha == "defesa":
            inimigo.defendendo = True
            inimigo._defesas_seguidas += 1
            return [Evento(f"{nome} se defende", "defesa")]

        # agiu sem se defender: a contagem volta a zero
        inimigo._defesas_seguidas = 0

        if escolha == "cura":
            curado = inimigo.curar(perfil.cura)
            return [Evento(f"{nome} se cura por {curado}", "cura")]

        if escolha == "fuga":
            self.fugiu = True
            self.concluida = True
            return [Evento(f"{nome} foge da luta", "info")]

        if isinstance(escolha, Habilidade):
            return self._usar_habilidade(inimigo, escolha)

        return self._golpe_de(inimigo)

    def _golpe_de(self, inimigo: Combatente) -> list[Evento]:
        """O ataque basico do inimigo, no dano DELE."""
        dano = max(1, inimigo.forca + self.sorteio.randint(-1, 2))
        real = self.heroi.receber(dano)
        ditos = [Evento(f"{inimigo.nome} acerta {self.heroi.nome} por {real}",
                        "dano")]
        if not self.heroi.vivo:
            ditos.append(Evento(f"{self.heroi.nome} caiu", "morte"))
        return ditos

    def _usar_habilidade(
        self, inimigo: Combatente, habilidade: Habilidade
    ) -> list[Evento]:
        """A habilidade especial do inimigo."""
        inimigo.usar_habilidade(habilidade)
        nome = inimigo.nome

        if habilidade.efeito == "defesa":
            inimigo.defendendo = True
            inimigo._defesas_seguidas += 1
            return [Evento(f"{nome} usa {habilidade.nome}", "defesa")]

        if habilidade.efeito == "cura":
            curado = inimigo.curar(
                inimigo.perfil.cura if inimigo.perfil else 0
            )
            return [Evento(f"{nome} usa {habilidade.nome} e cura {curado}",
                           "cura")]

        dano = max(1, inimigo.forca * habilidade.potencia)
        real = self.heroi.receber(dano)
        ditos = [
            Evento(f"{nome} usa {habilidade.nome}!", "info"),
            Evento(f"{nome} acerta {self.heroi.nome} por {real}", "dano"),
        ]
        if not self.heroi.vivo:
            ditos.append(Evento(f"{self.heroi.nome} caiu", "morte"))
        return ditos

    def _escolher(self, inimigo: Combatente) -> str | Habilidade:
        """A escolha ponderada do inimigo.

        A ponderacao e o que faz cada tipo ser diferente: e o MESMO
        sorteio com PESOS diferentes, nao logicas diferentes. Um inimigo
        que "sempre ataca quando esta inteiro" e um inimigo com peso de
        ataque altissimo e peso de cura zero sao a mesma coisa — e o
        codigo e um so.

        As opcoes entram na lista conforme FAZ SENTIDO agora: nao ha
        "cura" em vida cheia, e nao ha "defesa" depois de se defender
        vezes seguidas demais (que e o que impede a luta de empacar).
        """
        perfil = inimigo.perfil or PERFIL_ESQUELETO
        opcoes: list[tuple[float, str | Habilidade]] = [
            (perfil.peso_ataque, "ataque"),
        ]

        if inimigo.ferido and inimigo.pode_defender():
            opcoes.append((perfil.peso_defesa, "defesa"))

        if inimigo.fracao_vida <= perfil.limiar_cura and perfil.cura > 0:
            opcoes.append((perfil.peso_cura, "cura"))

        if perfil.peso_fuga > 0 and inimigo.fracao_vida <= 0.3:
            opcoes.append((perfil.peso_fuga, "fuga"))

        # As habilidades entram como opcao propria, com peso derivado do
        # ataque: elas SAO o ataque deste inimigo. Uma habilidade recarregando
        # nao entra na lista — e o que faz a recarga importar.
        for habilidade in perfil.habilidades:
            if inimigo.habilidade_liberada(habilidade):
                peso = perfil.peso_ataque * (0.5 + 0.1 * habilidade.potencia)
                opcoes.append((peso, habilidade))

        total = sum(peso for peso, _ in opcoes)
        if total <= 0:
            return "ataque"

        alvo = self.sorteio.random() * total
        acumulado = 0.0
        for peso, opcao in opcoes:
            acumulado += peso
            if alvo <= acumulado:
                return opcao
        return opcoes[-1][1]

    # --- fim ------------------------------------------------------------

    def _checar_fim(self) -> None:
        if self.concluida:
            return
        if not self.heroi_vivo:
            self.concluida = True
            self.vencida = False
            self.eventos.append(Evento("O heroi caiu", "morte"))
        elif not self.inimigos_vivos:
            self.concluida = True
            self.vencida = True
            self.eventos.append(Evento("Vitoria", "info"))

    def resumo(self) -> str:
        """Uma linha com a vida de todos, para o rodape."""
        partes = [f"{self.heroi.nome} {self.heroi.vida}/{self.heroi.vida_max}"]
        for inimigo in self.inimigos_vivos:
            partes.append(f"{inimigo.nome} {inimigo.vida}/{inimigo.vida_max}")
        return "   ".join(partes)