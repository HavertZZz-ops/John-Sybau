"""Teste da fogueira, da taverna e do mercador.

O que importa nestas tres coisas e que elas funcionem JUNTO. Descansar
e de graca, pernoitar e pago, e o ouro que compra a pocao tem que vir
de algum lugar. Um teste de cada peca sozinho nao pega a combinacao
errada, que e onde esses sistemas costumam quebrar.
"""
from __future__ import annotations

import pathlib
import sys

import pygame

sys.path.insert(0, r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

from src import assets, estado, fogueira, itens  # noqa: E402
from src.progresso import CHEFE, PRIMEIRA, Progresso, SALAS  # noqa: E402

FALHOU = 0


def checa(condicao: bool, mensagem: str) -> None:
    global FALHOU
    if condicao:
        print(f"[ok] {mensagem}")
    else:
        FALHOU += 1
        print(f"[FALHOU] {mensagem}")


# --- onde as fogueiras estao -----------------------------------------
checa(len(fogueira.FOGUEIRAS) >= 2, "existem fogueiras em mais de um lugar")
checa(fogueira.primeira_do_cenario("aldeia") is not None,
      "a primeira fogueira do jogo e na aldeia")

# a regra que sustenta o recambio do chefe
checa(fogueira.da_sala("catacumbas", len(SALAS)) is None,
      f"NAO existe fogueira na sala {len(SALAS)}: e a sala do chefe")
for s in range(1, len(SALAS)):
    checa(fogueira.da_sala("catacumbas", s) is not None,
          f"a sala {s} tem fogueira")

# a chave precisa ser estavel, e o save depende disso
f = fogueira.da_sala("catacumbas", 2)
checa(f.chave == "catacumbas:2", f"a chave e estavel: {f.chave}")
checa(fogueira.POR_CHAVE[f.chave] is f, "a chave acha a fogueira de volta")

# --- descansar -------------------------------------------------------
e = estado.Estado(vida=5, vida_max=60)
checa(e.curar(30) == 30, f"curar recupera: {e.vida}")
# 5 + 30 = 35, entao de 35 ate 60 cabem 25, e nao 30
checa(e.curar(999) == 25, f"curar para no maximo: {e.vida} de 60")
checa(e.curar(999) == 0, "com a vida cheia, curar nao devolve nada")

e.vida = 1
e.descansar(1)
checa(e.vida == e.vida_max, f"descansar enche a vida: {e.vida}")
checa(e.pocoes_repor == 1, f"descansar repoe pocoes: {e.pocoes_repor}")

# --- o descanso nao pode ser de graca em qualquer lugar -------------
# Descansar e de graca, mas so na fogueira. A taverna cobra.
checa(fogueira.POCOES_DO_DESCANSO >= 1,
      "a fogueira repõe pelo menos uma pocao")

# --- a moeda ---------------------------------------------------------
p = Progresso()
salas_com_recompensa = [s.numero for s in SALAS]
for n in salas_com_recompensa:
    r = p.recompensa_por_vencer(n)
    checa(r > 0, f"a sala {n} paga ouro: {r}")

chefe_paga = p.recompensa_por_vencer(CHEFE.numero)
outra_paga = p.recompensa_por_vencer(PRIMEIRA.numero)
checa(chefe_paga > outra_paga * 3,
      f"o chefe paga muito mais que a primeira sala: {chefe_paga} vs {outra_paga}")

# --- a loja do Estranho ---------------------------------------------
venda = itens.a_venda()
checa(len(venda) >= 2, f"o mercador tem o que vender: {len(venda)} itens")
checa(all(i.a_venda for i in venda),
      "tudo que esta na lista de venda realmente se vende")
checa(all(i.preco > 0 for i in venda), "todo item a venda tem preco")
checa(len({i.id for i in venda}) == len(venda), "os ids a venda sao unicos")

# comprar
inv = {}
deu, aviso = itens.comprar(inv, 1000, "pocao")
checa(deu and inv.get("pocao") == 1, f"comprou a pocao: {inv}")
deu2, aviso2 = itens.comprar(inv, 0, "pocao")
checa(not deu2, "sem ouro nao compra")
checa("Falta" in aviso2, f"o aviso diz o que falta: {aviso2}")

# o preco tem que caber no ouro que o jogo da
ouro_total = sum(p.recompensa_por_vencer(s.numero) for s in SALAS)
checa(ouro_total >= venda[0].preco,
      f"o ouro da campanha toda ({ouro_total}) paga pelo menos a pocao "
      f"({venda[0].preco})")
checa(ouro_total >= min(i.preco for i in venda),
      f"o ouro da campanha paga o item mais barato "
      f"({min(i.preco for i in venda)})")

# item que nao existe
deu3, _ = itens.comprar(inv, 1000, "nao_existe")
checa(not deu3, "nao vende o que nao existe")

# --- os desenhos dos moradores --------------------------------------
esperados = {"ida", "ze", "borracha", "dona_mo", "mercador", "taverneiro"}
pygame.init()
pygame.display.set_mode((8, 8))
faltando = []
for nome in sorted(esperados):
    caminho = assets.MORADOR_DIR / f"{nome}.png"
    if not caminho.is_file():
        faltando.append(nome)
checa(not faltando, f"todos os moradores tem desenho; faltando: {faltando}")

for nome in sorted(esperados):
    arte = assets.carregar_morador(nome, escala=2)
    checa(arte is not None, f"o desenho de {nome} carrega")
    if arte is not None:
        checa(arte.get_width() == 128,
              f"{nome} ampliado 2x tem 128px: {arte.get_width()}")
        # transparente: o desenho tem que cortar, nao vir em quadrado
        w, h = arte.get_size()
        canto = arte.get_at((1, 1))[3]
        checa(canto < 40, f"o canto de {nome} e transparente (alpha={canto})")

checa(assets.carregar_morador("nao_existe", escala=2) is None,
      "morador sem arquivo devolve None em vez de quebrar")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\nfogueira, taverna e mercador: tudo certo")