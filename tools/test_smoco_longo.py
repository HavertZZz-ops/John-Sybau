"""Sessao longa apertando tecla, em todas as cenas.

O crash que derrubava o jogo foi achado assim: `--frames 900` passava
limpo e `--frames 3600` quebrava. O jogo nao quebrava no primeiro
segundo, e sim quando o jogador chegava numa cena depois de andar um
pouco. Nenhum teste headless curto alcanca esse ponto.

Aqui o jogo roda de verdade e recebe TECLAS: Q, R, E, F5, as setas, o
enter, em todas as cenas, durante muitos segundos simulados. E o que
acha caminho que nenhum outro teste pega.
"""
from __future__ import annotations

import pathlib
import random
import sys
import traceback

import pygame

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.main import build_scene_manager, create_window  # noqa: E402
from src.scene_manager import SceneManager  # noqa: E402
from src.settings import TILES_DIR  # noqa: E402,F401

TECLAS_MENU = [
    pygame.K_q, pygame.K_r, pygame.K_e, pygame.K_ESCAPE,
    pygame.K_RETURN, pygame.K_SPACE,
]
TECLAS_JOGO = [
    pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d,
    pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
]
TECLAS_RISCO = [
    pygame.K_F5, pygame.K_F5, pygame.K_ESCAPE, pygame.K_ESCAPE,
    pygame.K_q, pygame.K_r, pygame.K_e,
]

CENAS = ("dungeon", "road", "city", "combat", "title")


def keydown(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="",
                              scancode=0)


def keyup(k):
    return pygame.event.Event(pygame.KEYUP, key=k, mod=0, unicode="",
                              scancode=0)


def uma_tecla(manager, k) -> None:
    if manager.active is None:
        return
    manager.active.handle_event(keydown(k))
    manager.active.handle_event(keyup(k))


def martelar(manager, teclas: list, passos: int) -> None:
    """Aperta as teclas em rodizio, com update e draw, por N passos."""
    dt = 1 / 60
    rng = random.Random(4242)
    for passo in range(passos):
        uma_tecla(manager, teclas[passo % len(teclas)])
        manager.update(dt)
        if passo % 5 == 0:
            manager.draw()


def main() -> int:
    from src.config import Config

    pygame.init()
    config = Config()
    window = create_window(config)
    manager = build_scene_manager(SceneManager(window, config))
    manager.ui_state.clear()

    crashes: list[str] = []
    visitadas: set[str] = set()
    teclas_total = 0
    rng = random.Random(20260930)
    dt = 1 / 60

    def registrar(passo: int, onde: str, erro_txt: str) -> None:
        linhas = erro_txt.strip().splitlines()
        ultima = linhas[-1]
        arquivo = next(
            (l.strip() for l in linhas if 'File "' in l
             and "test_smoco_longo" not in l),
            "",
        )
        crashes.append(f"{onde}: {ultima}\n      {arquivo}")

    # --- cada cena, martelada de propenso -----------------------------
    # Sem isso o teste so vivia na masmorra: road, city e combat nunca
    # eram alcançados por tecla nenhuma, e era exatamente ai que o
    # NameError do pygame estava escondido.
    for cena in CENAS:
        try:
            manager.switch(cena)
        except Exception:  # noqa: BLE001
            registrar(0, cena, traceback.format_exc())
            continue
        visitadas.add(cena)
        grupo = rng.choice((TECLAS_MENU, TECLAS_JOGO, TECLAS_RISCO))
        antes = len(crashes)
        try:
            for passo in range(700):
                uma_tecla(manager, grupo[passo % len(grupo)])
                teclas_total += 1
                manager.update(dt)
                if passo % 5 == 0:
                    manager.draw()
        except Exception:  # noqa: BLE001
            registrar(passo, cena, traceback.format_exc())
        if len(crashes) > antes:
            break

    # --- e uma corrida longa na masmorra ------------------------------
    manager.switch("dungeon")
    visitadas.add("dungeon")
    grupo = rng.choice((TECLAS_MENU, TECLAS_JOGO))
    for passo in range(3000):
        try:
            uma_tecla(manager, grupo[passo % len(grupo)])
            teclas_total += 1
            manager.update(dt)
            if passo % 7 == 0:
                manager.draw()
        except Exception:  # noqa: BLE001
            registrar(passo, "dungeon longa", traceback.format_exc())
            break

    print(f"teclas apertadas: {teclas_total}")
    print(f"cenas vistas: {sorted(visitadas)}")

    if crashes:
        print(f"\n{len(crashes)} CRASH(ES):")
        vistos = set()
        for c in crashes:
            chave = c.splitlines()[0].split(": ", 1)[-1]
            if chave in vistos:
                continue
            vistos.add(chave)
            print(f"  - {c}")
        return 1

    faltando = [c for c in CENAS if c not in visitadas]
    if faltando:
        print(f"[FALHOU] cenas nunca visitadas: {faltando}")
        return 1
    print("\nsmoco longo: nenhum crash")
    return 0


if __name__ == "__main__":
    sys.exit(main())