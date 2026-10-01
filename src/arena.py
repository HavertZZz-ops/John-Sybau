"""A sala da luta, desenhada como uma sala e nao como um retangulo.

A luta acontecia sobre um retangulo liso com uma linha no meio: parede
chapada em cima, uma faixa preta embaixo, e os lutadores pequenos no
meio de um vao. A foto do jogador mostra o problema inteiro numa imagem
so: parede marrom com um pontilhado, chao preto, e um boneco em 22% da
altura da janela.

Aqui a arena e montada uma vez por tamanho de janela e guardada em
cache. O que ela faz, e por que cada parte:

  - **Parede em fiadas.** A arte do pacote tem uma peca de parede
    solida (a chave `PPPP` da grade Wang). Em vez de repetir um tile
    qualquer, a parede usa essa peca em fiadas horizontais, com a fiada
    de baixo mais clara. Sao fiadas de verdade, e o olho le alvenaria.
    A fiada do topo e mais escura: a luz da cena cai de cima para o
    chao, e a parede escurece para o alto como massa.

  - **Chao em perspectiva.** O chao nao e uma faixa: e uma superficie
    que cresce em direcao a camera. Cada fiada e desenhada mais alta e
    mais larga que a anterior, o que da a leitura de que o chao se
    aproxima. O ladrilho vem do tileset da masmorra, o mesmo do mapa, e
    a linha do horizonte fica no mesmo lugar para o heroi e para os
    inimigos.

  - **Tochas.** A arena e uma catacumba: sem luz, uma parede cinza e
    um chao cinza. A tocha e o que cria o foco e a profundidade, e o
    brilho dela e o que separa o primeiro plano do fundo.

  - **Sobras.** Cada lutador ganha uma sombra elipse no chao. Sem
    sombra o boneco parece贴着 na parede, e nao apoiado no chao.

A arena e so o fundo. Lutadores, barras e menus sao desenhados pela
cena, por cima.
"""
from __future__ import annotations

import pygame

# a linha do horizonte, em fracao da altura da janela. E a mesma marca
# que a cena usa para ancorar lutadores pelo pe: se o fundo e os
# lutadores discordarem da linha, os bonecos flutuam.
HORIZONTE = 0.58

# quantas fiadas de chao, de tras para a frente. Mais fiada e mais
# perspectiva; menos fiada e o chao volta a ser uma faixa.
FIADAS_CHAO = 7
# a parede ocupa o que sobra acima do horizonte
FIADAS_PAREDE = 9
# a altura da primeira fiada da parede, em fracao da altura da janela.
# A parede comeca pequena, como quem esta longe.
FIADA_PAREDE_INICIO = 0.045
FIADA_PAREDE_FIM = 0.085

# A tocha e desenhada em duas partes: a CHAMA, pequena e quente, e o
# brilho em volta dela.
#
# O alcance e medido pelo diametro, e nao pelo raio. Com raio de 0.34 da
# altura o halo virava um disco de 245px de diametro, do tamanho de um
# quarto da tela, e a parede inteira ficava amarela. O que a cena pedia
# era um foco, nao um sol.
# O alcance e uma FRACAO DA ALTURA da janela, nao da largura. Com 0.30
# numa janela 1008x720, o diametro do halo dava 432px: mais da metade da
# tela, e ele nao era um foco. O que importa e o diametro em RELACAO A
# ALTURA: 0.22 da altura da janela e um disco do tamanho de uma
# personagem, que e o que um foco de tocha deve ser.
ALCANCE_TOCHA = 0.22
# O alfa maximo do halo e o TOTAL de luz somada no centro da tocha, e
# nao o alfa de um anel. O halo e desenhado em aneis, cada um com o
# alfa decai: com 30 por anel e ~73 aneis empilhados, o centro recebia
# mais de mil de luz e estourava em branco chapado. A imagem da arena
# mostrava um disco amarelo solido do tamanho de um quarto da tela.
#
# A soma e o que importa. Este e o total que o centro deve receber, e os
# aneis dividem esse total entre eles.
# O total de luz no CENTRO do halo, em canais de cor. A parede das
# catacumbas e azul-escura, uns (40, 50, 66). Com 150 de luz somada no
# centro o vermelho ia de 40 para 190: a parede ficava alaranjada, e o
# anel logo ao lado dava 226. O halo tem que ser um ACENTO na pedra, nao
# uma luz que troca a cor da parede: 60 deixa a pedra azul STILL
# azul-escura no centro, so que mais quente.
LUZ_TOCHA = 60
RAIO_TOCHA = 4

_cache: dict[tuple[int, int, str], pygame.Surface] = {}


def _pedra(cenario, lado: int) -> pygame.Surface | None:
    """A peca de parede solida do tileset, escalada.

    A chave toda-`True` da grade Wang e o interior da parede: os quatro
    cantos sao parede. Devolve None sem a arte, e a arena cai no
    desenho liso, que e melhor do que nao desenhar nada.
    """
    try:
        from . import dungeon_scene

        tabela = dungeon_scene._tabela_wang(cenario)
        if not tabela:
            return None
        peca = tabela.get((True, True, True, True))
        if peca is None:
            # qualquer peca com parede serve melhor do que nenhuma
            peca = next((v for k, v in tabela.items() if any(k)), None)
        if peca is None:
            return None
        return pygame.transform.scale(peca, (lado, lado))
    except Exception:  # noqa: BLE001 - a arte e opcional
        return None


def _ladrilho(cenario, lado: int) -> pygame.Surface | None:
    """O ladrilho de chao puro do tileset, escalado."""
    try:
        from . import dungeon_scene

        tabela = dungeon_scene._tabela_wang(cenario)
        if not tabela:
            return None
        peca = tabela.get((False, False, False, False))
        if peca is None:
            peca = next(iter(tabela.values()))
        return pygame.transform.scale(peca, (lado, lado))
    except Exception:  # noqa: BLE001 - a arte e opcional
        return None


def _parede(w: int, h: int, horizonte: int, cenario,
            pedra: pygame.Surface | None) -> None:
    """A parede de tras, em fiadas que crescem para baixo.

    A peca de pedra do tileset ja vem com a junta desenhada dentro. A
    fiada encolhe a peca para a altura da fiada e a repete, entao a
    junta da arte E a junta da parede: nao se acrescenta uma linha por
    cima, que e o que dava a tarja preta atravessando a parede a cada
    fiada na primeira versao.

    Cada fiada e um pouco mais clara que a de cima. E nao a ilumina��ao:
    e perspectiva, com a fiada de baixo mais perto da camera.
    """
    surf = surf_cache[0]
    y = 0
    fiada = max(10, int(h * FIADA_PAREDE_INICIO))
    passo = 0
    while y < horizonte:
        # o quanto a parede clareia por fiada. Com 98 fiadas e um degrau
        # fixo o topo virava preto e a base virava branco.
        claro = min(46, 8 + passo // 2)
        pygame.draw.rect(
            surf, (24 + claro // 3, 24 + claro // 4, 28 + claro // 5),
            pygame.Rect(0, y, w, fiada)
        )
        if pedra is not None:
            # a peca e encolhida para a fiada: a junta dela vira a junta
            # da parede, e a fiada parece ter a altura que tem
            altura_p = max(4, fiada - 1)
            p = pygame.transform.scale(pedra, (pedra.get_width(), altura_p))
            # o deslocamento e por fiada: as fiadas nao sao copias uma
            # da outra, e a parede para de ter um padrao vertical
            x = -((passo * p.get_width() // 2) % p.get_width())
            while x < w:
                surf.blit(p, (x, y))
                x += p.get_width()
            if y + fiada < horizonte:
                pygame.draw.line(
                    surf, (16, 15, 18), (0, y + fiada - 1), (w, y + fiada - 1)
                )
        y += fiada
        fiada = int(fiada * 1.22)
        passo += 1
    if y < horizonte:
        pygame.draw.rect(surf, (56, 52, 46), pygame.Rect(0, y, w, horizonte - y))


def _chao(w: int, h: int, horizonte: int,
          ladrilho: pygame.Surface | None) -> None:
    """O chao em perspectiva: cada fiada maior que a de tras.

    O ladrilho do tileset e repetido em fiadas, e cada fiada e desenhada
    com o ladrilho MAIOR que a de tras. A junta entre fiadas e uma linha
    fina e escura: e o que separa um degrau do outro, e sem ela o chao
    vira um so ladrilho gigante.

    O ladrilho tambem clareia para a frente, como a parede escurecia
    para o alto: o chao perto da camera recebe mais luz.
    """
    surf = surf_cache[0]
    altura = h - horizonte
    if altura <= 0:
        return
    if ladrilho is None:
        pygame.draw.rect(surf, (34, 31, 27), pygame.Rect(0, horizonte, w, altura))
        return

    lado_fiada = max(8, int(altura / FIADAS_CHAO * 1.3))
    y = horizonte
    for i in range(FIADAS_CHAO):
        frac = i / FIADAS_CHAO
        y2 = horizonte + int(altura * ((i + 1) / FIADAS_CHAO) ** 1.7)
        if y2 <= y:
            continue
        lado = max(8, int(lado_fiada * (1 + frac * 0.85)))
        px = pygame.transform.scale(ladrilho, (lado, lado))
        cols = int(w / lado) + 2
        rows = max(1, int((y2 - y) / lado) + 1)
        # o ladrilho anda de fiada em fiada, senao todas as fiadas
        # comecam na mesma coluna e o chao ganha um risco vertical
        desloc = (i * lado * 3 // 4) % lado
        for r in range(rows):
            py = y + r * lado
            if py >= y2:
                break
            for c in range(cols):
                surf.blit(px, (c * lado - desloc, py))
        # a junta da fiada
        if y2 < h:
            pygame.draw.line(surf, (26, 23, 20), (0, y2 - 1), (w, y2 - 1))
        y = y2


def _tochas(w: int, h: int, horizonte: int) -> list[tuple[int, int]]:
    """As tochas da parede, e onde fica o brilho de cada uma.

    Duas, uma de cada lado, e nunca na faixa do meio: e onde os lutadores
    ficam, e a tocha no meio da briga distrai do golpe.
    """
    return [
        (int(w * 0.10), horizonte - int(h * 0.16)),
        (int(w * 0.90), horizonte - int(h * 0.16)),
    ]


def _brilho(surf: pygame.Surface, x: int, y: int, h: int, tempo: float) -> None:
    """O halo quente da tocha, pulsando devagar."""
    raio = int(h * ALCANCE_TOCHA)
    # o pulso e o seno do tempo da cena: a chama treme, e e o unico
    # movimento do fundo
    pulso = 0.86 + 0.14 * (0.5 + 0.5 * _seno(tempo, 2.1))
    r = max(8, int(raio * pulso))
    # A luz e pintada numa superficie OPACA, sem canal alpha.
    #
    # `BLEND_RGBA_ADD` ignora o alpha: ele soma os canais RGB como
    # vierem. Com uma superficie SRCALPHA cheia de (255, 176, 92) e
    # alpha de 1 a 255, o pygame somava 255 no vermelho em TODO pixel do
    # disco, e o halo virava branco chapado independente do alpha.
    # Foi por isso que baixar o alfa nao resolveu nada, e foram tres
    # tentativas antes de a causa aparecer.
    #
    # Aqui a cor E a luz: preto e ausencia de luz, e a cor quente e o
    # maximo. `BLEND_RGB_ADD` soma exatamente o que esta escrito.
    brilho = pygame.Surface((r * 2, r * 2))
    for dy in range(-r, r):
        for dx in range(-r, r):
            d = (dx * dx + dy * dy) ** 0.5
            if d > r:
                brilho.set_at((dx + r, dy + r), (0, 0, 0))
                continue
            t = d / r
            parcela = LUZ_TOCHA * (1.0 - t) ** 1.9 / 255.0
            brilho.set_at((dx + r, dy + r), (
                int(255 * parcela),
                int(176 * parcela),
                int(92 * parcela),
            ))
    # a chama por cima do halo: soma em cima da propria luz, e e ela
    # que fica branca
    pygame.draw.rect(brilho, (226, 150, 60),
                     pygame.Rect(r - RAIO_TOCHA, r - RAIO_TOCHA - 3,
                                 RAIO_TOCHA * 2, RAIO_TOCHA * 2 + 3))
    pygame.draw.rect(brilho, (255, 244, 208),
                     pygame.Rect(r - RAIO_TOCHA + 1, r - RAIO_TOCHA - 2,
                                 RAIO_TOCHA * 2 - 2, RAIO_TOCHA * 2 + 1))
    pygame.draw.rect(brilho, (255, 255, 248),
                     pygame.Rect(r - 1, r - RAIO_TOCHA, 2, RAIO_TOCHA * 2))
    surf.blit(brilho, (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)


def _seno(t: float, periodo: float) -> float:
    import math

    return math.sin(t / periodo * math.tau)


def arena(w: int, h: int, cenario, tempo: float = 0.0) -> pygame.Surface:
    """O fundo da luta, cacheado por tamanho de janela e por cenario."""
    chave = (w, h, cenario.nome if cenario else "")
    base = _cache.get(chave)
    horizonte = int(h * HORIZONTE)

    if base is None:
        base = pygame.Surface((w, h))
        global surf_cache
        surf_cache = [base]
        _parede(w, h, horizonte, cenario, _pedra(cenario, max(16, int(h * 0.06))))
        _chao(w, h, horizonte, _ladrilho(cenario, max(16, int(h * 0.07))))
        # o rodape: a fiada onde a parede encontra o chao, mais clara,
        # que separa os dois planos
        pygame.draw.rect(base, (52, 48, 42), pygame.Rect(0, horizonte - 4, w, 4))
        pygame.draw.line(base, (16, 15, 14), (0, horizonte), (w, horizonte))
        surf_cache = []
        _cache[chave] = base

    # O brilho vai numa COPIA, nunca no fundo em cache.
    #
    # Somar luz no fundo cacheado e a mesma coisa que somar luz na
    # parede: a cada chamada a tocha clareava mais a parede em volta, e
    # depois de alguns segundos a tela ficava amarela. O teste pegou
    # isso medindo a MESMA regiao depois de duas chamadas: o anel do
    # halo ja dava 255 quando deveria dar menos de 200.
    #
    # A copia e o custo: uma superficie por quadro, o que a arena
    # cacheada evitava. E a unica forma de o halo ser pulsante sem
    # ferir o fundo.
    saida = base.copy()
    for x, y in _tochas(w, h, horizonte):
        _brilho(saida, x, y, h, tempo)
    return saida


def sombra_chao(surf: pygame.Surface, x: int, y: int,
                largura: int, fracao: float = 1.0) -> None:
    """A sombra de um lutador, no chao.

    Sem ela o boneco parece colado na parede. A sombra e achatada e
    esta no chao, e ela encolhe quando o lutador esta no ar.
    """
    meia = max(6, int(largura * 0.5))
    altura = max(3, int(largura * 0.16 * max(0.4, fracao)))
    sombra = pygame.Surface((meia * 2, altura), pygame.SRCALPHA)
    pygame.draw.ellipse(
        sombra, (0, 0, 0, 110), pygame.Rect(0, 0, meia * 2, altura)
    )
    surf.blit(sombra, sombra.get_rect(center=(x, y)))


def limpar_cache() -> None:
    _cache.clear()


# `surf_cache` e o alvo das funcoes que pintam. Existe para nao passar a
# superficie por parametro em cada uma; a arena monta, usa e limpa.
surf_cache: list = []