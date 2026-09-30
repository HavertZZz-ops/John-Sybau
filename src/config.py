"""Configuracoes do jogo, salvas em JSON.

A tela de opcoes edita este arquivo, e o loop principal le antes de
criar a janela. Nada aqui e hardcoded: resolucao, tela cheia, vsync,
escala dos sprites e limite de FPS sao ajustaveis em tempo de execucao.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from . import settings

CONFIG_PATH = settings.ROOT_DIR / "config.json"

# resolucoes oferecidas na tela de opcoes, em pixels
RESOLUTION_CHOICES: tuple[tuple[int, int], ...] = (
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
)

# escalas de sprite oferecidas (multiplicador sobre o tamanho original)
SCALE_CHOICES: tuple[int, ...] = (1, 2, 3, 4)

# limites de FPS oferecidos
FPS_CHOICES: tuple[int, ...] = (30, 60, 120, 144, 0)  # 0 = ilimitado

VSYNC_CHOICES: tuple[bool, ...] = (False, True)


@dataclass
class Config:
    """Configuracoes ativas do jogo."""

    width: int = settings.SCREEN_WIDTH
    height: int = settings.SCREEN_HEIGHT
    fullscreen: bool = False
    vsync: bool = True
    sprite_scale: int = 3
    fps_limit: int = 60
    show_fps: bool = True
    # teclas por acao: {"mover_cima": ["up", "w"], ...}
    bindings: dict[str, list[str]] = field(default_factory=dict)

    # --- validacao ------------------------------------------------
    def clamp(self) -> "Config":
        """Ajusta valores invalidos, para um arquivo corrompido nao
        quebrar o jogo na hora de abrir."""
        if (self.width, self.height) not in RESOLUTION_CHOICES:
            self.width, self.height = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        if self.sprite_scale not in SCALE_CHOICES:
            self.sprite_scale = 3
        if self.fps_limit not in FPS_CHOICES:
            self.fps_limit = 60
        self.vsync = bool(self.vsync)
        self.fullscreen = bool(self.fullscreen)
        self.show_fps = bool(self.show_fps)
        return self

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def cycle_resolution(self, delta: int) -> None:
        index = RESOLUTION_CHOICES.index(self.size)
        self.width, self.height = RESOLUTION_CHOICES[
            (index + delta) % len(RESOLUTION_CHOICES)
        ]

    def cycle_scale(self, delta: int) -> None:
        index = SCALE_CHOICES.index(self.sprite_scale)
        self.sprite_scale = SCALE_CHOICES[(index + delta) % len(SCALE_CHOICES)]

    def cycle_fps(self, delta: int) -> None:
        index = FPS_CHOICES.index(self.fps_limit)
        self.fps_limit = FPS_CHOICES[(index + delta) % len(FPS_CHOICES)]

    def toggle(self, name: str) -> None:
        """Inverte um booleano (fullscreen, vsync, show_fps)."""
        setattr(self, name, not getattr(self, name))

    def reset_bindings(self) -> None:
        """Apaga o mapeamento customizado, voltando ao padrao."""
        self.bindings = {}

    def copy_from(self, other: "Config") -> None:
        """Copia tudo de outro config (usado pelo botao de restaurar)."""
        for f in fields(self):
            setattr(self, f.name, getattr(other, f.name))

    # --- persistencia ----------------------------------------------
    def save(self, path: Path = CONFIG_PATH) -> None:
        try:
            path.write_text(
                json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            print(f"[config] nao foi possivel salvar: {exc}")

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        """Le o arquivo de configuracao, se existir e for valido."""
        config = cls()
        if not path.is_file():
            return config
        try:
            raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[config] arquivo invalido, usando padrao: {exc}")
            return config

        known = {f.name: f.type for f in fields(cls)}
        for key, value in raw.items():
            if key in known:
                setattr(config, key, value)
        return config.clamp()


def native_refresh_rate() -> int | None:
    """Refresh rate do monitor principal, em Hz.

    Usa a API do Windows. Se nao der (outro sistema, API muda), devolve
    None e o jogo apenas usa o limite de FPS configurado.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class DEVMODE(ctypes.Structure):
            _fields_ = [
                ("dmDeviceName", wintypes.WCHAR * 32),
                ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD),
                ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD),
                ("dmFields", wintypes.DWORD),
                ("dmPositionX", ctypes.c_long),
                ("dmPositionY", ctypes.c_long),
                ("dmDisplayOrientation", ctypes.c_uint),
                ("dmDisplayFixedOutput", ctypes.c_uint),
                ("dmColor", ctypes.c_short),
                ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short),
                ("dmCollate", ctypes.c_short),
                ("dmFormName", wintypes.WCHAR * 32),
                ("dmLogPixels", wintypes.WORD),
                ("dmBitsPerPel", ctypes.c_uint),
                ("dmPelsWidth", ctypes.c_uint),
                ("dmPelsHeight", ctypes.c_uint),
                ("dmDisplayFlags", ctypes.c_uint),
                ("dmDisplayFrequency", ctypes.c_uint),
                ("dmICMMethod", ctypes.c_uint),
                ("dmICMIntent", ctypes.c_uint),
                ("dmMediaType", ctypes.c_uint),
                ("dmDitherType", ctypes.c_uint),
                ("dmReserved1", ctypes.c_uint),
                ("dmReserved2", ctypes.c_uint),
                ("dmPanningWidth", ctypes.c_uint),
                ("dmPanningHeight", ctypes.c_uint),
            ]

        best: tuple[int, int, int] | None = None
        index = 0
        while True:
            mode = DEVMODE()
            mode.dmSize = ctypes.sizeof(mode)
            if not ctypes.windll.user32.EnumDisplaySettingsW(
                None, index, ctypes.byref(mode)
            ):
                break
            if mode.dmPelsWidth and mode.dmPelsHeight and mode.dmDisplayFrequency:
                candidate = (
                    mode.dmPelsWidth,
                    mode.dmPelsHeight,
                    mode.dmDisplayFrequency,
                )
                if best is None or candidate[0] * candidate[1] > best[0] * best[1]:
                    best = candidate
            index += 1

        return best[2] if best else None
    except Exception:
        return None
