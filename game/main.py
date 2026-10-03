"""Ponto de entrada do jogo: janela, relogio e loop principal.

Este arquivo tem uma responsabilidade so: manter a janela aberta e
delegar o que deve ser desenhado. Ele nao desenha o jogador, nao sabe
o que e uma sala e nao le arquivo de save.

A separacao existe por um motivo pratico: o `loop` roda uma vez por
quadro, entao qualquer coisa que ele fizer mal feito custa 60 vezes por
segundo. Um `print` de depuracao dentro do loop transforma o terminal
numa lavanderia e derruba o framerate; uma carga de imagem dentro do
loop abre o arquivo 60 vezes por segundo. O loop fica burro de proposito.

O fluxo de uma volta:

    1. dt  = menor tempo desde a ultima volta (em segundos)
    2. dt  = menor(dt, LIMITE_DE_QUADRO)   <- a protecao contra o "chuque"
    3. tratar os eventos da fila
    4. atualizar a cena (mover o jogador, correr a animacao)
    5. desenhar a cena
    6. mostrar o quadro na tela

A ordem dos passos 4 e 5 e invertida em relacao ao desenho: atualizar
antes de desenhar garante que o quadro na tela ja corresponde ao estado
novo, e nao ao anterior. Errar essa ordem produz um quadro de atraso, que
em movimento rapido aparece como o personagem "escorregando".
"""
from __future__ import annotations

import pygame

import settings


# --- estados ---------------------------------------------------------------


class Estado:
    """Os estados do jogo, como constantes.

    Um `enum.Enum` seria mais elegante, e aqui seria errado: os estados
    sao comparados e impressos o tempo todo (`if self.estado ==
    MENU`), e uma string ja faz isso sem exigir importacao extra. Se um
    dia um estado precisar de dado proprio, ai sim vira classe.
    """

    MENU = "menu"
    EXPLORACAO = "exploracao"
    COMBATE = "combate"
    PAUSE = "pause"
    FIM_DE_JOGO = "fim_de_jogo"


# --- o jogo ---------------------------------------------------------------


class Jogo:
    """A janela e o loop. Nada mais."""

    def __init__(self) -> None:
        pygame.init()

        self.tela = pygame.display.set_mode(
            (settings.LARGURA, settings.ALTURA)
        )
        pygame.display.set_caption(settings.TITULO)

        # O icone e opcional de verdade: se o arquivo nao existir, o
        # pygame aceita `None` e usa o icone padrao. Um `try/except`
        # aqui custa tres linhas e evita que um asset faltando derrube o
        # jogo na hora de abrir.
        if settings.ICONE.is_file():
            pygame.display.set_icon(pygame.image.load(str(settings.ICONE)))

        # O relogio e o que segura o framerate. `tick` dorme o que for
        # preciso para a volta levar 1/60s, e devolve quanto tempo
        # realmente passou.
        self.relogio = pygame.time.Clock()

        self.estado = Estado.MENU
        self.rodando = True

    # --- eventos -----------------------------------------------------

    def tratar_eventos(self) -> None:
        """Esvazia a fila de eventos.

        `get()` devolve um evento por vez e esvazia a fila. O `while`
        existe porque fechar a janela e apertar ESC sao dois eventos
        diferentes, e processar so o primeiro perderia o segundo.
        """
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                # Quit e o "fechar a janela do SO". E o unico evento que
                # desliga o jogo sem confirmacao: se o jogador fechou a
                # janela, a intencao dele ja foi clara.
                self.rodando = False

            elif evento.type == pygame.KEYDOWN:
                self.tratar_tecla(evento)

    def tratar_tecla(self, evento: pygame.event.Event) -> None:
        """Reage a uma tecla. Separado para a logica de estado nao
        ficar misturada com a leitura da fila de eventos."""
        if evento.key == pygame.K_ESCAPE:
            # ESC volta um estado. Sair direto do jogo e o oposto de um
            # jogo de aventura: perder o progresso por um dedo na tecla
            # errada e a forma mais rapida de um jogador desistir.
            if self.estado == Estado.EXPLORACAO:
                self.estado = Estado.PAUSE
            elif self.estado == Estado.PAUSE:
                self.estado = Estado.EXPLORACAO
            elif self.estado in (Estado.COMBATE, Estado.FIM_DE_JOGO):
                # em combate e em fim de jogo nao ha para onde voltar
                self.estado = Estado.MENU
            else:
                self.estado = Estado.MENU

    # --- atualizacao e desenho ---------------------------------------

    def atualizar(self, dt: float) -> None:
        """Avanca o estado atual em `dt` segundos.

        Ainda vazio: cada estado ganha o seu `atualizar` quando existir.
        """
        if self.estado == Estado.EXPLORACAO:
            # futuro: mover o jogador com pygame.Vector2, resolver a
            # colisao com pygame.Rect
            pass

    def desenhar(self) -> None:
        """Desenha o estado atual na tela.

        Por enquanto a tela e preta. O preenchimento acontece aqui e
        nao uma vez na inicializacao: cada estado desenha o seu quadro
        inteiro, e um estado novo que desenhe por cima de um fundo velho
        deixa rastro quando some.
        """
        self.tela.fill(settings.PRETO)
        pygame.display.flip()

    # --- loop --------------------------------------------------------

    def rodar(self) -> None:
        """O loop principal.

        O `dt` e limitado ANTES de ser entregue a cena. Sem isso, uma
        janela arrastada por 2 segundos entrega um `dt` de 2.0 e o
        jogador atravessa a parede oposta da sala num unico passo — o
        classico bug de "atravessou o mapa inteiro". Limitando o dt, o
        mundo andar mais devagar durante um engasgo, que e o correto.
        """
        while self.rodando:
            dt = self.relogio.tick(settings.FPS) / 1000.0
            dt = min(dt, settings.LIMITE_DE_QUADRO)

            self.tratar_eventos()
            if not self.rodando:
                break

            self.atualizar(dt)
            self.desenhar()

        pygame.quit()


def main() -> None:
    """Chamada padrao: cria o jogo e entra no loop."""
    Jogo().rodar()


if __name__ == "__main__":
    main()