"""Abre os menus com a arte nova e tira a foto.

Roda a cena de verdade, abre o inventario, a loja e o equipamento, e
salva uma imagem de cada. Um painel que nao abre, ou que abre
cortado, so aparece na foto.
"""
import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))

from src import assets  # noqa: E402
from src.city_scene import CityScene  # noqa: E402
from src.dungeon_scene import DungeonScene  # noqa: E402
from src.main import build_scene_manager, create_window  # noqa: E402
from src.progresso import Progresso  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402

# Os menus foram fotografados com `Config()` cru, que abre em 1280x720.
# O jogo do jogador roda em 1008x720 com `sprite_scale` 3, e um painel
# medido em uma resolucao corta diferente na outra. A foto tem de ser
# da resolucao de quem joga.
sys.path.insert(0, str(RAIZ / "tools"))
from preview_real import config_real  # noqa: E402

L, A = pygame.Surface.convert_alpha, pygame.event.Event


def kd(k):
    return A(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)


def ku(k):
    return A(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0)


def teclar(ger, k):
    ger.active.handle_event(kd(k))
    ger.active.handle_event(ku(k))


pygame.init()
CONFIG = config_real()
assets.set_sprite_scale(CONFIG.sprite_scale)
janela = create_window(CONFIG)
ger = build_scene_manager(SceneManager(janela, CONFIG))
ger.ui_state.clear()
print(f"config da foto: {CONFIG.width}x{CONFIG.height}, "
      f"sprite_scale {CONFIG.sprite_scale}")

p = Progresso()
p.itens["pocao"] = 2
p.itens["pocao_forte"] = 1
ger.ui_state["progresso"] = p
ger.ui_state["estado"] = __import__(
    "src.estado", fromlist=["Estado"]).Estado(vida=30, ouro=520)

ger.switch("city")
cena = ger.active
cena.on_enter()

print("--- inventario (Q) ---")
teclar(ger, pygame.K_q)
ger.update(1 / 60)
ger.draw()
pygame.image.save(janela, str(RAIZ / "preview_menu_inventario.png"))
print("  salvo")

print("--- loja do Estranho ---")
# vai ate o Estranho
cena.perto = next((m for m in cena.moradores if m.nome == "O Estranho"), None)
teclar(ger, pygame.K_e)
ger.update(1 / 60)
ger.draw()
print(f"  loja aberta: {cena.loja}")
pygame.image.save(janela, str(RAIZ / "preview_menu_loja.png"))

print("--- equipamento (Q depois R) ---")
# NAO usar ESC aqui. O update() recalcula a proximidade e zera `perto`,
# entao o ESC com a loja aberta era lido como "sair da aldeia" e
# trocava a cena no meio da foto. O proprio Q ja fecha a loja.
teclar(ger, pygame.K_q)
teclar(ger, pygame.K_r)
ger.update(1 / 60)
ger.draw()
print(f"  modo_equip: {cena.modo_equip}")
if cena.modo_equip is None:
    print("  FALHOU: o R nao abriu o submenu de equipamento")
pygame.image.save(janela, str(RAIZ / "preview_menu_equipamento.png"))

print("\npronto")