"""Gera o protagonista encapuzado com idle de 4 quadros em 4 direcoes.

Referencia visual: personagem de capuz escuro, camisa azul-marinho,
calca oliva com bolsos, bota marrom e bolsa de ombro.

Saidas em assets/sprites/hero/:
    hero_sheet.png       folha 4 colunas (N, S, L, O) x 4 linhas
    hero_norte_0..3.png  quadros avulsos
    hero.json            metadados de animacao (quadro, linha, fps)

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

FW, FH = 24, 32  # tamanho de cada quadro
FRAMES = 4  # quadros do idle
FPS = 6

# colunas da folha: norte, sul, leste, oeste
DIRECTIONS = ("norte", "sul", "leste", "oeste")
COL = {"norte": 0, "sul": 1, "leste": 2, "oeste": 3}

# --- paleta, tirada da referencia ---------------------------------
OUTLINE = (18, 20, 28, 255)
HOOD = (36, 41, 56, 255)
HOOD_DARK = (26, 30, 42, 255)
HOOD_RIM = (48, 54, 72, 255)
SHIRT = (46, 51, 68, 255)
SHIRT_LIGHT = (62, 68, 88, 255)
SKIN = (228, 188, 152, 255)
SKIN_SHADE = (198, 158, 126, 255)
HAIR = (48, 40, 38, 255)
PANTS = (94, 97, 63, 255)
PANTS_LIGHT = (112, 115, 78, 255)
BOOT = (94, 63, 44, 255)
BOOT_DARK = (72, 48, 34, 255)
BAG = (124, 90, 58, 255)
BAG_DARK = (96, 68, 44, 255)
STRAP = (108, 78, 52, 255)
EYE = (28, 26, 34, 255)

# respiracao: sobe, neutro, desce, neutro
IDLE = ((0, 0), (-1, -1), (0, 0), (1, 1))


def flip_h(src: Canvas) -> Canvas:
    """Espelha a imagem na horizontal (oeste sai de leste)."""
    out = Canvas(src.w, src.h)
    for y in range(src.h):
        for x in range(src.w):
            out.set(src.w - 1 - x, y, src.get(x, y))
    return out


def _legs(c: Canvas, dy: int) -> None:
    """Calca oliva e botas, vista de frente e de costas."""
    top = 20 + dy
    c.rect(9, top, 3, 7, PANTS)
    c.rect(13, top, 3, 7, PANTS)
    c.vline(12, top, top + 6, PANTS_LIGHT)
    c.hline(21 + dy, 9, 15, PANTS_LIGHT)
    c.rect(8, top + 7, 4, 2, BOOT)
    c.rect(13, top + 7, 4, 2, BOOT)
    c.hline(top + 8, 8, 11, BOOT_DARK)
    c.hline(top + 8, 13, 16, BOOT_DARK)


def _legs_side(c: Canvas, dy: int) -> None:
    """Calca e botas de perfil: perna da frente avancada."""
    top = 20 + dy
    c.rect(9, top, 3, 7, PANTS)
    c.rect(13, top, 3, 7, PANTS_LIGHT)
    c.vline(12, top, top + 6, PANTS_LIGHT)
    c.rect(12, top + 7, 5, 2, BOOT)
    c.rect(7, top + 7, 4, 2, BOOT)
    c.hline(top + 8, 12, 16, BOOT_DARK)


def _torso_front(c: Canvas, dy: int) -> None:
    """Torso de frente: camisa, faixa diagonal e bolsa."""
    c.rect(8, 11 + dy, 9, 9, SHIRT)
    c.hline(11 + dy, 8, 16, SHIRT_LIGHT)
    c.hline(12 + dy, 8, 16, SHIRT)
    # bracos colados ao corpo
    c.rect(6, 12 + dy, 2, 7, SHIRT)
    c.rect(17, 12 + dy, 2, 7, SHIRT)
    # faixa atravessando o peito, do ombro esquerdo ao direito
    for i in range(8):
        c.set(9 + i, 12 + dy + i, STRAP)
    # bolsa na cintura
    c.rect(15, 16 + dy, 4, 4, BAG)
    c.rect(15, 16 + dy, 4, 1, BAG_DARK)
    c.hline(19 + dy, 15, 18, BAG_DARK)


def _torso_back(c: Canvas, dy: int) -> None:
    """Torso de costas: sem rosto, bolsa do outro lado."""
    c.rect(8, 11 + dy, 9, 9, SHIRT)
    c.hline(11 + dy, 8, 16, SHIRT_LIGHT)
    c.hline(12 + dy, 8, 16, SHIRT)
    c.rect(6, 12 + dy, 2, 7, SHIRT)
    c.rect(17, 12 + dy, 2, 7, SHIRT)
    for i in range(8):
        c.set(15 - i, 12 + dy + i, STRAP)
    c.rect(5, 16 + dy, 4, 4, BAG)
    c.rect(5, 16 + dy, 4, 1, BAG_DARK)
    c.hline(19 + dy, 5, 8, BAG_DARK)


def _torso_side(c: Canvas, dy: int) -> None:
    """Torso de perfil: mais estreito, um braco na frente, bolsa atrás."""
    c.rect(9, 11 + dy, 8, 9, SHIRT)
    c.hline(11 + dy, 9, 16, SHIRT_LIGHT)
    c.hline(12 + dy, 9, 16, SHIRT)
    c.rect(15, 12 + dy, 2, 7, SHIRT)
    c.rect(15, 19 + dy, 2, 2, SKIN)
    c.rect(7, 12 + dy, 2, 7, SHIRT_LIGHT)
    c.rect(5, 16 + dy, 3, 4, BAG)
    c.rect(5, 16 + dy, 3, 1, BAG_DARK)


def _hood_front(c: Canvas, dy: int) -> None:
    """Capuz de frente: rosto dentro da sombra do capuz."""
    c.ellipse(12, 6 + dy, 4, 4, HOOD)
    c.ellipse(12, 7 + dy, 2, 2, SKIN)
    c.set(11, 8 + dy, SKIN_SHADE)
    # sombra do capuz cortando a testa
    c.hline(5 + dy, 10, 14, HOOD_DARK)
    c.set(10, 7 + dy, HOOD_DARK)
    c.set(14, 7 + dy, HOOD_DARK)
    c.set(10, 6 + dy, HOOD_RIM)
    c.set(14, 6 + dy, HOOD_RIM)
    # olhos
    c.set(11, 7 + dy, EYE)
    c.set(13, 7 + dy, EYE)


def _hood_back(c: Canvas, dy: int) -> None:
    """Capuz de costas: capsula escura, sem rosto."""
    c.ellipse(12, 6 + dy, 4, 4, HOOD)
    c.ellipse(12, 4 + dy, 3, 2, HOOD_RIM)
    c.hline(2 + dy, 11, 13, HOOD_RIM)
    c.set(8, 5 + dy, HOOD_DARK)
    c.set(16, 5 + dy, HOOD_DARK)


def _hood_side(c: Canvas, dy: int) -> None:
    """Capuz de perfil: rosto aparece na borda da frente."""
    c.ellipse(12, 6 + dy, 4, 4, HOOD)
    c.ellipse(14, 7 + dy, 2, 2, SKIN)
    c.hline(5 + dy, 13, 16, HOOD_DARK)
    c.hline(9 + dy, 14, 16, SKIN_SHADE)
    c.set(17, 7 + dy, SKIN)  # nariz
    c.set(15, 7 + dy, EYE)   # um olho so
    c.set(9, 6 + dy, HOOD_RIM)
    c.set(9, 8 + dy, HOOD_DARK)


def build_frame(direction: str, frame: int) -> Canvas:
    """Monta um quadro do idle na direcao pedida."""
    dy, arm = IDLE[frame % len(IDLE)]
    c = Canvas(FW, FH)

    if direction == "norte":
        _torso_back(c, dy)
        _hood_back(c, dy)
        _legs(c, dy)
    elif direction == "sul":
        _torso_front(c, dy)
        _hood_front(c, dy)
        _legs(c, dy)
    elif direction == "leste":
        _torso_side(c, dy)
        _hood_side(c, dy)
        _legs_side(c, dy)
    elif direction == "oeste":
        base = Canvas(FW, FH)
        _torso_side(base, dy)
        _hood_side(base, dy)
        _legs_side(base, dy)
        base.outline_silhouette(OUTLINE)
        return flip_h(base)
    else:
        raise ValueError(direction)

    if arm:
        # bracos descem/sobem 1px junto com a respiracao
        c.set(5, 20 + dy + arm, SHIRT)
        c.set(17, 20 + dy + arm, SHIRT)

    c.outline_silhouette(OUTLINE)
    return c


def build_all() -> dict[str, list[Canvas]]:
    return {
        d: [build_frame(d, i) for i in range(FRAMES)]
        for d in DIRECTIONS
    }


def sheet_of(frames: dict[str, list[Canvas]]) -> Canvas:
    """Monta a folha: colunas = direcoes, linhas = quadros."""
    sheet = Canvas(FW * len(DIRECTIONS), FH * FRAMES)
    for direction, canvases in frames.items():
        col = COL[direction]
        for row, canvas in enumerate(canvases):
            sheet.draw(canvas, col * FW, row * FH)
    return sheet


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprites do protagonista, 4 direcoes")
    parser.add_argument("--preview", action="store_true", help="gera folha ampliada")
    args = parser.parse_args()

    frames = build_all()
    out_dir = settings.SPRITES_DIR / "hero"
    out_dir.mkdir(parents=True, exist_ok=True)

    # folha
    sheet_of(frames).to_png(out_dir / "hero_sheet.png")
    print(f"gerado: hero_sheet.png  {FW * len(DIRECTIONS)}x{FH * FRAMES}")

    # quadros avulsos
    for direction, canvases in frames.items():
        for i, canvas in enumerate(canvases):
            canvas.to_png(out_dir / f"hero_{direction}_{i}.png")

    # metadados
    meta = {
        "frame_width": FW,
        "frame_height": FH,
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
            "width": FW * len(DIRECTIONS),
            "height": FH * FRAMES,
        },
    }
    (out_dir / "hero.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print("gerado: hero.json")

    # marcador para o git guardar a pasta mesmo vazia de outros arquivos
    (out_dir / ".gitkeep").write_text("", encoding="utf-8")

    # copia o quadro de referencia (sul, frame 0) para o fluxo antigo
    frames["sul"][0].to_png(settings.SPRITES_DIR / "protagonista.png")
    print("gerado: assets/sprites/protagonista.png (sul, quadro 0)")

    if args.preview:
        preview = ROOT / "preview_hero.png"
        contact = Canvas(FW * 4 * 3 + 20, FH * 4 * 3 + 20, (32, 28, 42, 255))
        sheet = sheet_of(frames)
        for y in range(contact.h - 20):
            for x in range(contact.w - 20):
                contact.set(x + 10, y + 10, sheet.get(x // 3, y // 3))
        contact.to_png(preview)
        print(f"gerado: {preview.name}")

    print(f"\n{len(DIRECTIONS) * FRAMES} quadros em {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
