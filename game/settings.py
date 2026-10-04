"""Configuracoes basicas do jogo.

Tudo que o resto do jogo precisa saber sobre a janela, o relogio e as
cores mora aqui. Nenhum outro modulo deve hardcodar `800` ou `60`: um
`clock.tick(60)` espalhado pelo codigo vira um pesadelo quando a
resolucao mudar, porque existem doze lugares diferentes que Precisariam
mudar juntos.

Este arquivo nao importa pygame de proposito. `settings` e lido pela
ferramenta de linha de comando e pelo servidor do Django em alguns
fluxos, e um modulo que abre uma janela ao ser importado nao pode ser
lido por um script que so quer o caminho das imagens.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- janela ---------------------------------------------------------------

# 800x600 e a resolucao classica de janela de projeto academico: cabe em
# qualquer monitor, inclui 4:3 e 16:9 sem distorcer o pixel art, e divide
# por 2 e por 3 certinho — o que importa para uma grade de tiles.
LARGURA = 800
ALTURA = 600

# O titulo aparece na barra da janela. `John Sybau` e o nome do jogo e o
# nome do arquivo de save ao mesmo tempo.
TITULO = "John Sybau"

# O icone e opcional: se o arquivo nao existir, o jogo abre normalmente
# com o icone padrao do pygame. Melhor um `try` do que uma excecao na
# inicializacao, porque um icone faltando nao e motivo para o jogo nao
# abrir.
ICONE = Path(__file__).parent / "assets" / "icone.png"

# --- tempo ----------------------------------------------------------------

# 60 FPS e o alvo, nao um teto de verdade. O `tick` limita o quao rapido o
# jogo desenha; com vsync ligado e o monitor a 60, o movimento fica
# travado no mesmo intervalo do monitor, que e o que o olho espera.
FPS = 60

# Se um quadro demorar mais que isto, o pygame mostra um aviso de
# lentidao. Em maquina de desenvolvimento com o debugger ligado e comum
# passar, e o aviso ajuda a achar o gargalo antes de o usuario ver.
LIMITE_DE_LENTIDAO_MS = 250

# O maior `dt` que uma cena recebe, em segundos. Um quadro que demorou
# mais que isto e tratado como se tivesse durado exatamente isto.
#
# Sem esse teto, arrastar a janela por 2 segundos entrega um dt de 2.0 e
# o jogador atravessa a parede oposta da sala num passo so. Limitando o
# dt, o mundo andar mais devagar durante o engasgo — que e o comportamento
# correto e o que todo motor com passo fixo faz.
LIMITE_DE_QUADRO = 1.0 / 15.0

# --- cores ----------------------------------------------------------------

# A paleta e pequena de proposito. Um jogo de aventura top-down le melhor
# com poucos tons bem escolhidos do que com uma paleta grande e gastada.
# O fundo preto e o que o jogo mostra enquanto nada esta desenhado; ele
# tambem esconde o "flash" de tela entre duas cenas.
PRETO = (0, 0, 0)
BRANCO = (255, 255, 255)

# Cinza para texto que nao e a informacao principal — instructions de
# rodape, contadores, o estado do inventario. O texto que o jogador
# PRECISA ler usa OURO ou BRANCO, nunca CINZA.
CINZA = (140, 140, 140)

# Dourado e a cor de destaque do jogo: vida cheia, pontuacao, o item que
# voce esta olhando. O olho vai para o dourado primeiro, entao ele so
# pode ser usado no que importa.
OURO = (255, 200, 60)

# Vermelho para dano, perigo e vida baixa. O vermelho puro (255, 0, 0) e
# berrante demais em tela escura e cansa a vista; o tom abaixo foi
# escurecido o bastante para ler sem vibrar.
VERMELHO = (200, 50, 50)
VERDE = (80, 200, 100)

# --- sprites ---------------------------------------------------------------

# A chave de transparencia. Os sprites vem de um pacote desenhado com o
# fundo em magenta, e `set_colorkey` transforma aquele magenta em
# transparencia.
#
# Por que magenta e nao verde ou preto: preto e uma cor que aparece
# legitimamente em sprite de roupa e de cabelo, entao o retangulo preto
# da borda fica visivel. Magenta quase nao aparece em pixel art de
# personagem, entao o recorte e limpo.
# (Se um dia os sprites vierem com canal alpha, o certo e usar
# `convert_alpha()` e esquecer a colorkey — as duas juntas nao
# funcionam.)
COR_CHAVE = (255, 0, 255)

# --- grade ----------------------------------------------------------------

# O tile e a unidade do mundo. Com sprites de 16x16 e uma escala de 2, o
# personagem ocupa 32x32 na tela e o tile de 32x32 deixa um tile de
# folga, o que faz a colisao por caixa nao raspar na parede.
TAMANHO_DO_TILE = 32

# --- caminhos -------------------------------------------------------------

# `PASTA_DE_ASSETS` e absoluto de proposito. Um caminho relativo quebra
# quando o jogo e iniciado de outro diretorio — e e exatamente isso que
# acontece quando o usuario clica no executavel em vez de rodar
# `python main.py` na pasta.
PASTA_DE_ASSETS = Path(__file__).parent / "assets"

# Atalho para abrir um arquivo de arte pelo nome, sem repetir o caminho
# em todo lugar.
def caminho_do_asset(nome_do_arquivo: str) -> Path:
    """Caminho de um arquivo dentro de `assets/`.

    Funcao e nao constante porque `assets` tem subpastas (`sprites/`,
    `tiles/`, `sfx/`) e cada uma delas vai repetir este prefixo.
    """
    return PASTA_DE_ASSETS / nome_do_arquivo


# --- ambiente -------------------------------------------------------------

# `SDL_VIDEODRIVER` permite rodar sem tela (CI, servidor, container). O
# jogo so define isto se a variavel de ambiente nao existir, para nao
# sobrescrever a escolha de quem esta rodando com um driver de verdade.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")