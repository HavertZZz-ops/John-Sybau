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

# resolucoes oferecidas na tela de opcoes, em pixels logicos.
# A lista e filtrada em tempo de execucao pelo que cabe na tela, e a
# resolucao nativa do desktop e incluida automaticamente, entao uma
# tela 1536x960 ganha essa opcao mesmo sem estar aqui.
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
    # teclas por acao: {"mover_cima": ["up", "w"], ...}
    bindings: dict[str, list[str]] = field(default_factory=dict)

    # --- validacao ------------------------------------------------
    def clamp(self) -> "Config":
        """Ajusta valores invalidos, para um arquivo corrompido nao
        quebrar o jogo na hora de abrir."""
        self.width = int(self.width or settings.SCREEN_WIDTH)
        self.height = int(self.height or settings.SCREEN_HEIGHT)
        # coerido antes de ser lido abaixo: o limite depende do modo
        self.fullscreen = bool(self.fullscreen)

        # invertido (altura maior que largura) e config invalido: corrige
        if self.height > self.width:
            self.width, self.height = self.height, self.width

        # a resolucao precisa caber na tela; senao o jogo abre com a
        # janela estourando a lateral e o menu fica inacessivel.
        # O limite depende do modo: em janela a moldura e descontada, em
        # tela cheia nao ha moldura e a superficie e escalada pelo SDL.
        limit = (
            logical_desktop_size()
            if self.fullscreen
            else usable_window_size()
        )
        if limit:
            if self.width > limit[0] or self.height > limit[1]:
                self.width = min(self.width, limit[0])
                self.height = min(self.height, limit[1])

        # so agora, depois de ajustar para o que cabe, se ainda assim o
        # tamanho estiver absurdo (0x0, arquivo lixo), volta ao padrao.
        # A checagem NAO e contra RESOLUTION_CHOICES: essa lista e so a
        # oferta do menu. A maior resolucao que cabe no desktop e
        # adicionada em tempo de execucao e nunca esta na lista, entao
        # exigir pertencer a ela fazia o config salvo com ela voltar
        # para 1280x720 em toda abertura. Era esse o bug de "a
        # resolucao nao fica": a escolha era aceita, salva, e descartada
        # na hora de carregar.
        if self.width < 640 or self.height < 360:
            self.width, self.height = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT

        if self.sprite_scale not in SCALE_CHOICES:
            self.sprite_scale = 3
        if self.fps_limit not in FPS_CHOICES:
            self.fps_limit = 60
        self.vsync = bool(self.vsync)
        self.fullscreen = bool(self.fullscreen)
        return self

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def available_resolutions(self) -> tuple[tuple[int, int], ...]:
        """Resolucoes que cabem na tela, mais a que estiver em uso.

        Uma resolucao maior que o desktop logico cria uma janela maior
        que a tela: sobra uma faixa em branco na direita e embaixo. Em
        vez de oferecer e falhar, a lista e filtrada. A resolucao atual
        sempre entra, senao um config antigo com 2560x1440 ficaria
        travado sem como sair.

        O limite depende do modo, e essa distincao e o que mantem a
        tela cheia funcionando:

        - em JANELA a resolucao e o tamanho da janela, que tem borda e
          barra de titulo. O desktop e descontado de uma moldura
          medida de verdade.
        - em TELA CHEIA a resolucao e a superficie de desenho, que o
          SDL escala para a tela inteira. Nao ha moldura, e usar uma
          aqui faria o filtro oferecer resolucoes pequenas demais.
        """
        from .config import usable_window_size

        # o limite e o desktop MENOS a moldura: uma janela do tamanho
        # exato do desktop ultrapassa a tela, porque a borda e a barra
        # de titulo somam alguns pixels de cada lado
        limit = (
            logical_desktop_size()
            if self.fullscreen
            else usable_window_size()
        )
        if not limit:
            return RESOLUTION_CHOICES

        usable = [
            r
            for r in RESOLUTION_CHOICES
            if r[0] <= limit[0] and r[1] <= limit[1]
        ]

        # a maior resolucao que cabe entra como opcao: e a que
        # preenche a tela sem sobrar pedaco
        nativa = limit
        if nativa not in usable and nativa[0] >= 640 and nativa[1] >= 360:
            usable.append(nativa)

        # a resolucao em uso entra, MAS so se ela realmente couber.
        # Sem isso, um config salvo com 1536x960 voltaria a ser
        # oferecida e o jogador escolheria de novo uma janela que
        # ultrapassa a tela.
        if self.size not in usable and (
            self.size[0] <= limit[0] and self.size[1] <= limit[1]
        ):
            usable.append(self.size)

        usable.sort()
        return tuple(usable)

    def cycle_resolution(self, delta: int) -> None:
        choices = self.available_resolutions()
        if self.size not in choices:
            choices = RESOLUTION_CHOICES
        index = choices.index(self.size)
        self.width, self.height = choices[(index + delta) % len(choices)]

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

    def sync_from_input_map(self, controls) -> None:
        """Copia o mapeamento vivo do InputMap para o config.

        O remapeamento acontece no InputMap (que as cenas consultam),
        enquanto este dataclass e o que vai para o arquivo. Sem esta
        copia, a tela mostra a tecla nova mas o config.json fica vazio.
        """
        self.bindings = controls.to_dict()

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


def usable_window_size() -> tuple[int, int] | None:
    """Maior resolucao de janela que cabe na tela, descontando a moldura.

    O desktop logico e a area da tela, mas a janela tem borda e barra de
    titulo: pedir 1536x960 (o desktop inteiro) cria uma janela de
    1552x999, que passa da tela. Por isso a moldura e descontada.

    A moldura e medida no jogo com a janela ja aberta e guardada num
    cache. Medir e abrir sao coisas que nao podem depender uma da outra:
    o filtro roda antes da janela existir. Sem medicao, cai num valor
    tipico de Windows.
    """
    desktop = logical_desktop_size()
    if not desktop:
        return None

    frame = _FRAME_CACHE or (16, 39)
    return (
        max(640, desktop[0] - frame[0]),
        max(360, desktop[1] - frame[1]),
    )


# moldura real da janela, medida no startup
_FRAME_CACHE: tuple[int, int] | None = None


def set_window_frame(frame: tuple[int, int]) -> None:
    """Guarda a moldura medida, para o filtro de resolucao usar.

    Medicao absurda e descartada. Uma borda de janela tem poucos pixels:
    16 de lado e 39 de altura no Windows com barra de titulo. Se a
    medicao vier muito maior, nao e moldura, e sim alguma outra coisa
    (o espaco da escala em tela cheia, ou uma janela nao recriada), e
    aceitar o numero faria o filtro rebaixar a resolucao do jogador sem
    ele pedir. Errar para o padrao e melhor do que persistir o errado.

    (0, 0) tambem e descartado, e este era o mais importante: e o que
    `measure_window_frame` devolve em tela cheia. Aceitava, apagava o
    cache, e o limite voltava a ser o desktop inteiro (1536x960) em vez
    do desktop menos a moldura (1520x921). Com o limite errado, o
    filtro oferecia 1536x960 como tamanho de JANELA, e essa janela nao
    cabe: 1536 mais 16 de bordura da 1552 numa area de 1536.
    """
    global _FRAME_CACHE
    if frame[0] < 0 or frame[1] < 0:
        return
    if frame[0] == 0 and frame[1] == 0:
        return  # tela cheia: nao existe moldura para medir
    if frame[0] > 64 or frame[1] > 96:
        return
    _FRAME_CACHE = (int(frame[0]), int(frame[1]))


def logical_desktop_size() -> tuple[int, int] | None:
    """Tamanho util da tela em pixels logicos, ja considerando DPI.

    Com DPI 125%, uma tela de 1920x1200 fisicos vale 1536x960 logicos,
    e e esse numero que limita a janela. Se pygame ainda nao foi
    inicializado, nao ha como descobrir: devolve None.
    """
    try:
        import pygame

        if not pygame.display.get_init():
            return None
        sizes = pygame.display.get_desktop_sizes()
        return max(sizes) if sizes else None
    except Exception:
        return None
