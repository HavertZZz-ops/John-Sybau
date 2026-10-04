"""O protagonista: movimento, colisao e o que o corpo dele ocupa.

Tudo que este modulo faz cabe em uma ideia: **o que o olho ve nao e o
que colide.** Um sprite de 32x32 desenhado com os pes no meio da imagem
precisa de uma caixa nos pes, senao o personagem "anda dentro" da parede
pela metade do corpo. Por isso a maior parte deste arquivo e sobre caixas.

Tres decisoes que mudam o resultado, e que estao comentadas onde ocorrem:

1. **Mover e por velocidade, nao por celula.** Integrar
   `velocidade * dt` a cada quadro e o que da animacao de caminhada do
   tamanho certo. O passo por celula exato so serve para o _: as teclas
   usam `pygame.key.get_pressed()`, que devolve estado, e nao evento — e
   estado significa "ainda apertado".

2. **A colisao testa as quatro celulas que a caixa toca.** Uma caixa
   maior que um tile esta em quatro celulas ao mesmo tempo; testar so a
   celula do canto deixa atravessar parede na diagonal.

3. **Os eixos sao testados um por vez.** E o que faz o heroi escorregar
   na parede em vez de grudar nela quando se aperta duas direcoes.
"""
from __future__ import annotations

import pygame

import arte
import settings

# --- movimento -------------------------------------------------------------

# Velocidade em pixels por segundo.
#
# O numero nao e gosto, e consequencia do tamanho da tela: em 800x600 com
# tile de 32, quem anda a 150px/s cruza a tela em 5 segundos. Acima de
# ~180 a sensacao e de teleporte, porque o cenario nao da tempo de ser
# lido enquanto o personagem atravessa.
VELOCIDADE_ANDANDO = 150.0

# A corrida e 1.7x, e nao 2x. A diferenca precisa CABER na tela: a 2x o
# personagem sai do campo de visao em 2,7 segundos e o jogador perde o
# lugar de onde veio.
FATOR_CORRIDA = 1.7

# O fator de multiplicacao da arte. Com `escala=2`, um sprite de 16x16 vira
# 32x32 — exatamente um tile, que e a escala que faz o desenho nao ficar
# pequeno em 800x600.
ESCALA_SPRITE = 2

# As quatro direcoes e o vetor de cada uma. Tabela e nao `if`: quatro
# `if` com sinal trocado e o caminho classico do heroi que so anda para a
# esquerda quando se aperta para a direita.
DIRECOES: dict[str, pygame.Vector2] = {
    "norte": pygame.Vector2(0, -1),
    "sul": pygame.Vector2(0, 1),
    "leste": pygame.Vector2(1, 0),
    "oeste": pygame.Vector2(-1, 0),
}

# Teclas por direcao: WASD. Um jogo que aceita so um padrao obriga quem
# jogou o outro a reaprender — e por isso que as duas familias existem em
# quase todo jogo 2D.
TECLAS_DIRECAO: dict[str, tuple[int, ...]] = {
    "norte": (pygame.K_w, pygame.K_UP),
    "sul": (pygame.K_s, pygame.K_DOWN),
    "leste": (pygame.K_d, pygame.K_RIGHT),
    "oeste": (pygame.K_a, pygame.K_LEFT),
}

# A ordem de prioridade quando duas direcoes estao apertadas. Norte antes
# de sul porque, com dois dedos, cima e o que o jogador acerta primeiro —
# e o boneco virando para baixo quando o jogador quer subir e o tipo de
# detalhe que so se percebe jogando.
ORDEM_DIRECOES = ("norte", "sul", "leste", "oeste")


def correndo_agora() -> bool:
    """O Shift esta apertado neste instante?

    Funcao e nao atributo porque Shift e estado, e nao evento: segurar
    Shift para andar correndo nao gera KEYDOWN novo a cada quadro, entao
    quem decide precisa LER o estado, e nao esperar evento.
    """
    return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)


# --- o mapa ---------------------------------------------------------------


class Mapa:
    """A grade do mundo: o que da para andar e o que nao.

    Um tile e um caractere. Texto, e nao matriz de booleanos, porque um
    mapa em arquivo e o que permite desenhar o cenario no editor em vez
    de escrever codigo.
    """

    PAREDE = "#"
    CHAO = "."
    SAIDA = "E"
    ITEM = "i"
    # um inimigo parado no mapa. Derrotado, ele vira chao e o tile some
    # — e por isso que a cena de combate tira o tile do mapa ANTES de
    # entrar na luta: se o jogador voltar e o tile ainda estivesse la,
    # ele entraria em combate de novo no mesmo instante.
    INIMIGO = "b"

    @staticmethod
    def _sem_recuo(linhas: list[str]) -> list[str]:
        """Tira o recuo comum a todas as linhas.

        Mapas em texto sao escritos com indentacao, porque e assim que
        ficam legiveis dentro do codigo:

            mapa = Mapa.de_texto(\"\"\"
                #####
                #...#
                #####\n\"\"\")

        Sem tirar o recuo, cada linha comeca com quatro `#` a mais: o
        mapa fica deslocado para a direita e — pior — a coluna 1, que era
        o chao mais a esquerda, vira parede. A sala ganha uma borda
        grossa de um tile em volta e o jogador nao anda.

        O recuo e o do MENOR entre as linhas, e nao o da primeira: um
        mapa cuja primeira linha e mais curta que as outras nao pode ter
        o recuo inteiro dela, senao a linha mais curta fica vazia.
        """
        if not linhas:
            return []

        menor = min(len(linha) - len(linha.lstrip()) for linha in linhas)
        return [linha[menor:].rstrip() for linha in linhas]

    def __init__(self, linhas: list[str]) -> None:
        self.linhas = self._sem_recuo([linha.rstrip() for linha in linhas])
        if not self.linhas:
            raise ValueError("o mapa nao pode estar vazio")

        # Mapa retangular, obrigatorio. Um mapa com linhas de tamanhos
        # diferentes faria `em()` estourar o indice em uma das ultimas
        # colunas, e o erro apareceria longe de onde o mapa foi escrito.
        largura = len(self.linhas[0])
        for numero, linha in enumerate(self.linhas, start=1):
            if len(linha) != largura:
                raise ValueError(
                    f"a linha {numero} tem {len(linha)} casas e a primeira "
                    f"tem {largura}: o mapa precisa ser retangular"
                )

        self.altura = len(self.linhas)
        self.largura = largura

    @classmethod
    def de_texto(cls, texto: str) -> "Mapa":
        """Cria o mapa de um texto com varias linhas.

            mapa = Mapa.de_texto(\"\"\"
                #####
                #...#
                #.E.#
                #####
            \"\"\")

        As linhas vazias das pontas sao descartadas. Um mapa escrito com
        quebra de linha depois da ultima linha de jogo traria uma linha
        vazia no fim, e o mapa ganharia uma faixa de chao que nao
        existe no desenho — visivel como uma linha de tiles a mais
        embaixo da sala.
        """
        linhas = [linha for linha in texto.splitlines() if linha.strip()]
        if not linhas:
            raise ValueError("o mapa nao tem nenhuma linha com conteudo")
        return cls(linhas)

    def em(self, coluna: int, linha: int) -> str:
        """O que tem na celula. Fora do mapa e parede.

        Devolver parede em vez de estourar o indice e o que impede o
        jogador de cair para fora do cenario: ele bate na borda e para,
        como se houvesse parede — que e o que existe na borda de qualquer
        sala.
        """
        if 0 <= linha < self.altura and 0 <= coluna < self.largura:
            return self.linhas[linha][coluna]
        return self.PAREDE

    def andavel(self, coluna: int, linha: int) -> bool:
        """Dá para andar nesta celula?

        `SAIDA` conta como andavel: e uma saida, nao um obstaculo. O
        jogador precisa atravessar a celula da porta para usa-la.
        """
        return self.em(coluna, linha) in (self.CHAO, self.SAIDA)

    def saidas(self) -> list[tuple[int, int]]:
        """Onde estao as saidas, em (coluna, linha)."""
        achadas: list[tuple[int, int]] = []
        for linha in range(self.altura):
            for coluna in range(self.largura):
                if self.em(coluna, linha) == self.SAIDA:
                    achadas.append((coluna, linha))
        return achadas

    def itens(self) -> list[tuple[int, int]]:
        """Onde estao os itens no chao, em (coluna, linha)."""
        return self._celulas_com(Mapa.ITEM)

    def inimigos(self) -> list[tuple[int, int]]:
        """Onde estao os inimigos, em (coluna, linha)."""
        return self._celulas_com(Mapa.INIMIGO)

    def _celulas_com(self, simbolo: str) -> list[tuple[int, int]]:
        """Toda celula com este simbolo. A busca e feita uma vez por mapa.

        O mapa e estatico, entao varrer as celulas a cada quadro seria
        trabalho repetido sem ganho. Quem chama guarda o resultado.
        """
        achadas: list[tuple[int, int]] = []
        for linha in range(self.altura):
            for coluna in range(self.largura):
                if self.em(coluna, linha) == simbolo:
                    achadas.append((coluna, linha))
        return achadas

    def para_pixels(self, coluna: int, linha: int) -> tuple[int, int]:
        """O centro da celula, em pixels."""
        return (coluna * settings.TAMANHO_DO_TILE,
                linha * settings.TAMANHO_DO_TILE)


# --- colisao --------------------------------------------------------------


def caixa_livre(
    caixa: pygame.Rect,
    mapa: Mapa,
    tamanho_do_tile: int = settings.TAMANHO_DO_TILE,
) -> bool:
    """A caixa cabe no mapa sem atravessar parede?

    Testa as QUATRO celulas que a caixa toca, e nao uma so. Uma caixa de
    12px esta em uma celula; uma de 48px esta em quatro. Testar so a
    celula do canto deixa passar parede na diagonal — e atravessar na
    diagonal e o defeito de colisao mais comum que existe, porque a caixa
    esta "dentro" de varias celulas e cada teste olha so uma.
    """
    esquerda = caixa.left // tamanho_do_tile
    direita = (caixa.right - 1) // tamanho_do_tile
    cima = caixa.top // tamanho_do_tile
    baixo = (caixa.bottom - 1) // tamanho_do_tile

    return all(
        mapa.andavel(coluna, linha)
        for coluna in range(esquerda, direita + 1)
        for linha in range(cima, baixo + 1)
    )


def mover(
    posicao: pygame.Vector2,
    velocidade: pygame.Vector2,
    delta: float,
    mapa: Mapa,
    caixa_dos_pes: pygame.Rect,
    tamanho_do_tile: int = settings.TAMANHO_DO_TILE,
) -> pygame.Vector2:
    """Move a posicao testando um eixo por vez.

    Aqui mora a diferenca entre um jogo que trava na parede e um que
    escorrega nela. O codigo classico e:

        posicao += velocidade * delta
        if bateu(parede): posicao = posicao_anterior

    Isso e "grudar na parede": apertando cima e direita ao mesmo tempo, o
    vetor vai para o canto, bate e o heroi PARA, mesmo com metade do
    caminho livre. Testando X e Y separados, o heroi sobe renteando a
    parede e desliza na horizontal — que e o que qualquer jogador espera
    de um personagem que nao esta deslizando por trilhos.
    """
    alvo = pygame.Vector2(posicao)

    if velocidade.x:
        alvo.x += velocidade.x * delta
        caixa = caixa_dos_pes.copy()
        caixa.centerx = int(alvo.x)
        if not caixa_livre(caixa, mapa, tamanho_do_tile):
            # Trava no limite da parede e nao um pouco antes. Travar antes
            # deixa um buraco de um pixel que o jogador ve como folga, e
            # o defeito reaparece quando a velocidade muda.
            alvo.x = posicao.x

    if velocidade.y:
        alvo.y += velocidade.y * delta
        caixa = caixa_dos_pes.copy()
        caixa.centery = int(alvo.y)
        if not caixa_livre(caixa, mapa, tamanho_do_tile):
            alvo.y = posicao.y

    return alvo


# --- o jogador ------------------------------------------------------------


class Jogador:
    """O protagonista: onde esta, para onde olha e o que carrega."""

    def __init__(
        self,
        coluna: int = 1,
        linha: int = 1,
        tamanho_do_tile: int = settings.TAMANHO_DO_TILE,
    ) -> None:
        # A posicao e o CENTRO DOS PES, nao o canto do sprite. Centro
        # porque e o centro que fica sobre o chao; com o canto, o heroi
        # anda meio tile acima do chao e a ilusao e de que ele flutua.
        self.posicao = pygame.Vector2(
            coluna * tamanho_do_tile + tamanho_do_tile // 2,
            linha * tamanho_do_tile + tamanho_do_tile // 2,
        )
        self.tamanho_do_tile = tamanho_do_tile
        self.direcao = "sul"

        # A caixa dos pes: pequena e na base do sprite.
        #
        # Estes numeros sao o ajuste fino do movimento, e valem ser
        # explicitados. Com a caixa do tamanho do sprite inteiro (32x32),
        # o heroi nao entra em corredor de um tile. Com uma caixa
        # minuscula (4x4), ele enfia metade do corpo na parede. Metade da
        # largura e uma faixa baixa no chao e o meio-termo que funciona
        # para sprite de 16x16 desenhado de pe.
        largura = max(4, int(tamanho_do_tile * 0.5))
        altura = max(3, int(tamanho_do_tile * 0.2))
        self.caixa = pygame.Rect(0, 0, largura, altura)

        # Comeca sem nada. Um heroi que comeca com uma espada contradiz a
        # historia de quem caiu no mundo sem nada — e o inventario vazio
        # e o que faz o primeiro bau ter importancia.
        self.inventario: list[str] = []
        self.vida = 100
        self.vida_maxima = 100

        # A velocidade do ULTIMO quadro, e nao a desejada agora. E o que
        # a animacao usa: se o jogador aperta e solta no mesmo quadro, o
        # heroi pode nao andar nada mas o passo ja comecou, e o boneco
        # "anda" no lugar.
        self.velocidade_atual = pygame.Vector2(0, 0)

    # --- estado --------------------------------------------------------

    @property
    def caixa_no_mundo(self) -> pygame.Rect:
        """A caixa dos pes, na posicao atual. E o que a colisao testa."""
        caixa = self.caixa.copy()
        caixa.centerx = int(self.posicao.x)
        caixa.bottom = int(self.posicao.y)
        return caixa

    @property
    def andando(self) -> bool:
        return self.velocidade_atual.length_squared() > 0

    def na_celula(self, mapa: Mapa) -> tuple[int, int]:
        """Em qual celula o heroi esta."""
        return (
            int(self.posicao.x) // self.tamanho_do_tile,
            int(self.posicao.y) // self.tamanho_do_tile,
        )

    # --- movimento -----------------------------------------------------

    def velocidade_desejada(
        self, teclas: pygame.key.ScancodeWrapper
    ) -> pygame.Vector2:
        """O vetor de velocidade, normalizado, conforme as teclas.

        A diagonal e normalizada SEMPRE. Sem isso, andar para cima e para
        a direita daria 1,41x a velocidade e o heroi passaria a ser mais
        rapido na diagonal — um dos defeitos mais dificeis de ver,
        porque so aparece em diagonal e passa por "o jogo anda rapido".
        """
        direcao = pygame.Vector2(0, 0)
        for nome in ORDEM_DIRECOES:
            if any(teclas[tecla] for tecla in TECLAS_DIRECAO[nome]):
                direcao = DIRECOES[nome]
                break

        if direcao.length_squared() == 0:
            return pygame.Vector2(0, 0)

        return direcao.normalize() * VELOCIDADE_ANDANDO * (
            FATOR_CORRIDA if correndo_agora() else 1.0
        )

    def atualizar(
        self,
        delta: float,
        mapa: Mapa,
        teclas: pygame.key.ScancodeWrapper,
    ) -> None:
        """Avanca um quadro."""
        velocidade = self.velocidade_desejada(teclas)
        self.velocidade_atual = velocidade

        if velocidade.length_squared() == 0:
            return

        self.posicao = mover(
            self.posicao, velocidade, delta, mapa,
            self.caixa_no_mundo, self.tamanho_do_tile,
        )

        # A direcao do desenho e a do movimento, resolvida pelo eixo
        # DOMINANTE. Guardar o nome da tecla em vez disso faria o boneco
        # virar para o lado errado no meio da diagonal, porque o eixo
        # maior e o que o jogador ve como direcao principal.
        if abs(velocidade.y) >= abs(velocidade.x):
            self.direcao = "sul" if velocidade.y > 0 else "norte"
        else:
            self.direcao = "leste" if velocidade.x > 0 else "oeste"

    # --- desenho -------------------------------------------------------

    def desenhar(self, tela: pygame.Surface) -> None:
        """Desenha o heroi, com a sombra antes do corpo.

        A imagem vem por nome a cada quadro, e nao guardada em atributo.
        Guardar seria mais rapido, mas o sprite so pode ser recarregado
        depois que a escala muda, e um atributo guardado antes disso fica
        com o tamanho velho para sempre.
        """
        prefixo = "anda" if self.andando else "idl"
        sprite = arte.carregar_sprite(
            f"heroi/{prefixo}_{self.direcao}.png",
            escala=settings.ESCALA_SPRITE,
        )
        if sprite is None:
            return

        # `midbottom` e nao `center`: centralizar o sprite faz o heroi
        # parecer flutuar acima do chao.
        destino = sprite.get_rect(
            midbottom=(int(self.posicao.x), int(self.posicao.y))
        )

        # A sombra ANTES do sprite. Somada depois, ela escurece os pes do
        # heroi e faz o chao parecer sujo.
        largura = max(6, int(self.tamanho_do_tile * 0.6))
        altura = max(3, int(self.tamanho_do_tile * 0.22))
        sombra = pygame.Surface((largura, altura), pygame.SRCALPHA)
        pygame.draw.ellipse(
            sombra, (0, 0, 0, 80),
            pygame.Rect(0, 0, largura, altura),
        )
        tela.blit(
            sombra,
            (destino.centerx - largura // 2, destino.bottom - altura // 2),
        )
        tela.blit(sprite, destino)

    # --- inventario -----------------------------------------------------

    def pegar(self, item: str) -> bool:
        """Guarda um item. False se o inventario esta cheio.

        O limite existe porque o inventario e o que o jogador ve: sem
        teto, "pegar tudo" deixa de ser uma decisao.
        """
        if len(self.inventario) >= settings.MAXIMO_DE_ITENS:
            return False
        self.inventario.append(item)
        return True

    def largar(self, item: str) -> bool:
        if item not in self.inventario:
            return False
        self.inventario.remove(item)
        return True

    def __str__(self) -> str:
        return (
            f"{self.direcao} em "
            f"({int(self.posicao.x)}, {int(self.posicao.y)})"
        )