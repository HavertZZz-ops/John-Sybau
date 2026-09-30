"""Faz o jogo falar com o servidor Django de verdade.

Sobe o SceneManager de verdade, escolhe o store, grava um save pela
cena da masmorra e le de volta. E o caminho completo: pygame -> HTTP ->
Django -> banco.

    python tools/test_save_client.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src import assets, saves  # noqa: E402
from src.config import Config  # noqa: E402
from src.input_map import InputMap  # noqa: E402
from src.main import build_scene_manager  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402


def main() -> int:
    pygame.init()
    config = Config(width=1280, height=720, sprite_scale=3)
    assets.set_sprite_scale(config.sprite_scale)
    window = pygame.display.set_mode(config.size)
    manager = build_scene_manager(
        SceneManager(window, config, InputMap(config.bindings))
    )
    manager.ui_state.clear()

    falhas: list[str] = []

    def checar(cond: bool, desc: str) -> None:
        print(f"  {'ok  ' if cond else 'FALHA'} {desc}")
        if not cond:
            falhas.append(desc)

    print("1. o jogo escolhe o servidor quando ele responde")
    store = saves.escolher_store()
    checar(isinstance(store, saves.DjangoSaveStore),
           f"store escolhido: {store.descricao}")
    if not isinstance(store, saves.DjangoSaveStore):
        print("\no servidor nao respondeu; suba com:")
        print("  cd server; python manage.py runserver 8000")
        pygame.quit()
        return 1

    print("\n2. limpando o que tinha")
    store.apagar()

    print("\n3. o jogo grava pela cena da masmorra")
    manager.ui_state["store"] = store
    manager.switch("dungeon")
    cena = manager.active
    dt = 1 / 60
    for _ in range(int(7.0 / dt)):
        manager.update(dt)
    cena.direction = "oeste"
    cena.moving = True
    for _ in range(60):
        manager.update(dt)
    cena.moving = False
    onde = cena.posicao.copy()
    checar(manager.salvar_progresso(), "salvar_progresso() voltou True")

    print("\n4. o banco devolve o que o jogo mandou")
    lido = store.carregar()
    checar(lido is not None, "save veio do servidor")
    if lido is not None:
        checar(abs(lido.x - onde.x) < 0.01, f"x: {lido.x:.2f} == {onde.x:.2f}")
        checar(abs(lido.y - onde.y) < 0.01, f"y: {lido.y:.2f} == {onde.y:.2f}")
        checar(lido.area == "catacumbas", f"area: {lido.area}")
        checar(lido.direcao == "oeste", f"direcao: {lido.direcao}")

    print("\n5. Continuar pelo menu usa esse save")
    manager.switch("title")
    titulo = manager.active
    checar(titulo.tem_save, "menu mostra que ha save")
    checar("Continuar" in titulo._visiveis, "Continuar aparece no menu")
    titulo.index = titulo._visiveis.index("Continuar")
    titulo._activate()
    cena2 = manager.active
    checar(cena2.fase == "livre", "entrou direto no jogo, sem a abertura")
    checar(abs(cena2.posicao.x - onde.x) < 1.0,
           f"posicao voltou ({cena2.posicao.x:.0f}, {cena2.posicao.y:.0f})")
    checar(cena2.tempo_jogado > 0, f"tempo preservado: {cena2.tempo_jogado:.0f}s")

    print("\n6. Novo jogo apaga o progresso")
    manager.switch("title")
    titulo = manager.active
    titulo.index = titulo._visiveis.index("Novo jogo")
    titulo._activate()
    checar(manager.active.fase == "acordando",
           "jogo novo comeca na abertura pelo caixao")
    checar(not store.existe(), "save apagado no servidor")

    print()
    if falhas:
        print(f"FALHOU: {len(falhas)}")
        for f in falhas:
            print(f"  - {f}")
        pygame.quit()
        return 1
    print("OK: jogo e servidor de save conversando de verdade")
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())