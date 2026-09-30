"""Teste do item na luta e das aulas por sala.

O caminho que importa: o jogador acha a pocao no chao, pega com E, o
inimigo aparece, e dentro da luta o jogo ensina a chegar em USAR ITEM,
abrir o inventario e curar. Cada passo e verificado, porque cada um
deste passos ja falhou sozinho em algum momento.
"""
from __future__ import annotations

import pathlib
import sys

import pygame

sys.path.insert(0, r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

from src import combat, input_map, itens, progresso  # noqa: E402
from src.progresso import Progresso  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))

FALHOU = 0


def checa(condicao: bool, mensagem: str) -> None:
    global FALHOU
    if condicao:
        print(f"[ok] {mensagem}")
    else:
        FALHOU += 1
        print(f"[FALHOU] {mensagem}")


# --- a acao existe no menu, ao lado das outras ----------------------
acoes = [a.name for a in combat.Acao]
checa("ITEM" in acoes, f"a acao ITEM existe: {acoes}")
checa("ATACAR" in acoes and "DEFENDER" in acoes and "FUGIR" in acoes,
      "usar item NAO substitui as outras acoes")

# --- a pocao cura e custa a vez --------------------------------------
h = combat.novo_heroi()
h.vida = 10
b = combat.Batalha(heroi=h, inimigos=[combat.novo_esqueleto(0)])
b.turno_heroi = True
barra_antes = b.heroi.barra.valor
# a barra comeca em zero, e gastar de zero nao muda nada: sem encher
# antes, o teste passaria com o custo do item quebrado
b.heroi.barra.valor = 60.0
barra_antes = b.heroi.barra.valor
b.item_escolhido = "pocao"
ev = b.acao_do_heroi(combat.Acao.ITEM)

checa(b.heroi.vida > 10, f"a pocao curou: {b.heroi.vida} de {h.vida_max}")
checa(b.heroi.vida == 40, f"a pocao cura 30 de vida: ficou {b.heroi.vida}")
checa(b.heroi.barra.valor < barra_antes,
      f"usar item gasta a barra: {b.heroi.barra.valor} de {barra_antes}")
checa(not b.turno_heroi, "usar item passa a vez")
checa(any("curou" in e.texto for e in ev),
      f"o log diz que curou: {[e.texto for e in ev]}")

# vida cheia: o item some do jogo, mas o turno NAO passa
b2 = combat.Batalha(heroi=combat.novo_heroi(), inimigos=[combat.novo_esqueleto(0)])
b2.turno_heroi = True
b2.item_escolhido = "pocao"
ev2 = b2.acao_do_heroi(combat.Acao.ITEM)
checa("vida cheia" in " ".join(e.texto for e in ev2),
      f"vida cheia avisa e nao gasta a vez: {[e.texto for e in ev2]}")
checa(b2.turno_heroi, "com a vida cheia o turno continua sendo do jogador")

# sem item escolhido, nada acontece
b3 = combat.Batalha(heroi=combat.novo_heroi(), inimigos=[combat.novo_esqueleto(0)])
b3.turno_heroi = True
antes = b3.heroi.vida
b3.acao_do_heroi(combat.Acao.ITEM)
checa(b3.heroi.vida == antes, "sem item escolhido nao cura ninguem")
checa(b3.turno_heroi, "sem item escolhido o turno nao passa")

# --- o inventario ---------------------------------------------------
checa(itens.tem_usaveis({"pocao": 1}), "com pocao ha usaveis")
checa(not itens.tem_usaveis({}), "sem nada nao ha usaveis")
checa(not itens.tem_usaveis({"pocao": 0}), "pocao com zero nao e usavel")
linhas = itens.rotulos({"pocao": 2, "item_que_nao_existe": 5})
checa(len(linhas) == 1, f"o inventario ignora item desconhecido: {linhas}")
checa(linhas[0][0] == "pocao" and linhas[0][2] == 2,
      f"a linha traz o id e a quantidade: {linhas[0][0]} x{linhas[0][2]}")

# o inventario NUNCA mostra o que o jogador nao tem
checa(itens.rotulos({}) == [], "inventario vazio nao mostra linha nenhuma")
checa(itens.rotulos({"pocao": -3}) == [],
      "quantidade negativa nao vira item usavel")

# --- a pocao no chao -------------------------------------------------
p = Progresso()
checa(not p.tem_pocao(), "comeca sem pocao")
p.itens["pocao"] = 1
checa(p.tem_pocao(), "pegou a pocao")
checa(p.usar_pocao(), "consegue usar")
checa(not p.tem_pocao(), "a pocao acabou")
checa(not p.usar_pocao(), "nao da para usar a mesma pocao duas vezes")

# --- as aulas por sala -----------------------------------------------
ensina = progresso.ENSINA_COMBATE
checa(len(ensina) == len(progresso.SALAS),
      f"toda sala tem uma acao a ensinar: {len(ensina)} de {len(progresso.SALAS)}")
checa(ensina[1] == "ATACAR", "sala 1 ensina a atacar")
checa(ensina[2] == "DEFENDER", "sala 2 ensina a defender")
checa(ensina[3] == "HABILIDADE", "sala 3 ensina a habilidade")
checa(ensina[4] == "ITEM", "sala 4 ensina a usar item")
checa(ensina[5] == "FUGIR", "sala 5 ensina a fugir")
for numero, acao in ensina.items():
    existe = hasattr(combat.Acao, acao)
    checa(existe, f"a acao ensinada na sala {numero} existe no combate: {acao}")

# --- a tecla de interagir --------------------------------------------
checa("interagir" in input_map.ACTION_LABELS,
      f"existe a acao interagir: {input_map.ACTION_LABELS.get('interagir')}")
checa("e" in input_map.DEFAULT_BINDINGS.get("interagir", ()),
      f"a tecla de interagir e E: {input_map.DEFAULT_BINDINGS.get('interagir')}")
checa("interagir" in input_map.ACTION_LABELS
      and input_map.ACTION_GROUPS["interagir"] == input_map.GROUP_TECLAS,
      "interagir aparece na aba de teclas das opcoes")

# toda acao precisa de tecla, senao o remapear quebra
sem_tecla = [a for a, _l, _g, teclas in input_map.ACTION_LIST if not teclas]
checa(not sem_tecla, f"toda acao tem pelo menos uma tecla; sem: {sem_tecla}")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\nitens e aulas: tudo certo")
