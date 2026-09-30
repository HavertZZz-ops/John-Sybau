"""Renderiza a cidade pela cena de verdade, nao por conta propria.

Reimplementar o desenho para conferir o preview testa o preview, e nao
o jogo. Aqui a cena e instanciada e chamada de verdade.
"""
import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))

from src import assets  # noqa: E402
from src.city_scene import CityScene  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402

pygame.init()
janela = pygame.display.set_mode((1280, 720))
gerenciador = SceneManager(janela)
gerenciador.register("city", CityScene)

gerenciador.switch("city")
cena = gerenciador.active
cena.on_enter()

# centraliza a camera no grupo de moradores para o preview mostrar gente
if cena.moradores:
    pontos = [cena._posicao_de(m) for m in cena.moradores]
    centro = pontos[0].copy()
    for p in pontos[1:]:
        centro += p
    centro /= len(pontos)
    cena.camera = centro.copy()
    cena.posicao = centro + pygame.Vector2(0, cena.tile * 1.2)

gerenciador.update(1 / 60)
gerenciador.draw()
pygame.image.save(janela, str(RAIZ / "preview_cidade.png"))
print("preview_cidade.png  moradores:", len(cena.moradores))
print("nomes:", ", ".join(m.nome for m in cena.moradores))