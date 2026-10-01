"""Confere que o heroi na tela e sempre o do conjunto equipado.

O jogo tem DOIS sistemas de arte do heroi: o desenho do PixelLab,
por conjunto de maos, e a animacao do pacote de mercado. Eles
divergem em tamanho e em equipamento, e o jogador via o personagem
trocar de desenho e de tamanho a cada passo.
"""
import pathlib
import sys

import pygame

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
sys.path.insert(0, str(RAIZ))

from src import assets, equipamento as eq  # noqa: E402
from src.progresso import Progresso  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))

FALHOU = 0


def checa(cond, msg):
    global FALHOU
    print(f"[ok] {msg}" if cond else f"[FALHOU] {msg}")
    if not cond:
        FALHOU += 1


ESC = 3
ALTURA_ESPERADA = assets.HERO_BASE[1] * ESC

# --- o desenho equipado tem a ALTURA do heroi animado ---------------
# Era 192px contra 120px na escala 3: o heroi parado era duas vezes
# maior que andando.
for c in eq.todos_os_conjuntos():
    arte = assets.equipado_na_tela(c.chave, ESC)
    checa(arte is not None, f"{c.chave}: o desenho carrega")
    if arte is None:
        continue
    h = arte.get_height()
    checa(
        h == ALTURA_ESPERADA,
        f"{c.chave}: altura {h} bate com o heroi animado "
        f"({ALTURA_ESPERADA})",
    )
    # um personagem em pe e mais ALTO que largo, entao 90x120 esta
    # certo. O que nao pode e ser um desenho esmagado (largura
    # pequena demais) nem esticado (largura enorme). O alvo e uma
    # faixa de 40% a 200% da altura.
    larg, alt_px = arte.get_width(), arte.get_height()
    checa(
        larg >= alt_px * 0.4,
        f"{c.chave}: nao foi esmagado ({larg}x{alt_px})",
    )
    checa(
        larg <= alt_px * 2,
        f"{c.chave}: nao esta esticado demais ({larg}x{alt_px})",
    )

# --- todos os conjuntos comecam desarmados ---------------------------
p = Progresso()
checa(p.arma is None, f"a partida comeca desarmado: {p.arma}")
checa(
    assets.equipado_na_tela(eq.chave_com_desenho(p.arma, p.escudo), ESC)
    is not None,
    "o heroi desarmado tem desenho pronto para a tela",
)

# --- a direcao das folhas e o que o codigo assume --------------------
from src import assets as A  # noqa: E402

for d in A.HERO_DIRECTIONS:
    andavel = assets.carregar_animacao(d, "idle")
    check = assets.carregar_animacao(d, "walk")
    checa(len(andavel) > 0, f"{d}: tem idle")
    checa(len(check) > 0, f"{d}: tem walk")

# --- a ordem das linhas por folha ------------------------------------
import re  # noqa: E402

imp = (RAIZ / "tools" / "import_sprites.py").read_text(encoding="utf-8")
idle = re.search(r"ESPADA_ORDEM_IDLE\s*=\s*\(([^)]*)\)", imp)
caminha = re.search(r"ESPADA_ORDEM_WALK\s*=\s*\(([^)]*)\)", imp)
checa(idle is not None and caminha is not None,
      "o importador tem uma ordem por folha")
if idle and caminha:
    i = tuple(x.strip().strip('"') for x in idle.group(1).split(","))
    w = tuple(x.strip().strip('"') for x in caminha.group(1).split(","))
    checa(len(i) == 4 and len(w) == 4, "as duas ordens tem 4 direcoes")
    checa(
        set(i) == set(w) == {"sul", "norte", "leste", "oeste"},
        f"as duas ordem cobrem as 4 direcoes: {i} e {w}",
    )
    checa(
        i[0] == w[0] == "sul",
        "a linha 0 e a frente nas duas folhas",
    )
    checa(
        i != w,
        "as ordens NAO sao iguais: e o motivo do bug de direcao",
    )

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\nheroi na tela: tudo certo")