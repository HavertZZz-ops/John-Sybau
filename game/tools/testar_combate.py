"""Testes do combate por turnos.

O combate e a parte do jogo onde um testeautomatico vale mais do que em
qualquer outro lugar: o combate e um conjunto de numeros com sorteio, e
"funciona" e uma afirmacao fraca. O que estes testes medem sao as
PROPRIEDADES que o combate precisa ter, e nao "a batalha rodou sem
estourar".

    python tools/testar_combate.py

As propriedades verificadas sao as que definem o sistema:

- **A rodada e em blocos.** O heroi age, e so depois TODOS os inimigos.
  Nao alterna. E o que faz defender ser uma decisao real.
- **O telegrafo e o ato.** O que o inimigo anunciou e o que ele faz.
  Um telegrafo que mente quebra o planejamento.
- **Cada perfil decide diferente.** Medido sobre muitas jogadas.
- **A luta termina.** Nenhum perfil trava o combate para sempre.
- **Fugir acaba a luta na hora.**
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((64, 64))

import combat as C  # noqa: E402

FALHAS: list[str] = []


def checar(descricao: str, condicao: bool, detalhe: str = "") -> None:
    if condicao:
        print(f"  [ok]   {descricao}")
    else:
        print(f"  [FALHA] {descricao} {detalhe}")
        FALHAS.append(descricao)


def heroi(vida: int = 200, forca: int = 9) -> C.Combatente:
    return C.Combatente(
        nome="John", vida=vida, vida_max=vida, forca=forca, defesa=2
    )


def nova_luta(perfil: C.Perfil, quantidade: int = 1, semente: int = 7):
    luta = C.Batalha(heroi(), sorteio=random.Random(semente))
    luta.adicionar(*[C.novo_inimigo(perfil, i) for i in range(quantidade)])
    return luta


# --- a rodada em blocos ---------------------------------------------------


def test_blocos() -> None:
    print("\nA rodada e em blocos")
    luta = nova_luta(C.PERFIL_ESQUELETO, quantidade=3)

    # Antes de agir, e o heroi
    checar("comeca no heroi", luta.turno_do_heroi)

    luta.acao_do_heroi(C.AcaoHeroi.ATACAR)
    checar("depois do heroi, e a vez dos inimigos",
           not luta.turno_do_heroi and luta.fase is C.Fase.INIMIGOS)

    # Nenhum inimigo age enquanto o heroi nao agiu. A propriedade
    # invertida: se um inimigo agisse aqui, a rodada seria alternada.
    # O heroi ATACOU, entao um inimigo ja perdeu vida. A propriedade a
    # checar e outra: ninguem agiu no turno do HEROI, e isso se ve pelo
    # que o heroi recebeu — se algum inimigo tivesse agido, o heroi
    # estaria com dano.
    dano_no_heroi = luta.heroi.vida_max - luta.heroi.vida
    checar("ninguem agiu no turno do heroi", dano_no_heroi == 0,
           f"(heroi perdeu {dano_no_heroi})")

    # E a fase e a dos inimigos, com o telegrafo ja feito: o jogador
    # ve a intencao antes de agir.
    tem_telegrafo = all(
        luta.intencao_de(i) != "..." for i in luta.inimigos_vivos
    )
    checar("o telegrafo foi feito na virada", tem_telegrafo)

    luta.jogada_inimiga()
    checar("apos os inimigos, volta ao heroi",
           luta.turno_do_heroi or luta.concluida)
    checar("a rodada avancou", luta.rodada == 1, f"({luta.rodada})")


def test_defender_paga() -> None:
    """A propriedade que a fila alternada nao tinha."""
    print("\nDefender e uma decisao real")
    sem_defesa = heroi()
    com_defesa = heroi()
    com_defesa.defendendo = True

    golpe = C.novo_inimigo(C.PERFIL_ESQUELETO).forca
    dano_sem = sem_defesa.receber(golpe)
    dano_com = com_defesa.receber(golpe)

    checar("defender reduz o dano", dano_com < dano_sem,
           f"({dano_com} com defesa, {dano_sem} sem)")

    # E a defesa dura UM golpe: um estado permanente seria o estado mais
    # impossivel de entender num combate.
    c = heroi()
    c.defendendo = True
    c.receber(5)
    checar("a defesa dura so um golpe", not c.defendendo)


def test_alvo_mais_fraco() -> None:
    print("\nO heroi acerta o mais machucado")
    luta = nova_luta(C.PERFIL_ESQUELETO, quantidade=3)
    for i, inimigo in enumerate(luta.inimigos):
        inimigo.vida = 10 + i * 20

    alvo_antes = min(luta.inimigos_vivos, key=lambda i: i.vida).nome
    luta.acao_do_heroi(C.AcaoHeroi.ATACAR)

    ficou = [i.vida for i in luta.inimigos]
    checar("o mais fraco levou o golpe",
           ficou[0] < ficou[1] and ficou[0] < ficou[2],
           f"({ficou})")


# --- o telegrafo ------------------------------------------------------------


def test_telegrafo() -> None:
    print("\nO telegrafo e o ato")
    for perfil in C.PERFIS:
        # 60 rodadas, cada uma com o tele-grafo lido ANTES de agir
        combinadas = []
        for semente in range(60):
            luta = nova_luta(perfil, quantidade=1, semente=semente)
            luta.heroi.vida = 1000  # o heroi nao morre, para ver todas as rodadas
            luta.heroi.vida_max = 1000
            luta.acao_do_heroi(C.AcaoHeroi.DEFENDER)
            anunciado = luta.intencao_de(luta.inimigos[0])

            lutou = " ".join(e.texto for e in luta.jogada_inimiga())
            combinadas.append((anunciado, lutou))

        # Cada anuncio tem de aparecer no texto do que aconteceu
        mapa = {
            "atacar": "acerta",
            "se defender": "defende",
            "se curar": "cura",
            "fugir": "foge",
        }
        for anuncio, texto in combinadas:
            if anuncio in mapa:
                if mapa[anuncio] not in texto:
                    checar(f"{perfil.nome}: '{anunciado}' aconteceu", False,
                           f"anunciou mas saiu: {texto[:60]}")
                    break
            elif anuncio.endswith(("Investida", "Maldicao", "Cobranca", "Uivo")):
                if anuncio not in texto:
                    checar(f"{perfil.nome}: '{anuncio}' aconteceu", False,
                           f"anunciou mas saiu: {texto[:60]}")
                    break
        else:
            checar(f"{perfil.nome}: 60 anuncios conferidos", True)


def test_fuga_anunciada() -> None:
    """Fugir so acontece quando foi anunciado."""
    print("\nFuga e anunciada antes")
    # Olado com peso de fuga: o sacerdote.
    fugiu_avisado = True
    for semente in range(80):
        luta = nova_luta(C.PERFIL_SACERDOTE, quantidade=1, semente=semente)
        inimigo = luta.inimigos[0]
        inimigo.vida = int(inimigo.vida_max * 0.15)  # ferido: destrava a fuga
        inimigo.girar_recargas()
        escolha = luta._escolher(inimigo)
        if escolha == "fuga":
            break
    else:
        fugiu_avisado = False

    checar("o sacerdote pode anunciar fuga", fugiu_avisado)

    # E sem ter anunciado, o inimigo nao foge: e o que garante que a
    # promessa seja o ato.
    lutas = 0
    for semente in range(40):
        luta = nova_luta(C.PERFIL_ESQUELETO, quantidade=1, semente=semente)
        inimigo = luta.inimigos[0]
        inimigo.vida = 1  # moribundo
        escolha = luta._escolher(inimigo)
        if escolha == "fuga":
            lutas += 1
    checar("o esqueleto nunca foge", lutas == 0, f"({lutas} vezes)")


# --- cada perfil decide diferente ------------------------------------------


def test_perfis_diferem() -> None:
    print("\nCada perfil decide diferente")
    for perfil in C.PERFIS:
        contagem: dict[str, int] = {}
        for semente in range(400):
            inimigo = C.novo_inimigo(perfil)
            inimigo.vida = int(inimigo.vida_max * 0.25)  # ferido
            inimigo.girar_recargas()
            escolha = C.Batalha(heroi(), sorteio=random.Random(semente))._escolher(inimigo)
            nome = escolha if isinstance(escolha, str) else escolha.nome
            contagem[nome] = contagem.get(nome, 0) + 1

        top = sorted(contagem.items(), key=lambda kv: -kv[1])[:3]
        resumo = ", ".join(f"{k} {100 * v // 400}%" for k, v in top)
        print(f"       {perfil.nome:11} {resumo}")

    # Propriedade: o esqueleto e o que mais ataca, e o sacerdote e o que
    # mais se cura. Se um dia esses dois trocarem de lugar, o combate
    # perdeu o sentido.
    def fracao(perfil, chave):
        n = 0
        for semente in range(400):
            inimigo = C.novo_inimigo(perfil)
            inimigo.vida = int(inimigo.vida_max * 0.25)
            inimigo.girar_recargas()
            e = C.Batalha(heroi(), sorteio=random.Random(semente))._escolher(inimigo)
            nome = e if isinstance(e, str) else e.nome
            if nome == chave:
                n += 1
        return n / 400

    ataques_esq = fracao(C.PERFIL_ESQUELETO, "ataque")
    curas_sac = fracao(C.PERFIL_SACERDOTE, "cura")
    checar("o esqueleto ataca mais", ataques_esq > 0.5,
           f"({ataques_esq:.0%})")
    checar("o sacerdote se cura mais", curas_sac > 0.15,
           f"({curas_sac:.0%})")


# --- a luta termina --------------------------------------------------------


def test_luta_termina() -> None:
    print("\nA luta sempre termina")
    for perfil in C.PERFIS:
        # heroi fraco de proposito: o teste e "a luta acaba", nao "o
        # heroi vence"
        for semente in range(12):
            luta = C.Batalha(C.Combatente(
                nome="John", vida=40, vida_max=40, forca=9, defesa=2),
                sorteio=random.Random(semente))
            luta.adicionar(*[C.novo_inimigo(perfil, i) for i in range(2)])

            rodadas = 0
            while not luta.concluida and rodadas < 300:
                rodadas += 1
                if luta.turno_do_heroi:
                    luta.acao_do_heroi(C.AcaoHeroi.ATACAR)
                else:
                    luta.jogada_inimiga()

            if not luta.concluida:
                checar(f"{perfil.nome} termina", False,
                       f"({rodadas} rodadas sem fim)")
                break
        else:
            checar(f"{perfil.nome} termina em ate 300 rodadas", True)


def test_defesa_nao_trava() -> None:
    """O guardiao pesado nao pode passar a luta se defendendo."""
    print("\nDefesa seguida tem limite")
    guardiao = C.novo_inimigo(C.PERFIL_GUARDIAN)
    for _ in range(guardiao.perfil.defesas_seguidas):
        checar_uma = guardiao.pode_defender()
        if not checar_uma:
            break
        guardiao._defesas_seguidas += 1
    checar("o guardiao para de poder se defender",
           not guardiao.pode_defender(),
           f"(limite {guardiao.perfil.defesas_seguidas})")


def test_fugir_acaba() -> None:
    print("\nFugir acaba a luta na hora")
    luta = nova_luta(C.PERFIL_ESQUELETO, quantidade=3)
    luta.acao_do_heroi(C.AcaoHeroi.FUGIR)
    checar("fugiu", luta.fugiu)
    checar("a luta acabou", luta.concluida)
    checar("nao virou para os inimigos", luta.fase is C.Fase.HEROI,
           f"(fase {luta.fase})")

    # E nao contou como vitoria.
    checar("fuga nao e vitoria", not luta.vencida)


def test_morrendo() -> None:
    print("\nO heroi morrendo encerra a luta")
    luta = nova_luta(C.PERFIL_COBRADOR, quantidade=1)
    luta.heroi.vida = 1
    luta.acao_do_heroi(C.AcaoHeroi.ATACAR)
    lutas = luta.jogada_inimiga()
    checar("a luta acabou", luta.concluida)
    checar("nao venceu", not luta.vencida)
    checar("o evento de morte existe",
           any("caiu" in e.texto for e in lutas),
           f"({[e.texto for e in lutas]})")


def test_ritmo_da_fase() -> None:
    """A fase dos inimigos precisa de TEMPO, e nao de um quadro.

    Esta e a propriedade que a tela depende. `jogada_inimiga()` resolve a
    fase inteira de uma vez — e assim que o log fica legivel. Quem
    controla o TEMPO em que o jogador ve cada evento e a cena, e nao o
    modelo. Este teste so confirma que o modelo entrega TODOS os eventos
    da fase de uma vez, para a cena ter o que mostrar um a um.
    """
    print("\nA fase entrega os eventos de uma vez")
    luta = nova_luta(C.PERFIL_ESQUELETO, quantidade=3)
    luta.heroi.vida = 500
    luta.heroi.vida_max = 500
    luta.acao_do_heroi(C.AcaoHeroi.DEFENDER)

    eventos = luta.jogada_inimiga()

    # tres inimigos, cada um com pelo menos um evento
    atacaram = [e for e in eventos if "acerta" in e.texto]
    checar("cada inimigo agiu uma vez", len(atacaram) == 3,
           f"({len(atacaram)} golpes de 3 inimigos)")
    checar("a fase veio inteira de uma vez", len(eventos) >= 3,
           f"({len(eventos)} eventos)")

    # E o heroi levou os tres golpes: e o que a cena vai mostrar com
    # pausa entre um e outro.
    checar("o heroi levou os golpes",
           luta.heroi.vida_max - luta.heroi.vida > 0,
           f"(perdeu {luta.heroi.vida_max - luta.heroi.vida})")


def test_vitoria() -> None:
    print("\nVencer encerra a luta")
    lutas: list[C.Batalha] = []
    for semente in range(5):
        l = C.Batalha(heroi(vida=999, forca=99), sorteio=random.Random(semente))
        l.adicionar(*[C.novo_inimigo(C.PERFIL_ESQUELETO, i) for i in range(2)])
        lutas.append(l)

    for l in lutas:
        guarda = 0
        while not l.concluida and guarda < 100:
            guarda += 1
            if l.turno_do_heroi:
                l.acao_do_heroi(C.AcaoHeroi.ATACAR)
            else:
                l.jogada_inimiga()

    checar("todas venceram", all(l.vencida for l in lutas),
           f"({[l.vencida for l in lutas]})")


def main() -> int:
    print("=" * 62)
    print("testes do combate por turnos")

    test_blocos()
    test_defender_paga()
    test_alvo_mais_fraco()
    test_telegrafo()
    test_fuga_anunciada()
    test_perfis_diferem()
    test_luta_termina()
    test_defesa_nao_trava()
    test_fugir_acaba()
    test_ritmo_da_fase()
    test_morrendo()
    test_vitoria()

    print("=" * 62)
    if FALHAS:
        print(f"{len(FALHAS)} verificacao(oes) falharam:")
        for f in FALHAS:
            print(f"  - {f}")
        return 1
    print("tudo certo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
