"""Carregamento de arte: sprites, tiles e icones.

Este modulo existe para que um sprite QUALQUER entre no jogo sem que
alguem precise lembrar de aplicar `convert_alpha` na mao. Sem ele, cada
cenario de carregamento vira uma linha repetida, e a primeira linha
repetida erra o suficiente para derrubar o jogo na hora de abrir.

O que ele resolve, em ordem de importancia:

1. **A transparencia tem dois jeitos e o jogo nao pode escolher um por
   acaso.** Sprite de pacote vem com fundo magenta e precisa de
   `set_colorkey`. Sprite produzido em editor moderno vem com canal
   alpha e precisa de `convert_alpha`. Aplicar os dois juntos da um
   sprite com a borda furada ou com o fundo preto. Aqui a escolha e
   feita uma vez, por arquivo, e fica registrada.

2. **A imagem so e lida do disco uma vez.** `pygame.image.load` dentro
   de um laco de desenho significa abrir o arquivo 60 vezes por segundo.
   Todo sprite carregado passa por um cache, e o cache so e invalidado
   quando a escala global muda.

3. **Arquivo faltando nao derruba o jogo.** Um sprite que nao existe
   vira um retangulo magenta com o nome do arquivo escrito dentro. E feio,
   e e muito melhor do que um crash no meio de uma luta.

Exemplo de uso:

    imagem = arte.carregar_sprite("heroi/idl_sul.png", escala=3)
    if imagem is not None:
        tela.blit(imagem, posicao)
"""
from __future__ import annotations

from pathlib import Path

import pygame

import settings

# O cache: chave para a Surface ja carregada e escalada.
#
# A chave inclui a escala porque a mesma imagem em escalas diferentes sao
# duas surfaces diferentes — `transform.scale` cria uma imagem nova e nao
# muda a original de lugar. Sem a escala na chave, o jogo devolveria o
# sprite do tamanho errado sem nenhum aviso.
_cache: dict[str, pygame.Surface] = {}

# Quantas vezes cada arquivo foi pedido e nao estava no disco.
#
# Contar e melhor que ignorar: um sprite faltando e quase sempre um nome
# digitado errado, e um nome errado que nunca aparece em log e um nome
# errado que o jogador ve como um retangulo vazio na tela.
_erros: dict[str, int] = {}

_debug = False


def definir_depuração(ativo: bool) -> None:
    """Liga ou desliga o aviso de arquivo faltando."""
    global _debug
    _debug = ativo


def limpar_cache() -> None:
    """Esquece tudo que foi carregado.

    Chamar depois de mudar a escala global: as surfaces do cache tem o
    tamanho antigo, e continuar usando elas deixa o sprite do tamanho
    errado depois da troca.
    """
    _cache.clear()


def caminho_de_sprite(nome: str) -> Path:
    """Caminho do arquivo a partir do nome logico.

    `nome` usa barra, nunca barra invertida: `"heroi/idl_sul.png"`.
    No Windows os dois funcionam, mas a barra e a que funciona em todo
    sistema — e um spriteheet montado em outra maquina precisa abrir
    igual em qualquer lugar.
    """
    return settings.PASTA_DE_ASSETS / "sprites" / nome


def _placeholder(nome: str) -> pygame.Surface:
    """Um retangulo magenta que diz o que esta faltando.

    So e chamado quando o arquivo realmente nao existe, entao o custo de
    desenhar o nome nao importa.
    """
    largura = altura = 64
    imagem = pygame.Surface((largura, altura))
    imagem.fill(settings.COR_CHAVE)
    pygame.draw.rect(imagem, settings.PRETO, imagem.get_rect(), 2)

    try:
        rotulo = pygame.font.Font(None, 12)
        # o nome em duas linhas: um nome de arquivo longo nao cabe em 64px,
        # e um texto cortado nao diz nada
        pedacos = nome.split("/")[-1].split(".")
        imagem.blit(rotulo.render(pedacos[0][:14], True, settings.PRETO), (3, 18))
        if len(pedacos) > 1:
            imagem.blit(
                rotulo.render(pedacos[1][:14], True, settings.PRETO), (3, 30)
            )
    except Exception:
        # Se nem a fonte carregou, o retangulo magenta ainda avisa que
        # falta alguma coisa. Uma excecao aqui derrubaria o jogo por causa
        # de um arquivo que existia so para ser um aviso.
        pass

    return imagem


def _tem_alpha(caminho: Path) -> bool:
    """O arquivo tem canal alpha de verdade?

    Le a imagem sem converter e olha o alpha do primeiro pixel. E o mais
    barato de distinguir: um PNG de 32 bits tem o canal; um de 24 bits —
    o formato dos pacotes antigos, com fundo magenta — nao tem.
    """
    try:
        bruta = pygame.image.load(str(caminho))
        if bruta.get_bitsize() >= 32:
            return bruta.get_at((0, 0))[3] < 255
        return False
    except Exception:
        return False


def carregar_sprite(
    nome: str,
    escala: int = 1,
    usar_alpha: bool | None = None,
) -> pygame.Surface | None:
    """Carrega um sprite, escalado e com a transparencia pronta.

    `nome` e o caminho dentro de `assets/sprites/`, com barra.

    `usar_alpha` decide a transparencia:
      - `True`  usa o canal alpha da propria imagem;
      - `False` apaga a cor-chave (magenta);
      - `None`  (padrao) descobre sozinho, lendo o arquivo.

    A descoberta automatica olha o primeiro pixel: em sprite de pacote, o
    canto e a cor-chave; em sprite com alpha, o canto e transparente. E
    uma heuristica, e por isso ela e o padrao e nao a obrigatoriedade —
    um sprite com fundo de verdade no canto e um caso legitimo, e nesse
    caso o argumento `usar_alpha=True` resolve.
    """
    caminho = caminho_de_sprite(nome)
    chave = f"{nome}|{escala}|{usar_alpha}"

    achada = _cache.get(chave)
    if achada is not None:
        return achada

    try:
        imagem = pygame.image.load(str(caminho))
    except (pygame.error, FileNotFoundError, OSError):
        _erros[nome] = _erros.get(nome, 0) + 1
        if _debug:
            print(f"[arte] sprite nao encontrado: {nome}")
        # Devolve o placeholder E memoiza. Sem memoizar, um sprite que
        # falta e redesenhado do zero a cada quadro — e o aviso some bem
        # na hora em que o jogador mais precisaria ver.
        marcador = _placeholder(nome)
        if escala > 1:
            marcador = pygame.transform.scale(
                marcador, (marcador.get_width() * escala,
                           marcador.get_height() * escala)
            )
        _cache[chave] = marcador
        return marcador

    # --- transparencia, decidida uma vez -------------------------------
    decidir = usar_alpha if usar_alpha is not None else _tem_alpha(caminho)

    if escala > 1:
        # `scale` e nao `smoothscale`, de proposito: em pixel art o filtro
        # suave transforma o quadriculado em borrao. O pixel art ampliado
        # tem que continuar sendo quadrado, mesmo que nao fique tao bonito.
        imagem = pygame.transform.scale(
            imagem, (imagem.get_width() * escala, imagem.get_height() * escala)
        )

    # A conversao vem DEPOIS da escala, e nao antes: `scale` devolve uma
    # imagem sem o formato de tela, e converter antes seria trabalho
    # jogado fora. Depois da escala, so o que importa e o canal alpha ou a
    # cor-chave.
    if decidir:
        imagem = imagem.convert_alpha()
    else:
        imagem = imagem.convert()
        imagem.set_colorkey(settings.COR_CHAVE, pygame.RLEACCEL)

    _cache[chave] = imagem
    return imagem


def carregar_sheet(
    nome: str,
    quadros: int,
    colunas: int,
    escala: int = 1,
) -> list[pygame.Surface]:
    """Fatia uma imagem em quadros de animacao.

    Um spriteheet e uma imagem unica com varios quadros lado a lado. Esta
    funcao corta, nao adivinha: quem chama diz quantos quadros tem e em
    quantas colunas eles estao — as duas informacoes que so o arquivo tem.

    Devolve lista de `quadros` imagens. Se a imagem for menor do que o
    grid diz, as fatias que faltam repetem a ultima: melhor um quadro
    repetido do que um `IndexError` no meio de uma animacao.
    """
    base = carregar_sprite(nome, escala=escala)
    if base is None:
        return []

    colunas = max(1, colunas)
    linhas = (quadros + colunas - 1) // colunas

    largura = base.get_width() // colunas
    altura = base.get_height() // max(1, linhas)

    if largura <= 0 or altura <= 0:
        return []

    fatias: list[pygame.Surface] = []
    for indice in range(quadros):
        linha, coluna = divmod(indice, colunas)
        x, y = coluna * largura, linha * altura
        if (x + largura <= base.get_width()
                and y + altura <= base.get_height()):
            fatias.append(base.subsurface((x, y, largura, altura)).copy())
        else:
            # o spriteheet tem menos quadros do que o jogo pediu
            fatias.append(fatias[-1] if fatias else base.copy())

    return fatias


def erros_de_carregamento() -> dict[str, int]:
    """Quantas vezes cada arquivo faltou. Para achar nome digitado errado."""
    return dict(_erros)