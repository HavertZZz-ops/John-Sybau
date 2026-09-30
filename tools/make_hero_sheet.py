"""Gera o protagonista (John Sybau) com idle de 8 quadros em 4 direcoes.

Referencia visual: soldado de bone verde, camisa verde, avental branco
na cintura, calca azul-marinho, bota escura e uma maca com espinhos na
mao direita.

Saidas em assets/sprites/hero/:
    hero_sheet.png       folha 4 colunas (norte, sul, leste, oeste) x 8 linhas
    hero_<dir>_<n>.png   quadros avulsos
    hero.json            metadados de animacao

    python tools/make_hero_sheet.py            # gera tudo
    python tools/make_hero_sheet.py --preview  # + folha ampliada
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import settings  # noqa: E402
from tools.make_pixelart import Canvas  # noqa: E402

FW, FH = 32, 38  # tamanho de cada quadro desenhado
FRAMES = 8
FPS = 6

# fator com que os PNGs sao gravados. Mantido em 1 de proposito: os
# arquivos ficam no tamanho de desenho, e quem aplica o enlarge e o
# jogo, com vizinho mais proximo. Gravar ja escalado aqui faria a
# escala das opcoes acted duas vezes.
OUTPUT_SCALE = 1

DIRECTIONS = ("norte", "sul", "leste", "oeste")
COL = {"norte": 0, "sul": 1, "leste": 2, "oeste": 3}

CX = 16  # eixo horizontal do personagem

# --- paleta da referencia -----------------------------------------
OUTLINE = (22, 24, 30, 255)
CAP = (96, 112, 60, 255)
CAP_DARK = (70, 84, 42, 255)
CAP_LIGHT = (118, 134, 76, 255)
SHIRT = (100, 120, 64, 255)
SHIRT_DARK = (74, 92, 46, 255)
SHIRT_LIGHT = (126, 146, 82, 255)
SKIN = (236, 196, 156, 255)
SKIN_SHADE = (204, 164, 128, 255)
HAIR = (60, 46, 38, 255)
APRON = (230, 228, 220, 255)
APRON_SHADE = (198, 195, 186, 255)
PANTS = (56, 62, 92, 255)
PANTS_LIGHT = (76, 82, 116, 255)
BOOT = (48, 42, 50, 255)
BOOT_DARK = (32, 28, 36, 255)
METAL = (152, 158, 170, 255)
METAL_DARK = (78, 84, 98, 255)
METAL_LIGHT = (196, 202, 214, 255)
EYE = (34, 30, 38, 255)

# 8 quadros: sobe, segura, desce, segura
BREATH = (0, 0, -1, -1, -1, 0, 1, 1)
# a maca balanca com atraso em relacao ao corpo
SWAY = (0, 1, 1, 1, 0, -1, -1, 0)


def flip_h(src: Canvas) -> Canvas:
    out = Canvas(src.w, src.h)
    for y in range(src.h):
        for x in range(src.w):
            out.set(src.w - 1 - x, y, src.get(x, y))
    return out


def _legs(c: Canvas, dy: int) -> None:
    """Calca azul-marinho e botas escuras, de frente e de costas."""
    top = 27 + dy
    c.rect(CX - 5, top, 4, 5, PANTS)
    c.rect(CX + 1, top, 4, 5, PANTS)
    c.vline(CX, top, top + 4, PANTS_LIGHT)
    c.hline(top, CX - 5, CX + 4, PANTS_LIGHT)
    c.rect(CX - 6, top + 5, 5, 3, BOOT)
    c.rect(CX + 1, top + 5, 5, 3, BOOT)
    c.hline(top + 7, CX - 6, CX - 2, BOOT_DARK)
    c.hline(top + 7, CX + 1, CX + 5, BOOT_DARK)


def _legs_side(c: Canvas, dy: int) -> None:
    top = 27 + dy
    c.rect(CX - 4, top, 4, 5, PANTS)
    c.rect(CX + 1, top, 4, 5, PANTS_LIGHT)
    c.vline(CX, top, top + 4, PANTS_LIGHT)
    c.rect(CX, top + 5, 6, 3, BOOT)
    c.rect(CX - 5, top + 5, 5, 3, BOOT)
    c.hline(top + 7, CX, CX + 5, BOOT_DARK)
    c.hline(top + 7, CX - 5, CX - 1, BOOT_DARK)


def _apron(c: Canvas, dy: int, wide: int = 6) -> None:
    """Avental branco amarrado na cintura, cobrindo a calca."""
    top = 23 + dy
    c.rect(CX - wide, top, wide * 2, 6, APRON)
    c.hline(top, CX - wide, CX + wide - 1, APRON_SHADE)
    c.hline(top + 5, CX - wide, CX + wide - 1, APRON_SHADE)
    c.vline(CX, top + 1, top + 4, APRON_SHADE)


def _torso_front(c: Canvas, dy: int) -> None:
    """Camisa verde larga, com ombros marcados e pescoco visivel."""
    top = 18 + dy
    c.rect(CX - 1, 16 + dy, 3, 3, SKIN_SHADE)  # pescoco
    c.rect(CX - 6, top, 13, 5, SHIRT)
    c.hline(top, CX - 6, CX + 6, SHIRT_LIGHT)
    c.rect(CX - 5, top + 4, 11, 3, SHIRT_DARK)
    c.rect(CX - 8, top + 1, 3, 6, SHIRT)
    c.rect(CX + 6, top + 1, 3, 6, SHIRT)
    c.rect(CX - 8, top + 7, 3, 2, SKIN)
    c.rect(CX + 6, top + 7, 3, 2, SKIN)


def _torso_back(c: Canvas, dy: int) -> None:
    top = 18 + dy
    c.rect(CX - 1, 16 + dy, 3, 3, SKIN_SHADE)
    c.rect(CX - 6, top, 13, 5, SHIRT)
    c.hline(top, CX - 6, CX + 6, SHIRT_LIGHT)
    c.rect(CX - 5, top + 4, 11, 3, SHIRT_DARK)
    c.rect(CX - 8, top + 1, 3, 6, SHIRT)
    c.rect(CX + 6, top + 1, 3, 6, SHIRT)
    c.rect(CX - 8, top + 7, 3, 2, SKIN)
    c.rect(CX + 6, top + 7, 3, 2, SKIN)


def _torso_side(c: Canvas, dy: int) -> None:
    top = 18 + dy
    c.rect(CX - 1, 16 + dy, 3, 3, SKIN_SHADE)
    c.rect(CX - 5, top, 11, 5, SHIRT)
    c.hline(top, CX - 5, CX + 5, SHIRT_LIGHT)
    c.rect(CX - 4, top + 4, 9, 3, SHIRT_DARK)
    c.rect(CX + 4, top + 1, 3, 6, SHIRT)
    c.rect(CX - 7, top + 1, 3, 6, SHIRT_LIGHT)
    c.rect(CX + 4, top + 7, 3, 2, SKIN)


def _mace(c: Canvas, dx: int, dy: int) -> None:
    """Maca com espinhos, na mao direita (cabo + bola espinhosa)."""
    x = 27 + dx
    hand = 25 + dy
    ball = 31 + dy
    c.vline(x, hand, ball - 1, METAL_DARK)  # cabo
    c.ellipse(x, ball, 3, 3, METAL)
    c.ellipse(x - 1, ball - 1, 1, 1, METAL_LIGHT)
    # espinhos saindo da bola
    for ox, oy in (
        (0, -4), (-3, -3), (3, -3), (-4, 0), (4, 0), (-3, 3), (3, 3), (0, 4)
    ):
        c.set(x + ox, ball + oy, METAL_DARK)


def _mace_side(c: Canvas, dx: int, dy: int) -> None:
    """Maca de perfil, encostada no corpo."""
    x = 25 + dx
    hand = 25 + dy
    ball = 31 + dy
    c.vline(x, hand, ball - 1, METAL_DARK)
    c.ellipse(x, ball, 2, 3, METAL)
    c.set(x - 1, ball - 1, METAL_LIGHT)
    for ox, oy in ((-2, -3), (1, -3), (-3, 0), (2, 0), (-2, 3), (2, 3), (0, 4)):
        c.set(x + ox, ball + oy, METAL_DARK)


def _head_front(c: Canvas, dy: int) -> None:
    """Rosto primeiro, bone e aba por cima da testa."""
    c.ellipse(CX, 14 + dy, 4, 4, SKIN)
    c.hline(17 + dy, CX - 2, CX + 2, SKIN_SHADE)
    c.set(CX - 2, 14 + dy, EYE)
    c.set(CX + 2, 14 + dy, EYE)
    c.ellipse(CX, 8 + dy, 5, 4, CAP)
    c.ellipse(CX, 6 + dy, 4, 2, CAP_LIGHT)
    c.rect(CX - 5, 11 + dy, 11, 2, CAP_DARK)
    c.hline(12 + dy, CX - 5, CX + 5, CAP)


def _head_back(c: Canvas, dy: int) -> None:
    """Costas: cabelo escuro, sem rosto."""
    c.ellipse(CX, 14 + dy, 4, 4, HAIR)
    c.ellipse(CX, 8 + dy, 5, 4, CAP)
    c.ellipse(CX, 6 + dy, 4, 2, CAP_LIGHT)
    c.rect(CX - 5, 11 + dy, 11, 2, CAP)
    c.hline(12 + dy, CX - 5, CX + 5, CAP_DARK)


def _head_side(c: Canvas, dy: int) -> None:
    """Perfil: aba do bone apontando para a frente."""
    c.ellipse(CX, 14 + dy, 4, 4, SKIN)
    c.hline(17 + dy, CX - 2, CX + 3, SKIN_SHADE)
    c.set(CX + 3, 14 + dy, EYE)
    c.set(CX - 4, 15 + dy, SKIN_SHADE)
    c.ellipse(CX, 8 + dy, 5, 4, CAP)
    c.ellipse(CX, 6 + dy, 4, 2, CAP_LIGHT)
    c.rect(CX + 2, 11 + dy, 6, 2, CAP_DARK)
    c.hline(12 + dy, CX + 2, CX + 7, CAP)
    c.rect(CX - 5, 11 + dy, 4, 2, CAP_DARK)
    c.set(CX - 4, 13 + dy, HAIR)


def build_frame(direction: str, frame: int) -> Canvas:
    """Monta um quadro do idle na direcao pedida."""
    index = frame % FRAMES
    dy = BREATH[index]
    sway = SWAY[index]
    c = Canvas(FW, FH)

    if direction == "norte":
        _torso_back(c, dy)
        _apron(c, dy)
        _legs(c, dy)
        _head_back(c, dy)
        _mace(c, sway, dy)
    elif direction == "sul":
        _torso_front(c, dy)
        _apron(c, dy)
        _legs(c, dy)
        _head_front(c, dy)
        _mace(c, sway, dy)
    elif direction == "leste":
        _torso_side(c, dy)
        _apron(c, dy, wide=5)
        _legs_side(c, dy)
        _head_side(c, dy)
        _mace_side(c, sway, dy)
    elif direction == "oeste":
        base = Canvas(FW, FH)
        _torso_side(base, dy)
        _apron(base, dy, wide=5)
        _legs_side(base, dy)
        _head_side(base, dy)
        _mace_side(base, sway, dy)
        base.outline_silhouette(OUTLINE)
        return flip_h(base)
    else:
        raise ValueError(direction)

    c.outline_silhouette(OUTLINE)
    return c


def build_all() -> dict[str, list[Canvas]]:
    return {
        d: [build_frame(d, i) for i in range(FRAMES)]
        for d in DIRECTIONS
    }


def sheet_of(frames: dict[str, list[Canvas]], scale: int = 1) -> Canvas:
    """Folha: colunas = direcoes, linhas = quadros."""
    fw, fh = FW * scale, FH * scale
    sheet = Canvas(fw * len(DIRECTIONS), fh * FRAMES)
    for direction, canvases in frames.items():
        col = COL[direction]
        for row, canvas in enumerate(canvases):
            sheet.draw(canvas.upscale(scale), col * fw, row * fh)
    return sheet


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprites do John Sybau, 4 direcoes")
    parser.add_argument("--preview", action="store_true", help="gera folha ampliada")
    parser.add_argument(
        "--scale",
        type=int,
        default=OUTPUT_SCALE,
        choices=[1, 2, 3, 4],
        help=(
            "fator de gravacao dos PNGs. O padrao 1 mantem o tamanho de "
            "desenho e deixa o jogo aplicar a escala das opcoes"
        ),
    )
    args = parser.parse_args()

    scale = args.scale
    if scale != OUTPUT_SCALE:
        print(
            f"aviso: gravando em {scale}x. O jogo espera {OUTPUT_SCALE}x, "
            f"entao a escala das opcoes vai agir em cima disso."
        )

    frames = build_all()
    out_dir = settings.SPRITES_DIR / "hero"
    out_dir.mkdir(parents=True, exist_ok=True)

    for old in out_dir.glob("hero_*.png"):
        old.unlink()

    sheet_of(frames, scale).to_png(out_dir / "hero_sheet.png")
    print(
        f"gerado: hero_sheet.png  "
        f"{FW * scale * len(DIRECTIONS)}x{FH * scale * FRAMES}"
    )

    fw, fh = FW * scale, FH * scale
    for direction, canvases in frames.items():
        for i, canvas in enumerate(canvases):
            canvas.upscale(scale).to_png(out_dir / f"hero_{direction}_{i}.png")

    meta = {
        "frame_width": fw,
        "frame_height": fh,
        "frames": FRAMES,
        "scale": scale,
        "columns": list(DIRECTIONS),
        "column_index": COL,
        "fps": FPS,
        "animations": {
            "idle": {
                direction: [f"hero_{direction}_{i}.png" for i in range(FRAMES)]
                for direction in DIRECTIONS
            }
        },
        "sheet": {
            "file": "hero_sheet.png",
            "width": fw * len(DIRECTIONS),
            "height": fh * FRAMES,
        },
    }
    (out_dir / "hero.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(f"gerado: hero.json  (quadro {fw}x{fh})")
    (out_dir / ".gitkeep").write_text("", encoding="utf-8")

    frames["sul"][0].upscale(scale).to_png(
        settings.SPRITES_DIR / "protagonista.png"
    )
    print("gerado: assets/sprites/protagonista.png (sul, quadro 0)")

    if args.preview:
        preview = ROOT / "preview_hero.png"
        samples = [0, 2, 4, 6]
        zoom = 2
        pad = 6
        sheet = Canvas(
            len(samples) * fw * zoom + pad * (len(samples) + 1),
            len(DIRECTIONS) * fh * zoom + pad * (len(DIRECTIONS) + 1),
            (30, 27, 40, 255),
        )
        for r, direction in enumerate(DIRECTIONS):
            for ci, fi in enumerate(samples):
                big = frames[direction][fi].upscale(scale)
                ox = pad + ci * (fw * zoom + pad)
                oy = pad + r * (fh * zoom + pad)
                for y in range(fh * zoom):
                    for x in range(fw * zoom):
                        sheet.set(ox + x, oy + y, big.get(x // zoom, y // zoom))
        sheet.to_png(preview)
        print(
            f"gerado: {preview.name}  "
            f"(linhas = N/S/L/O, colunas = quadros 0,2,4,6, {fw * zoom}px cada)"
        )

    print(f"\n{len(DIRECTIONS) * FRAMES} quadros de {fw}x{fh} em {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
