"""Ponto de entrada do jogo.

Uso:
    python run.py              joga normalmente
    python run.py --frames 3   roda 3 quadros e sai (usado no teste)
"""
from __future__ import annotations

import sys

from src.main import main


def main_with_args() -> int:
    """Trata os argumentos e chama o loop principal."""
    frame_limit = None
    if "--frames" in sys.argv:
        index = sys.argv.index("--frames")
        if index + 1 < len(sys.argv):
            try:
                frame_limit = int(sys.argv[index + 1])
            except ValueError:
                print("--frames precisa de um numero inteiro")
                return 2
        else:
            print("--frames precisa de um numero")
            return 2

    return main(frame_limit=frame_limit)


if __name__ == "__main__":
    sys.exit(main_with_args())
