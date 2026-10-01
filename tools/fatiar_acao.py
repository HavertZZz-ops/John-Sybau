"""Fatia o Action_panel na mao.

O detector automatico achou ZERO paineis nessa folha: `Action_panel` e
uma folha solta com uma barra de 10 slots, uma faixa de titulo e varios
icones soltos, sem a grade regular que o detector procura.

A folha e 192x96. As coordenadas sao medidas com a grade de 16px do
`tools/preview_ui.py`, que e a mesma que o jogo usa como grade de arte.
"""

import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))
from src.ui_arte import UI_DIR  # noqa: E402

ORIGEM = UI_DIR / "fontes" / "Action_panel.png"
if not ORIGEM.is_file():
    raise SystemExit(
        f"folha nao encontrada: {ORIGEM}\n"
        "copie a original do pacote para assets/ui/fontes/"
    )

# nome, x, y, largura, altura  (folha 192x96, grade de 16)
RECORTES = [
    # a fileira de slots de madeira: e o que carrega as acoes.
    # 18 e nao 20 de altura: com 20 entrava a faixa colorida da linha
    # de icones logo abaixo e a barra saia com uma borda listrada.
    # Cortada em 86 e nao 168: o jogo tem cinco acoes e a folha tem dez
    # slots, e cinco slots vazios do lado pareciam painel quebrado.
    ("action_bar.png", 13, 46, 86, 18),
    # a faixa dourada do titulo, na mesma largura da barra
    ("action_header.png", 15, 18, 88, 17),
    # os icones soltos da metade de baixo
    ("icone_espada.png", 128, 67, 14, 14),
    ("icone_rosto.png", 144, 67, 14, 14),
    ("icone_escudo.png", 160, 67, 14, 14),
    ("icone_olho.png", 176, 67, 14, 14),
    ("icone_pocao_azul.png", 160, 82, 14, 14),
    ("icone_pocao_vermelha.png", 176, 82, 14, 14),
]

pygame.init()
# `convert_alpha` exige modo de video, mesmo sem janela: e o modo que
# deixa a folha em SRCALPHA, que e de onde saem os recortes.
pygame.display.set_mode((1, 1))
if not ORIGEM.is_file():
    raise SystemExit(f"folha nao encontrada: {ORIGEM}")
folha = pygame.image.load(str(ORIGEM)).convert_alpha()
print(f"folha: {folha.get_width()}x{folha.get_height()}  de {ORIGEM.name}")

# os icones ficam em icons/, nao na lista de paineis
ICONS = UI_DIR / "icones"
ICONS.mkdir(parents=True, exist_ok=True)

for nome, x, y, w, h in RECORTES:
    if x + w > folha.get_width() or y + h > folha.get_height():
        raise SystemExit(f"{nome} estourou a folha: {x + w}x{y + h}")
    pedaco = pygame.Surface((w, h), pygame.SRCALPHA)
    pedaco.blit(folha, (0, 0), pygame.Rect(x, y, w, h))
    destino = ICONS if nome.startswith("icone_") else UI_DIR
    pygame.image.save(pedaco, str(destino / nome))
    print(f"  {nome:26s} {w}x{h}  <- ({x},{y})")

print("\npronto")