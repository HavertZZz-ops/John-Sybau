"""Mede, de dentro do jogo, se a janela cabe na tela apos cada troca.

Este teste e o mais importante do projeto: e o unico que roda o jogo de
verdade, na resolucao do usuario, e compara a janela real (medida pela
API do Windows) com a area de trabalho. Foi ele que pegou a resolucao
nativa estourando a tela, porque a moldura da janela soma ~16px de cada
lado e o filtro comparava so com a tela crua.

    python tools/probe_window_fit.py
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
SC = {"DOWN": (0x28, 0x50), "ENTER": (0x0D, 0x1C), "RIGHT": (0x27, 0x4D)}


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


def window_rect(hwnd: int) -> RECT:
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def work_area() -> RECT:
    r = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
    return r


def tap(hwnd: int, name: str) -> None:
    vk, scan = SC[name]
    lparam = 1 | (scan << 16) | (1 << 24)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lparam)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, lparam | 0xC0000000)
    time.sleep(0.16)


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, "run.py"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
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

    work = work_area()
    work_w, work_h = work.r - work.l, work.b - work.t
    print(f"area de trabalho (logica): {work_w} x {work_h}")

    # as medidas sao feitas pelo MESMO processo que roda o jogo, entao
    # nao ha divergencia de DPI entre quem mede e quem e medido
    failures = []

    def check(rotulo: str) -> None:
        h = find_window()
        if not h:
            failures.append(f"{rotulo}: janela sumiu")
            print(f"  {rotulo}: JANELA SUMIU")
            return
        r = window_rect(h)
        w, ht = r.r - r.l, r.b - r.t
        dentro = (
            r.l >= work.l and r.t >= work.t
            and r.r <= work.r and r.b <= work.b
        )
        print(
            f"  {rotulo:10} janela {w}x{ht} em ({r.l},{r.t})-({r.r},{r.b})"
            f"  dentro={dentro}"
        )
        if not dentro:
            failures.append(
                f"{rotulo}: {w}x{ht} em ({r.l},{r.t}) passa da area "
                f"{work_w}x{work_h}"
            )

    print("\ninicial:")
    check("inicial")

    # entra nas opcoes e cicla a resolucao varias vezes
    tap(hwnd, "DOWN")
    tap(hwnd, "ENTER")
    time.sleep(0.4)

    print("\ntrocando a resolucao 6 vezes:")
    for i in range(6):
        tap(hwnd, "RIGHT")
        time.sleep(0.8)
        check(f"troca {i + 1}")

    proc.terminate()
    time.sleep(0.3)

    print()
    if failures:
        print(f"FALHOU: {len(failures)} janela(s) fora da area de trabalho")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: toda janela ficou dentro da area de trabalho")
    return 0


if __name__ == "__main__":
    sys.exit(main())
