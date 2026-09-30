"""Roda o jogo de verdade e injeta teclas reais pela API do Windows.

Este teste nao simula eventos do pygame: ele abre a janela de verdade e
manda teclas com SendInput, que percorre o mesmo caminho que as teclas do
teclado. E o unico jeito de achar problema de input que so aparece com
o jogo em execucao (foco da janela, eventos engolidos, tecla presa).

    python tools/probe_input.py
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32

# constantes de SendInput
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008

# scancodes de hardware (set de teclado dos EUA)
SC = {
    "TAB": 0x0F,
    "ESC": 0x01,
    "ENTER": 0x1C,
    "SPACE": 0x39,
    "BACKSPACE": 0x0E,
    "UP": 0x48,
    "DOWN": 0x50,
    "LEFT": 0x4B,
    "RIGHT": 0x4D,
    "R": 0x13,
    "I": 0x17,
    "W": 0x11,
    "A": 0x1E,
    "S": 0x1F,
    "D": 0x20,
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", INPUTunion)]


def find_window(title: str) -> int:
    """HWND da janela do jogo pelo titulo."""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if title.lower() in buf.value.lower():
            found.append(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else 0


def send(scan: int, up: bool = False) -> bool:
    """Manda uma tecla pelo scancode de hardware."""
    extra = ctypes.c_ulong(0)
    ev = INPUT()
    ev.type = INPUT_KEYBOARD
    ev.ki = KEYBDINPUT(0, scan, KEYEVENTF_KEYUP if up else 0, 0, ctypes.pointer(extra))
    return bool(user32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(INPUT)))


def tap(name: str, hold: float = 0.06) -> None:
    scan = SC[name]
    send(scan)
    time.sleep(hold)
    send(scan, up=True)
    time.sleep(0.10)


def focus(hwnd: int) -> None:
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.35)


def main() -> int:
    print("iniciando o jogo de verdade...")
    proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    hwnd = 0
    for _ in range(40):
        time.sleep(0.5)
        hwnd = find_window("John Sybau")
        if hwnd:
            break

    if not hwnd:
        proc.terminate()
        print("FALHOU: janela do jogo nao apareceu")
        print(proc.stdout.read() if proc.stdout else "")
        return 1

    print(f"janela encontrada: hwnd={hwnd}")
    focus(hwnd)

    print("\nmandando teclas reais (setas, TAB, enter, esc):")
    for name in ("DOWN", "DOWN", "TAB", "DOWN", "ENTER", "I", "ESC"):
        tap(name)
        print(f"  {name}")

    time.sleep(0.5)
    focus(hwnd)
    tap("ESC")
    print("  ESC")

    time.sleep(0.5)
    proc.terminate()
    try:
        out = proc.stdout.read() if proc.stdout else ""
    except Exception:
        out = ""

    print("\n--- saida do jogo ---")
    print(out.strip() or "(nenhuma saida)")

    if "Traceback" in out:
        print("\n>>> o jogo CRASHOU com teclas reais")
        return 1
    print("\n>>> o jogo respondeu sem crash")
    return 0


if __name__ == "__main__":
    sys.exit(main())
