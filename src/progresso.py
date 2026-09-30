"""O progresso da campanha: salas, mecânicas e o chefe que muda de lugar.

A masmorra deixou de ser um mapa gerado qualquer. Sao cinco salas em
ordem, e cada uma ensina UMA mecânica de combate. A ordem nao e
decorativa: a primeira mostra o golpe fraco, a ultima mostra que da
para fugir, e o jogador so encontra o chefe na saida depois de passar
por tudo antes.

O que este modulo guarda:
  - em que sala o jogador esta
  - quais salas ja foram limpas
  - se o jogador ja saiu da masmorra inteira pelo menos uma vez
  - se o chefe ja fugiu, e portanto se ele foi recambiado para a
    primeira sala

O estado inteiro vai dentro de `Save.extra`, entao nao muda o formato
do arquivo de save nem o modelo do servidor.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# --- as cinco salas, em ordem ----------------------------------------
# `fracos` existe porque a primeira sala tem que ensinar o golpe sem
# matar o jogador. Um esqueleto com a vida de um inimigo normal transforma
# a primeira aura de combate em um obstaculo, nao em uma aula.

ATAQUE = "ataque"
DEFESA = "defesa"
HABILIDADE = "habilidade"
ITEM = "item"
FUGA = "fuga"


@dataclass(frozen=True)
class Sala:
    """Uma sala da masmorra e o que ela ensina."""

    numero: int
    nome: str
    mecanica: str
    inimigos: int = 1
    fracos: bool = False
    tem_boss: bool = False
    # frase curta que a sala ensina, mostrada junto com a aula
    dica: str = ""


SALAS: tuple[Sala, ...] = (
    Sala(
        1, "Sala do Um", ATAQUE,
        inimigos=1, fracos=True,
        dica="Atacar. O golpe fraco abre a luta; nao espere sobreviver a dois.",
    ),
    Sala(
        2, "Sala do Espelho", DEFESA,
        inimigos=2,
        dica="Defender. Defender corta o dano pela metade e gasta menos tempo.",
    ),
    Sala(
        3, "Sala do Selo", HABILIDADE,
        inimigos=1,
        dica="Habilidade. O golpe forte machuca mais e custa a barra inteira.",
    ),
    Sala(
        4, "Sala da Panela", ITEM,
        inimigos=1,
        dica="Item. A pocao que voce achou cura e passa a vez.",
    ),
    Sala(
        5, "Camara Fechada", FUGA,
        inimigos=1, tem_boss=True,
        dica="Fugir. Nao da para vencer isto. Saia pela mesma porta.",
    ),
)

PRIMEIRA = SALAS[0]
CHEFE = SALAS[-1]

# A masmorra tem cinco salas. A SEXTA e fora: e a estrada que leva a
# cidade. "Sair da masmorra" e chegar na sexta, nao terminar a quinta.
SAIDA = 6


@dataclass
class Progresso:
    """Estado da campanha. Tudo que o save precisa saber."""

    cenario: str = "catacumbas"
    sala: int = 1
    # salas ja vencidas, para o jogador nao refazer a aula
    vencidas: list[int] = field(default_factory=list)
    # chefe que o jogador ja fugiu uma vez
    chefe_fugiu: bool = False
    # quantas vezes o jogador SAIU da masmorra, ou seja, chegou na
    # sala 6. Este e o portao do recambio do chefe, e nao a quinta sala
    vezes_saida: int = 0
    # itens no bolso: {"pocao": 1}
    itens: dict[str, int] = field(default_factory=dict)
    # para onde o mundo exterior esta liberado: "masmorra", "estrada", "cidade"
    mundo: str = "masmorra"

    # --- consultas --------------------------------------------------
    def sala_atual(self) -> Sala:
        for sala in SALAS:
            if sala.numero == self.sala:
                return sala
        return PRIMEIRA

    def concluida(self, numero: int) -> bool:
        return numero in self.vencidas

    def ja_saiu_da_masmorra(self) -> bool:
        """True depois de chegar na sala 6 pelo menos uma vez.

        E o portao do recambio do chefe. Sem esta flag o chefe volta
        para a quinta sala em toda visita, e o jogador nunca ve o que
        a propria regra promete.
        """
        return self.vezes_saida >= 1

    def onde_esta_o_chefe(self) -> int:
        """Em que sala o chefe esta.

        O chefe comeca na quinta, a ultima da masmorra, e e forte demais
        para quem esta aprendendo a fugir.

        Depois que o jogador FUGIU e JA SAIU da masmorra pelo menos uma
        vez, o chefe deixa a quinta e passa a estar na PRIMEIRA, que e
        onde o jogador nasce dentro da masmorra. Uma condicao sem a
        outra nao move o chefe.
        """
        if self.ja_saiu_da_masmorra() and self.chefe_fugiu:
            return PRIMEIRA.numero
        return CHEFE.numero

    def tem_pocao(self) -> bool:
        return self.itens.get("pocao", 0) > 0

    def usar_pocao(self) -> bool:
        if not self.tem_pocao():
            return False
        self.itens["pocao"] -= 1
        if self.itens["pocao"] <= 0:
            del self.itens["pocao"]
        return True

    # --- eventos ----------------------------------------------------
    def vencer(self, numero: int) -> None:
        if numero not in self.vencidas:
            self.vencidas.append(numero)
            self.vencidas.sort()

    def fugir_do_chefe(self) -> None:
        self.chefe_fugiu = True

    def sair_da_masmorra(self) -> None:
        """Chegou na sala 6. Vale tanto por fuga quanto por vitoria."""
        self.vezes_saida += 1
        if self.mundo == "masmorra":
            self.mundo = "estrada"

    def avancar(self) -> int:
        """Proxima sala ainda nao vencida, ou a ultima se todas foram."""
        for sala in SALAS:
            if sala.numero not in self.vencidas:
                self.sala = sala.numero
                return sala.numero
        self.sala = CHEFE.numero
        return self.sala

    def e_sala_do_chefe(self, numero: int | None = None) -> bool:
        n = self.sala if numero is None else numero
        return n == self.onde_esta_o_chefe()

    # --- save -------------------------------------------------------
    def para_extra(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_extra(cls, bruto: Any) -> "Progresso":
        """Le do save sem nunca levantar excecao.

        Um save vem do disco e pode ter sido editado a mao, ou ser de
        uma versao antiga sem nenhum destes campos. Um erro aqui
        derrubaria o jogo no menu, que e o pior lugar possivel.
        """
        padrao = cls()
        if not isinstance(bruto, dict):
            return padrao

        limpo = {k: v for k, v in bruto.items() if k in cls.__dataclass_fields__}

        try:
            sala = int(limpo.get("sala", padrao.sala))
        except (TypeError, ValueError):
            sala = padrao.sala
        # uma sala fora da faixa deixaria o jogador preso num numero
        # que nao existe no jogo
        if not any(s.numero == sala for s in SALAS):
            sala = padrao.sala

        vencidas = [
            n for n in (limpo.get("vencidas") or [])
            if isinstance(n, int) and any(s.numero == n for s in SALAS)
        ]
        itens = {
            str(k): int(v)
            for k, v in (limpo.get("itens") or {}).items()
            if isinstance(v, int) and v > 0
        }
        completada = limpo.get("vezes_saida", 0)
        if not isinstance(completada, int) or completada < 0:
            completada = 0
        mundo = limpo.get("mundo", padrao.mundo)
        if mundo not in ("masmorra", "estrada", "cidade"):
            mundo = padrao.mundo

        return cls(
            cenario=str(limpo.get("cenario", padrao.cenario)),
            sala=sala,
            vencidas=sorted(set(vencidas)),
            chefe_fugiu=bool(limpo.get("chefe_fugiu", False)),
            vezes_saida=completada,
            itens=itens,
            mundo=mundo,
        )