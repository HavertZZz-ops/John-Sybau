"""Estresse de video medindo o estado REAL do jogo, nao a janela.

Duas lições que custaram duas versoes falsas deste probe:

1. Medir o retangulo da janela nao serve para dizer a resolucao. Em
   tela cheia a janela SEMPRE tem o tamanho do monitor (1536x960 aqui),
   e na maior resolucao a janela tambem da 1536x960 (1520x921 + moldura).
   Os dois estados sao identicos do lado de fora. Por isso o probe
   reclamava que "a tela cheia nao mudou a janela" quando ela tinha
   mudado.

2. Navegar a menu com um numero fixo de UP e sutil. A aba de video tem
   5 linhas; apertar UP 5 vezes sempre volta ao mesmo lugar, 4 ou 6
   nao. Com 6, o RIGHT seguinte mexia em Vsync em vez de Tela cheia e o
   teste media uma janela parada sem avisar nada.

Agora a fonte da verdade e o proprio log do jogo (src/main._log), que
grava a superficie e o modo a cada troca. O retangulo continua sendo
medido, porque foi ele que pegou a janela estourando a tela.

    python tools/probe_video_stress.py [ciclos]
"""
from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32
LOG = ROOT / "jogo.log"

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SC = {
    "DOWN": (0x28, 0x50),
    "UP": (0x26, 0x48),
    "LEFT": (0x25, 0x4B),
    "RIGHT": (0x27, 0x4D),
    "ENTER": (0x0D, 0x1C),
    "ESC": (0x1B, 0x01),
}

# "janela recriada: (1520, 921) moldura=(16, 39) fullscreen=False"
RE_ESTADO = re.compile(
    r"janela recriada: \((\d+), (\d+)\)\s*moldura=\((\d+), (\d+)\)\s*"
    r"fullscreen=(True|False)"
)

LINHAS_VIDEO = 5
RESOLUCAO, TELA_CHEIA = 0, 3


class RECT(ctypes.Structure):
    _fields_ = [
        ("l", ctypes.c_long), ("t", ctypes.c_long),
        ("r", ctypes.c_long), ("b", ctypes.c_long),
    ]


def find_window() -> int:
    achados: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if "John Sybau" in buf.value:
            achados.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return achados[0] if achados else 0


def rect(hwnd: int) -> RECT:
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def work_area() -> RECT:
    r = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
    return r


def tap(hwnd: int, nome: str, espera: float = 0.3) -> None:
    vk, scan = SC[nome]
    lp = 1 | (scan << 16) | (1 << 24)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lp)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, lp | 0xC0000000)
    time.sleep(espera)


def estado_do_jogo() -> tuple[tuple[int, int], tuple[int, int], bool] | None:
    """Ultimo (superficie, moldura, tela cheia) que o jogo registrou."""
    if not LOG.is_file():
        return None
    ultimo = None
    for linha in LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = RE_ESTADO.search(linha)
        if m:
            ultimo = (
                (int(m.group(1)), int(m.group(2))),
                (int(m.group(3)), int(m.group(4))),
                m.group(5) == "True",
            )
    return ultimo


def main() -> int:
    ciclos = int(sys.argv[1]) if len(sys.argv) > 1 else 14

    # sem save o menu tem 3 itens e DOWN+ENTER cai em "Opcoes"; com save
    # tem 4 e o mesmo caminho entra na masmorra, e o teste mede nada
    for nome in ("config.json", "save1.json"):
        (ROOT / nome).unlink(missing_ok=True)

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
        print("FALHOU: a janela nao apareceu")
        return 1
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.6)

    work = work_area()
    ww, wh = work.r - work.l, work.b - work.t
    print(f"area de trabalho: {ww} x {wh}")
    print(f"ciclos: {ciclos}\n")

    falhas: list[str] = []
    resolucoes_vistas: set[tuple[int, int]] = set()
    estados_fullscreen: set[bool] = set()

    def conferir(rotulo: str) -> None:
        """Confere o estado que o JOGO注册ou, e a janela na tela."""
        h = find_window()
        if not h:
            falhas.append(f"{rotulo}: a janela sumiu")
            print(f"  {rotulo:20} JANELA SUMIU")
            return
        r = rect(h)
        dentro = (
            r.l >= work.l - 1 and r.t >= work.t - 1
            and r.r <= work.r + 1 and r.b <= work.b + 1
        )
        estado = estado_do_jogo()
        if estado is None:
            falhas.append(f"{rotulo}: o jogo nao registrou a janela")
            print(f"  {rotulo:20} SEM REGISTRO")
            return
        (sw, sh), moldura, full = estado
        resolucoes_vistas.add((sw, sh))
        estados_fullscreen.add(full)

        # coerencia: a moldura so pode ter valor quando esta em janela
        if full and moldura != (0, 0):
            falhas.append(
                f"{rotulo}: em tela cheia mas com moldura {moldura}; "
                f"a moldura em tela cheia e o espaco da escala, nao borda"
            )
        if not full and (moldura == (0, 0) or moldura[0] > 64 or moldura[1] > 96):
            falhas.append(
                f"{rotulo}: em janela com moldura absurda {moldura}"
            )

        # coerencia: em tela cheia, a superficie e escalada para a tela
        if full and (r.r - r.l) != ww:
            falhas.append(
                f"{rotulo}: em tela cheia a janela tem {r.r - r.l}px, "
                f"a area e {ww}px"
            )

        marca = "ok  " if dentro else "FORA"
        modo = "cheia" if full else "janela"
        print(
            f"  {rotulo:20} {marca} {modo:7} superficie {sw}x{sh}  "
            f"moldura {moldura}  janela {r.r - r.l}x{r.b - r.t} em "
            f"({r.l - work.l},{r.t - work.t})"
        )
        if not dentro:
            falhas.append(
                f"{rotulo}: janela {r.r - r.l}x{r.b - r.t} em "
                f"({r.l - work.l},{r.t - work.t}) sai da area {ww}x{wh}"
            )

    # ---- vai para as opcoes ----
    tap(hwnd, "DOWN", 0.6)
    tap(hwnd, "ENTER", 1.0)
    conferir("inicial")

    def ir_para(linha: int) -> None:
        for _ in range(LINHAS_VIDEO):
            tap(hwnd, "UP", 0.11)
        for _ in range(linha):
            tap(hwnd, "DOWN", 0.11)
        time.sleep(0.25)

    # ---- resolucao, ida e volta ate dar a volta toda ----
    print("\ntrocando a resolucao (6 voltas):")
    for i in range(1, 7):
        ir_para(RESOLUCAO)
        tap(hwnd, "RIGHT", 0.85)
        conferir(f"res {i}")

    # ---- tela cheia, ida e volta ----
    print("\nligando e desligando a tela cheia:")
    for i in range(1, 5):
        ir_para(TELA_CHEIA)
        tap(hwnd, "RIGHT", 1.0)
        conferir(f"cheia {i}")

    # ---- alternando os dois, que e onde dava problema ----
    print("\nresolucao e tela cheia alternadas:")
    for i in range(1, 7):
        ir_para(RESOLUCAO)
        tap(hwnd, "RIGHT", 0.85)
        conferir(f"misto {i} res")
        ir_para(TELA_CHEIA)
        tap(hwnd, "RIGHT", 1.0)
        conferir(f"misto {i} cheia")

    # ---- e a saida pela resolucao mais alta, que e a que estoura ----
    print("\nindo para a resolucao maxima e voltando:")
    for _ in range(3):
        ir_para(RESOLUCAO)
        tap(hwnd, "RIGHT", 0.85)
        conferir("max ->")
    for _ in range(3):
        ir_para(RESOLUCAO)
        tap(hwnd, "LEFT", 0.85)
        conferir("min <-")

    tap(hwnd, "ESC", 0.7)
    conferir("depois do ESC")

    proc.terminate()
    time.sleep(0.4)

    print()
    print(f"resolucoes que o jogo realmente usou: "
          f"{sorted(resolucoes_vistas)}")
    print(f"modos vistos: {sorted('tela cheia' if f else 'janela' for f in estados_fullscreen)}")
    if len(resolucoes_vistas) < 3:
        falhas.append(
            f"a resolucao passou por so {len(resolucoes_vistas)} tamanhos; "
            f"a lista tem mais de um"
        )
    if len(estados_fullscreen) < 2:
        falhas.append("a tela cheia nunca ficou ligada E desligada")

    if falhas:
        print(f"\nFALHOU: {len(falhas)}")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print("\nOK: video estavel em todas as trocas")
    return 0


if __name__ == "__main__":
    sys.exit(main())