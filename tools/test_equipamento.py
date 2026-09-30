"""Teste do equipamento: as armas, os conjuntos e a troca.

O que importa aqui e a COBERTURA. Sao cinco conjuntos, e o jogo nao
pode quebrar quando o jogador escolhe um que nao tem desenho: ele cai
no desenho padrao, nunca em um retangulo vazio.
"""
from __future__ import annotations

import pathlib
import sys

import pygame

sys.path.insert(0, r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

from src import assets, equipamento as eq, input_map  # noqa: E402
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


# --- as armas --------------------------------------------------------
for arma in ("espada", "maca", "escudo"):
    caminho = assets.ARMA_DIR / f"{arma}.png"
    checa(caminho.is_file(), f"o desenho da {arma} existe")
    if caminho.is_file():
        arte = assets.carregar_arma(arma, escala=1)
        checa(arte is not None, f"a {arma} carrega")
        if arte is not None:
            checa(arte.get_at((1, 1))[3] == 0,
                  f"a {arma} tem canto transparente")

# --- os cinco conjuntos ----------------------------------------------
conjuntos = eq.todos_os_conjuntos()
checa(len(conjuntos) == 5, f"sao cinco conjuntos: {len(conjuntos)}")

chaves = [c.chave for c in conjuntos]
checa(len(chaves) == len(set(chaves)), f"as chaves sao unicas: {chaves}")

# nenhum conjunto tem os dois estados de escudo
for c in conjuntos:
    tem_arma = c.arma is not None
    tem_escudo = c.escudo is not None
    checa(not (tem_escudo and not tem_arma) or c.arma is None,
          f"{c.chave}: escudo so vem com algo na mao")
    checa(c.rotulo and c.rotulo != "", f"{c.chave}: tem rotulo: {c.rotulo}")

# so_escudo e o conjunto sem arma, e ele PRECISA ter desenho
so_escudo = [c for c in conjuntos if c.arma is None]
checa(len(so_escudo) == 1, "existe um conjunto so com escudo")
if so_escudo:
    c = so_escudo[0]
    checa(eq.tem_desenho(c.arma, c.escudo),
          f"o conjunto {c.chave} tem desenho")

# --- cobertura: todo conjunto tem arquivo no disco -------------------
faltando = []
for c in conjuntos:
    if not (assets.EQUIP_DIR / f"{c.chave}.png").is_file():
        faltando.append(c.chave)
checa(not faltando, f"todo conjunto tem desenho; faltando: {faltando}")

for c in conjuntos:
    arte = assets.carregar_equipado(c.chave, escala=1)
    checa(arte is not None, f"o desenho de {c.chave} carrega")
    if arte is not None:
        checa(arte.get_at((1, 1))[3] == 0,
              f"{c.chave} tem canto transparente")

# --- conjunto desconhecido cai no padrao, nao no vazio -------------
checa(eq.chave_com_desenho("lamina_exotica", "escudo_rachado")
      == eq.PADRAO.chave,
      "arma e escudo desconhecidos caem no conjunto padrao")
checa(assets.carregar_equipado("inexistente_xyz", escala=1) is None,
      "desenho que nao existe devolve None, nao quebra")

# --- a troca sobrevive ao save ---------------------------------------
p = Progresso()
checa(p.arma == "espada" and p.escudo is None,
      f"o comeco e espada sem escudo: {p.arma}/{p.escudo}")

p.arma = "maca"
p.escudo = "escudo"
voltou = Progresso.de_extra(p.para_extra())
checa(voltou.arma == "maca" and voltou.escudo == "escudo",
      f"o conjunto sobrevive ao save: {voltou.arma}/{voltou.escudo}")

# save editado a mao com arma que o jogo nao conhece
sujo = Progresso.de_extra({"arma": "varinha", "escudo": "escudo_quebrado"})
checa(sujo.arma == "espada",
      f"arma desconhecida no save cai na espada: {sujo.arma}")
checa(sujo.escudo is None,
      f"escudo desconhecido no save vira nenhum: {sujo.escudo}")

# --- a tecla de trocar ----------------------------------------------
checa("trocar_equipamento" in input_map.ACTION_LABELS,
      f"existe a acao de trocar: {input_map.ACTION_LABELS.get('trocar_equipamento')}")
checa("r" in input_map.DEFAULT_BINDINGS.get("trocar_equipamento", ()),
      f"a tecla de trocar e R: "
      f"{input_map.DEFAULT_BINDINGS.get('trocar_equipamento')}")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\nequipamento: tudo certo")
