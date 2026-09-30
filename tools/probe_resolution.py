"""Reproduz: mudar a resolucao com teclas reais e mede o estrago.

Roda o jogo de verdade, entra nas opcoes, muda a resolucao e verifica
o que quebra: foco, tamanho real da janela, estado da cena, e se as
teclas continuam chegando depois da troca.

    python tools/probe_resolution.py
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SC = {
    "DOWN": (0x28, 0x50), "UP": (0x26, 0x48), "LEFT": (0x25, 0x4B),
    "RIGHT": (0x27, 0x4D), "ENTER": (0x0D, 0x1C), "ESC": (0x1B, 0x01),
    "TAB": (0x09, 0x0F), "I": (0x49, 0x17),
}


class RECT(ctypes.Structure):
    _fields_ = [
        ("l", ctypes.c_long), ("t", ctypes.c_long),
        ("r", ctypes.c_long), ("b", ctypes.c_long),
    ]


def find_window() -> int:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if "John Sybau" in buf.value:
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def client_size(hwnd: int) -> tuple[int, int]:
    r = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return (r.r - r.l, r.b - r.t)


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.l, r.t, r.r, r.b)


def is_foreground(hwnd: int) -> bool:
    return int(user32.GetForegroundWindow()) == hwnd


def tap(hwnd: int, name: str) -> None:
    vk, scan = SC[name]
    lparam = 1 | (scan << 16) | (1 << 24)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lparam)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, lparam | 0xC0000000)
    time.sleep(0.14)


def main() -> int:
    env = {**os.environ, "TRACE": "1"}
    proc = subprocess.Popen(
        [sys.executable, "run.py"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
    )

    hwnd = 0
    for _ in range(40):
        time.sleep(0.5)
        hwnd = find_window()
        if hwnd:
            break
    if not hwnd:
        proc.terminate()
        print("FALHOU: janela nao apareceu")
        return 1

    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)

    print(f"janela inicial: hwnd={hwnd} cliente={client_size(hwnd)}")

    # entra nas opcoes
    tap(hwnd, "DOWN")
    tap(hwnd, "ENTER")
    time.sleep(0.4)

    old = hwnd
    old_size = client_size(hwnd)
    print(f"\napos entrar nas opcoes: cliente={old_size}")

    # muda a resolucao duas vezes
    for passo in (1, 2):
        tap(hwnd, "RIGHT")
        time.sleep(0.8)
        novo = find_window()
        novo_size = client_size(novo) if novo else (0, 0)
        rect = window_rect(novo) if novo else (0, 0, 0, 0)
        print(
            f"\n--- depois de mudar a resolucao (passo {passo}) ---"
        )
        print(f"  hwnd antigo={old}  hwnd novo={novo}  mudou={novo != old}")
        print(f"  tamanho anterior={old_size}  agora={novo_size}")
        print(f"  posicao da janela={rect}")
        print(f"  janela tem foco={is_foreground(novo)}")
        print(
            f"  cabe na tela do desktop? "
            f"{rect[2] <= 1920 and rect[3] <= 1200}"
        )
        if novo != old:
            user32.SetForegroundWindow(novo)
            time.sleep(0.2)
        old = novo

    # as teclas ainda chegam depois de tudo isso?
    print("\n--- testando teclas depois das trocas ---")
    for nome in ("DOWN", "ENTER", "ESC"):
        tap(old, nome)
    time.sleep(0.6)

    proc.terminate()
    out = proc.stdout.read()

    print("\n=== ultimas linhas do TRACE ===")
    linhas = [l for l in out.splitlines() if "[trace]" in l]
    for l in linhas[-12:]:
        print(l)
    print(f"\ntotal de teclas recebidas: {len([l for l in linhas if 'KEYDOWN' in l])}")
    if "Traceback" in out:
        print("\n>>> CRASH:")
        for l in out.splitlines()[-12:]:
            print(l)
    return 0


if __name__ == "__main__":
    sys.exit(main())
