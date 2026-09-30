"""Importa os sprites dos pacotes baixados para dentro do jogo.

Os pacotes ficam em ~/Downloads e nao entram no repositorio: sao
originais do autor, com licenca propria. Este script extrai so o que o
jogo usa e escreve em assets/, entao da para refazer a importacao a
qualquer momento sem perder nada.

    python tools/import_sprites.py

O que entra:
  - Dungeon_Tileset.png  -> assets/tiles/dungeon_tileset.png
  - char_run_*           -> assets/sprites/hero/hero_<dir>_walk_<n>.png
  - char_idle_*          -> assets/sprites/hero/hero_<dir>_idle_<n>.png

O personagem do pacote tem 16x16. A pipeline do jogo ja sabe escalar
por inteiro a partir de uma imagem quadrada, entao cada quadro e
dobrado para 32x32 na importacao e a escala 1x..4x continua valendo
igual (3x passa a dar 96x96, perto dos 96x114 do heroi antigo).
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOWNLOADS = Path.home() / "Downloads"
ADVENTURE_ZIP = DOWNLOADS / "Top_Down_Adventure_Pack_v.1.0.zip"
PACK = "Top_Down_Adventure_Pack_v.1.0"

TILES_DIR = ROOT / "assets" / "tiles"
HERO_DIR = ROOT / "assets" / "sprites" / "hero"

# nome do pacote -> direcao do jogo
DIRECTIONS = {
    "down": "sul",
    "up": "norte",
    "left": "oeste",
    "right": "leste",
}

FRAME = 16
UPSCALE = 2


def extract(paths: dict[str, Path], dest: Path) -> None:
    """Extrai do zip os arquivos pedidos, se ainda nao existirem."""
    if not ADVENTURE_ZIP.is_file():
        raise SystemExit(
            f"pacote nao encontrado: {ADVENTURE_ZIP}\n"
            "baixe o Top_Down_Adventure_Pack_v.1.0.zip para ~/Downloads"
        )
    with zipfile.ZipFile(ADVENTURE_ZIP) as zf:
        for name, out in paths.items():
            if out.exists():
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(f"{PACK}/{name}") as src, out.open("wb") as dst:
                dst.write(src.read())
            print(f"  extraido: {out.relative_to(ROOT)}")


def split_strip(image_path: Path, dest: Path, prefix: str, state: str) -> int:
    """Quebra uma tira de 6 quadros em PNGs individuais, dobrados."""
    import pygame

    pygame.init()
    try:
        sheet = pygame.image.load(image_path)
    finally:
        pygame.quit()

    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for i in range(sheet.get_width() // FRAME):
        frame = sheet.subsurface(pygame.Rect(i * FRAME, 0, FRAME, FRAME))
        big = pygame.transform.scale(
            frame, (FRAME * UPSCALE, FRAME * UPSCALE)
        )
        out = dest / f"hero_{prefix}_{state}_{i}.png"
        pygame.image.save(big, out)
        count += 1
    return count


def main() -> int:
    if not ADVENTURE_ZIP.is_file():
        print(f"AVISO: {ADVENTURE_ZIP.name} nao esta em ~/Downloads")
        print("       o resto da importacao sera pulado")
        return 1

    raw = ROOT / "assets" / "raw"
    wanted: dict[str, Path] = {}

    # tiles da masmorra
    wanted["Dungeon_Tileset.png"] = raw / "Dungeon_Tileset.png"

    # tiras do personagem: idle e corrida, 4 direcoes
    for pack_dir, state in (
        ("idle", "idle"),
        ("run", "walk"),
    ):
        for pack_dir_word, direction in DIRECTIONS.items():
            name = (
                f"Char_Sprites/char_{pack_dir}_{pack_dir_word}"
                f"_anim_strip_6.png"
            )
            wanted[name] = raw / name

    print("extraindo:")
    extract(wanted, raw)

    print("escrevendo tiles:")
    src = raw / "Dungeon_Tileset.png"
    if src.is_file():
        TILES_DIR.mkdir(parents=True, exist_ok=True)
        target = TILES_DIR / "dungeon_tileset.png"
        target.write_bytes(src.read_bytes())
        print(f"  {target.relative_to(ROOT)}")

    print("escrevendo personagem:")
    total = 0
    # estado do jogo -> prefixo da tira no pacote
    strips = {"idle": "idle", "walk": "run"}
    for state, prefix_word in strips.items():
        for pack_dir_word, direction in DIRECTIONS.items():
            name = f"char_{prefix_word}_{pack_dir_word}_anim_strip_6.png"
            path = raw / "Char_Sprites" / name
            if not path.is_file():
                print(f"  PULADO (ausente): {name}")
                continue
            n = split_strip(path, HERO_DIR, direction, state)
            total += n
            print(f"  {direction:7} {state:5} {n} quadros")

    print(f"\npronto: {total} quadros do heroi")
    return 0


if __name__ == "__main__":
    sys.exit(main())