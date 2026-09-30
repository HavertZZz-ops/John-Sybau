"""Teste do ciclo da fuga do chefe.

O caminho que importa: o jogador chega na sala do chefe, luta, escolhe
fugir, e isso o tira da masmorra. Sem isso, "fugir" era so um estado
marcado e o jogador voltava para o mesmo lugar com o chefe de novo na
frente.
"""
from __future__ import annotations

import pathlib
import sys

import pygame

sys.path.insert(0, r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

from src import combat, progresso  # noqa: E402
from src.progresso import CHEFE, PRIMEIRA, Progresso  # noqa: E402

FALHOU = 0


def checa(condicao: bool, mensagem: str) -> None:
    global FALHOU
    if condicao:
        print(f"[ok] {mensagem}")
    else:
        FALHOU += 1
        print(f"[FALHOU] {mensagem}")


# --- o chefe e forte, e e forte de um jeito especifico ---------------
# Cada bloco cria o seu proprio chefe. Reusar o mesmo objeto faz a
# luta anterior alterar a vida do chefe da luta seguinte, e o teste
# passa a medir o estrago do teste, nao o do jogo.
chefe = combat.novo_chefe()
fraco = combat.novo_esqueleto(0)

checa(chefe.vida > fraco.vida * 3,
      f"o chefe tem muito mais vida que um esqueleto ({chefe.vida} vs {fraco.vida})")
checa(chefe.defesa > fraco.defesa, "o chefe defende mais")
checa(chefe.forca > fraco.forca * 2, "o chefe bate muito mais forte")
checa(chefe.velocidade_barra > fraco.velocidade_barra,
      "a barra do chefe enche mais rapido que a do esqueleto")
checa(chefe.nome == "O Cobrador", f"o chefe tem nome: {chefe.nome}")

# --- fugir e uma opcao, nao um caminho obrigatorio -------------------
b = combat.Batalha(heroi=combat.novo_heroi(), inimigos=[chefe])
b.turno_heroi = True
acoes = [a.value for a in combat.Acao]
checa("Fugir" in acoes, f"Fugir esta no menu: {acoes}")
checa("Atacar" in acoes and "Defender" in acoes,
      "fugir NAO substitui as outras acoes: continua havendo como lutar")

# o heroi pode escolher lutar: atacar funciona normalmente
b2 = combat.Batalha(heroi=combat.novo_heroi(),
                    inimigos=[combat.novo_chefe()])
b2.turno_heroi = True
alvo = b2.inimigos[0]
b2.acao_do_heroi(combat.Acao.ATACAR)
checa(alvo.vida < alvo.vida_max, "atacar o chefe funciona: ele leva dano")
checa(not b2.fugiu, "atacar nao marca fuga")

# e pode escolher fugir
b3 = combat.Batalha(heroi=combat.novo_heroi(),
                    inimigos=[combat.novo_chefe()])
b3.turno_heroi = True
vida_heroi = b3.heroi.vida
alvo3 = b3.inimigos[0]
vida_chefe = alvo3.vida
eventos = b3.acao_do_heroi(combat.Acao.FUGIR)
checa(b3.fugiu, "a acao Fugir marca a fuga")
checa(b3.concluida, "a fuga encerra a luta")
checa(not b3.vencida, "fugir nao conta como vitoria")
checa(b3.heroi.vida == vida_heroi,
      f"fugir nao custa vida: {b3.heroi.vida} de {vida_heroi}")
checa(alvo3.vida == vida_chefe,
      f"fugir nao machuca o inimigo: {alvo3.vida} de {vida_chefe}")
# "fug" nao esta em "foge": sao palavras diferentes, e o teste passa
# pela palavra inteira e nao por um pedaco escolhido a mao
checa(any("foge" in e.texto.lower() for e in eventos),
      f"a fuga aparece no log: {[e.texto for e in eventos]}")

# --- o ciclo: fugir do chefe tira o jogador da masmorra -------------
p = Progresso()
checa(p.onde_esta_o_chefe() == CHEFE.numero,
      "antes de fugir, o chefe esta na ultima sala")
p.fugir_do_chefe()
p.sair_da_masmorra()
checa(p.onde_esta_o_chefe() == PRIMEIRA.numero,
      "depois de fugir e sair, o chefe espera na primeira sala")
checa(p.mundo == "estrada", "o jogador esta na estrada")

# e se ele voltar e fugir de novo, continua funcionando
p2 = Progresso()
p2.fugir_do_chefe()
p2.sair_da_masmorra()
checa(p2.onde_esta_o_chefe() == PRIMEIRA.numero, "o recambio e estavel")
p2.sair_da_masmorra()
checa(p2.onde_esta_o_chefe() == PRIMEIRA.numero,
      "sair de novo nao joga o chefe de volta para a ultima sala")
checa(p2.vezes_saida == 2, f"contar as saidas: {p2.vezes_saida}")

# --- o estado sobrevive ao save -------------------------------------
ida = Progresso()
ida.fugir_do_chefe()
ida.sair_da_masmorra()
voltou = Progresso.de_extra(ida.para_extra())
checa(voltou == ida, "a regra do chefe sobrevive ao save")
checa(voltou.onde_esta_o_chefe() == PRIMEIRA.numero,
      "depois de carregar o save, o chefe continua na primeira sala")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\nfuga do chefe: tudo certo")
