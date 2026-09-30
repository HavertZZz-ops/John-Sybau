"""Constantes globais do jogo.

Resolucao, cores e caminhos ficam centralizados aqui para facilitar
ajustes durante o desenvolvimento.
"""
from __future__ import annotations

from pathlib import Path

# --- caminhos ---
ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
SPRITES_DIR = ASSETS_DIR / "sprites"
TILES_DIR = ASSETS_DIR / "tiles"
FONTS_DIR = ASSETS_DIR / "fonts"
SOUNDS_DIR = ASSETS_DIR / "sounds"

# --- janela ---
TILE_SIZE = 32
GAME_TITLE = "John Sybau"
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# --- paleta (RGB) ---
COLOR_BACKGROUND = (18, 16, 24)
COLOR_PANEL = (32, 28, 42)
COLOR_PANEL_LIGHT = (46, 40, 60)
COLOR_ACCENT = (196, 154, 76)
COLOR_TEXT = (232, 228, 238)
COLOR_TEXT_DIM = (150, 144, 164)
COLOR_DANGER = (178, 72, 72)
COLOR_PLACEHOLDER = (60, 54, 76)
COLOR_PLACEHOLDER_EDGE = (94, 86, 116)
