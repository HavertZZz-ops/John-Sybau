"""Teste dos moradores da cidade e do caminho ate ela.

O que importa aqui: a fuga da masmorra tem que levar a algum lugar, e
esse lugar tem que ter gente. Uma cadeia de cenas que nao chega na
cidade e um beco sem saida com texto bonito.
"""
from __future__ import annotations

import pathlib
import sys

import pygame

sys.path.insert(0, r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

from src import city_scene, input_map  # noqa: E402
from src.city_scene import MORADORES  # noqa: E402

FALHOU = 0


def checa(condicao: bool, mensagem: str) -> None:
    global FALHOU
    if condicao:
        print(f"[ok] {mensagem}")
    else:
        FALHOU += 1
        print(f"[FALHOU] {mensagem}")


# --- os moradores ----------------------------------------------------
checa(len(MORADORES) >= 3, f"a aldeia tem moradores: {len(MORADORES)}")

nomes = [m.nome for m in MORADORES]
checa(len(nomes) == len(set(nomes)), f"os nomes sao unicos: {nomes}")
checa(all(n and n[0].isupper() for n in nomes), "todo mundo tem nome proprio")

falas = [m.fala for m in MORADORES]
checa(all(f.strip() for f in falas), "todo morador tem o que dizer")
checa(len(set(falas)) == len(falas), "ninguem repete a mesma frase")
checa(all(len(f) < 70 for f in falas),
      f"as falas sao curtas: {[len(f) for f in falas]}")

# as falas nao podem ter caractere estranho: elas vao direto na tela
estranhos = {
    m.nome: sorted({c for c in m.fala if ord(c) > 0x2FF})
    for m in MORADORES
}
checa(
    not any(estranhos.values()),
    f"nenhuma fala tem caractere fora do latin: {estranhos}",
)

# dois moradores nao podem estar no mesmo offset, senao um tapa o outro
offsets = [(m.dx, m.dy) for m in MORADORES]
checa(len(offsets) == len(set(offsets)),
      f"cada morador tem seu lugar: {offsets}")

# --- o caminho inteiro esta ligado -----------------------------------
import pygame  # noqa: E402

pygame.init()
janela = pygame.display.set_mode((320, 240))

from src import main as main_mod  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402

gerenciador = main_mod.build_scene_manager(SceneManager(janela))
cenas = set(gerenciador._scenes)
for necessaria in ("dungeon", "combat", "road", "city", "title"):
    checa(necessaria in cenas, f"a cena {necessaria} esta registrada")
checa("dungeon" in cenas and "road" in cenas,
      "a fuga da masmorra tem para onde ir: masmorra -> estrada")
checa("road" in cenas and "city" in cenas,
      "a estrada leva a aldeia")

# --- a tecla de falar e a mesma de pegar ----------------------------
checa("interagir" in input_map.ACTION_LABELS,
      "a acao de interagir serve para pegar e para falar")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\nmoradores: tudo certo")
