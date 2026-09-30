"""Gera os sprites do John Sybau sem depender de nenhuma API.

Escreve PNGs usando apenas a biblioteca padrao do Python (zlib +
struct) e desenha os personagens com primitivas simples, para que o
resultado fique coerente entre si.

    python tools/make_pixelart.py            # gera os 4 em assets/sprites/
    python tools/make_pixelart.py --preview  # gera tambem a folha de contato

Nao usa PIL, numpy, API ou chave nenhuma.
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import settings  # noqa: E402

W, H = 24, 32  # grade de cada personagem

# --- paleta compartilhada -----------------------------------------
TRANSPARENT = (0, 0, 0, 0)
OUTLINE = (26, 20, 32, 255)
SKIN = (226, 182, 146, 255)
SKIN_SHADE = (194, 148, 116, 255)
PALE_SKIN = (208, 208, 218, 255)
HAIR_DARK = (58, 42, 36, 255)
LEATHER = (142, 96, 58, 255)
LEATHER_DARK = (108, 70, 42, 255)
CLOTH = (70, 92, 132, 255)
CLOTH_DARK = (48, 64, 96, 255)
CLOAK = (58, 48, 78, 255)
CLOAK_DARK = (40, 34, 56, 255)
ROBE = (228, 224, 234, 255)
ROBE_SHADE = (198, 192, 208, 255)
GOLD = (224, 188, 98, 255)
GLOW = (250, 230, 158, 255)
WHITE = (240, 240, 246, 255)
DARK = (26, 22, 32, 255)
EYE = (30, 26, 38, 255)

HEAD_CX = 12
HEAD_CY = 7


class Canvas:
    """Grade de pixels RGBA minima."""

    def __init__(self, width: int = W, height: int = H, fill=TRANSPARENT):
        self.w = width
        self.h = height
        self.px: list[list[tuple[int, int, int, int]]] = [
            [fill] * width for _ in range(height)
        ]

    def set(self, x: int, y: int, color) -> None:
        """Marca um pixel, ignorando cores transparentes."""
        if 0 <= x < self.w and 0 <= y < self.h and color[3] > 0:
            self.px[y][x] = color

    def erase(self, x: int, y: int, color=TRANSPARENT) -> None:
        """Sobrescreve o pixel mesmo se a cor for transparente."""
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = color

    def get(self, x: int, y: int):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return TRANSPARENT

    def rect(self, x: int, y: int, w: int, h: int, color) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, color)

    def cut(self, x: int, y: int, w: int, h: int) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.erase(xx, yy)

    def ellipse(self, cx: int, cy: int, rx: int, ry: int, color) -> None:
        for yy in range(cy - ry, cy + ry + 1):
            for xx in range(cx - rx, cx + rx + 1):
                dx = (xx - cx) / max(rx, 0.5)
                dy = (yy - cy) / max(ry, 0.5)
                if dx * dx + dy * dy <= 1.0:
                    self.set(xx, yy, color)

    def vline(self, x: int, y0: int, y1: int, color) -> None:
        for y in range(y0, y1 + 1):
            self.set(x, y, color)

    def hline(self, y: int, x0: int, x1: int, color) -> None:
        for x in range(x0, x1 + 1):
            self.set(x, y, color)

    def outline_silhouette(self, color) -> None:
        """Contorno de 1px em volta dos pixels opacos."""
        marks = [
            (x, y)
            for y in range(self.h)
            for x in range(self.w)
            if self.get(x, y)[3] > 0
        ]
        for x, y in marks:
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if not (0 <= nx < self.w and 0 <= ny < self.h):
                    continue
                if self.get(nx, ny)[3] == 0:
                    self.px[ny][nx] = color

    def draw(self, other: "Canvas", ox: int, oy: int) -> None:
        for y in range(other.h):
            for x in range(other.w):
                c = other.get(x, y)
                if c[3] > 0:
                    self.set(x + ox, y + oy, c)

    def upscale(self, factor: int) -> "Canvas":
        """Replica cada pixel num bloco de `factor` x `factor`.

        Escala exata por vizinho mais proximo, entao o pixel art continua
        com as bordas duras (nada de interpolar).
        """
        if factor < 2:
            return self
        out = Canvas(self.w * factor, self.h * factor)
        for y in range(self.h):
            for x in range(self.w):
                c = self.get(x, y)
                if c[3] == 0:
                    continue
                for dy in range(factor):
                    for dx in range(factor):
                        out.set(x * factor + dx, y * factor + dy, c)
        return out

    def to_png(self, path: Path) -> None:
        raw = bytearray()
        for row in self.px:
            raw.append(0)  # filtro "None"
            for r, g, b, a in row:
                raw += bytes((r, g, b, a))

        def chunk(tag: bytes, data: bytes) -> bytes:
            body = tag + data
            return (
                struct.pack(">I", len(data))
                + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
            )

        ihdr = struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )


# --- personagem base ----------------------------------------------
# Um esqueleto unico com as mesmas quadriculas; cada personagem vira uma
# combinacao de cores e pecas opcionais, o que mantem o estilo igual.
def humanoid(
    body: tuple,
    body_dark: tuple,
    *,
    hair: tuple | None = None,
    long_hair: bool = False,
    cloak: tuple | None = None,
    lower: str = "legs",  # "legs" ou "skirt"
    beard: bool = False,
    hat: bool = False,
    hat_band: tuple = GOLD,
    staff: bool = False,
    lantern: bool = False,
    hood: bool = False,
    face: tuple = SKIN,
) -> Canvas:
    c = Canvas()
    cx = HEAD_CX

    # --- manto / capa atras do corpo ------------------------------
    if cloak:
        for y in range(12, 30):
            spread = min(4, (y - 12) // 3)
            c.hline(y, max(0, cx - 5 - spread), min(c.w - 1, cx + 5 + spread), cloak)

    # --- parte de baixo --------------------------------------------
    if lower == "skirt":
        for y in range(21, 30):
            spread = min(4, (y - 21) // 2)
            c.hline(y, max(0, cx - 4 - spread), min(c.w - 1, cx + 4 + spread), body)
        c.hline(29, 0, c.w - 1, body)
    else:
        c.rect(cx - 4, 23, 3, 6, body_dark)
        c.rect(cx + 1, 23, 3, 6, body_dark)
        c.rect(cx - 5, 29, 4, 2, DARK)
        c.rect(cx + 1, 29, 4, 2, DARK)

    # --- torso ------------------------------------------------------
    c.rect(cx - 5, 13, 11, 10, body)
    c.hline(13, cx - 5, cx + 5, body_dark)
    c.hline(19, cx - 5, cx + 5, LEATHER_DARK)  # cinto

    # --- bracos -----------------------------------------------------
    c.rect(cx - 7, 14, 2, 7, body_dark)
    c.rect(cx + 6, 14, 2, 7, body_dark)
    c.rect(cx - 7, 21, 2, 2, face)
    c.rect(cx + 6, 21, 2, 2, face)

    # --- cabeca -----------------------------------------------------
    # Elipse de pele primeiro; cabelo, capuz e chapeu entram por cima.
    # Nada aqui apaga a pele depois de desenhada, senao o rosto sai torto.
    if hood:
        # capuz por tras, rosto dentro
        c.ellipse(cx, HEAD_CY - 1, 5, 5, cloak or CLOAK)
        c.ellipse(cx, HEAD_CY + 1, 3, 3, face)
    else:
        c.ellipse(cx, HEAD_CY, 4, 4, face)

        if beard:
            c.ellipse(cx, HEAD_CY + 4, 3, 3, WHITE)
            c.rect(cx - 2, HEAD_CY + 1, 5, 3, WHITE)

        if hair:
            # calata e laterais, sem cobrir o miolo do rosto
            c.rect(cx - 4, HEAD_CY - 4, 9, 3, hair)
            c.rect(cx - 4, HEAD_CY - 2, 1, 4, hair)
            c.rect(cx + 4, HEAD_CY - 2, 1, 4, hair)
            if long_hair:
                c.rect(cx - 4, HEAD_CY + 1, 1, 10, hair)
                c.rect(cx + 4, HEAD_CY + 1, 1, 10, hair)

    if hat:
        c.rect(cx - 4, 0, 9, 5, body)
        c.rect(cx - 4, 3, 9, 1, hat_band)
        c.hline(5, cx - 7, cx + 7, body_dark)

    # --- rosto ------------------------------------------------------
    eye_y = HEAD_CY + (1 if hood else 1)
    c.set(cx - 2, eye_y, EYE)
    c.set(cx + 2, eye_y, EYE)

    # --- itens nas maos ---------------------------------------------
    if staff:
        c.vline(cx + 9, 9, 29, LEATHER_DARK)
        c.ellipse(cx + 9, 7, 1, 1, GLOW)
    if lantern:
        c.rect(cx + 6, 20, 3, 4, GOLD)
        c.rect(cx + 7, 21, 1, 2, GLOW)

    c.outline_silhouette(OUTLINE)
    return c


# --- os quatro personagens ----------------------------------------
def build() -> dict[str, Canvas]:
    return {
        # aventureiro de couro, cabelo escuro, botas
        "protagonista": humanoid(
            body=LEATHER,
            body_dark=LEATHER_DARK,
            hair=HAIR_DARK,
            lower="legs",
        ),
        # encapuzado na sombra, rosto palido, manto longo
        "estranho": humanoid(
            body=CLOAK_DARK,
            body_dark=CLOAK_DARK,
            cloak=CLOAK,
            lower="skirt",
            hood=True,
            face=PALE_SKIN,
        ),
        # vestido longo azul, cabelo longo, lanterna acesa
        "mulher_misteriosa": humanoid(
            body=CLOTH,
            body_dark=CLOTH_DARK,
            cloak=CLOTH_DARK,
            hair=HAIR_DARK,
            long_hair=True,
            lower="skirt",
            lantern=True,
        ),
        # barba branca, manto claro, chapeu e cajado
        "rei_mago": humanoid(
            body=ROBE,
            body_dark=ROBE_SHADE,
            hair=WHITE,
            lower="skirt",
            beard=True,
            hat=True,
            staff=True,
        ),
    }


def contact_sheet(sprites: dict[str, Canvas], scale: int = 4) -> Canvas:
    """Folha de contato: os 4 lado a lado, fundo escuro, ampliados."""
    pad = 8
    one = W * scale
    sheet = Canvas(len(sprites) * (one + pad) + pad, one + pad * 2, (32, 28, 42, 255))
    for i, canvas in enumerate(sprites.values()):
        big = Canvas(one, one)
        for y in range(one):
            for x in range(one):
                big.set(x, y, canvas.get(x // scale, y // scale))
        sheet.draw(big, pad + i * (one + pad), pad)
    return sheet


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprites em pixel art, sem API")
    parser.add_argument("--preview", action="store_true", help="gera a folha de contato")
    args = parser.parse_args()

    sprites = build()
    for name, canvas in sprites.items():
        path = settings.SPRITES_DIR / f"{name}.png"
        canvas.to_png(path)
        print(f"gerado: {path.name}  {canvas.w}x{canvas.h}")

    if args.preview:
        preview = ROOT / "preview_sprites.png"
        contact_sheet(sprites).to_png(preview)
        print(f"gerado: {preview.name}")

    print(f"\n{len(sprites)} sprites em {settings.SPRITES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
