"""Ponto de entrada do jogo: janela, relogio, maquina de estados e loop.

Este arquivo tem uma responsabilidade so: manter a janela aberta e
delegar. Ele nao desenha o jogador, nao sabe o que e uma sala, nao le
save. Quem sabe sao `player`, `cenario` e os estados.

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

Sobre a maquina de estados
-------------------------
Cada estado e uma classe com `atualizar` e `desenhar`. A vantagem sobre
um `if/elif` gigante no loop e que o jogo nao precisa saber a ordem
das telas: o estado so precisa saber o proximo estado, e a transicao
acontece no `atualizar` dele. Um estado novo nao exige mexer no loop.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pygame

import api_client
import cenario
import combat_scene
import settings
from player import Jogador, Mapa


# --- a maquina de estados --------------------------------------------------


class Estado(ABC):
    """Uma tela do jogo.

    `atualizar` e `desenhar` sao obrigatorios porque o loop sempre chama
    os dois. O resto do jogo nunca precisa perguntar "em que estado estou"
    para decidir o que desenhar — quem sabe e o proprio estado.
    """

    def __init__(self, jogo: "Jogo") -> None:
        self.jogo = jogo

    def atualizar_eventos(self) -> None:
        """Processa os eventos que este estado quer ver.

        O loop chama isto ANTES de `atualizar`, e e o que garante que
        uma tecla que muda de estado seja vista no mesmo quadro em que
        chegou. O `pygame.event.get()` esvazia a fila, entao o jogo
        pega o que e dele e o estado pega o que sobrou — nunca os dois
        leem a mesma fila, ou um comeria os eventos do outro.
        """

    def tratar_tecla(self, tecla: int) -> None:
        """Uma tecla de jogo, quando este estado e o combate.

        O combate tem um menu proprio, e e o unico estado que consome
        teclas por conta propria. Ele sobrescreve este metodo; os
        outros estados usam `atualizar_eventos`.
        """

    @abstractmethod
    def atualizar(self, delta: float) -> None:
        """Avanca um quadro deste estado."""

    @abstractmethod
    def desenhar(self, tela: pygame.Surface) -> None:
        """Desenha este estado inteiro na tela."""

    # atalhos para o jogo, para as subclasses nao carregarem `self.jogo`
    # em cada linha
    @property
    def jogador(self) -> Jogador:
        return self.jogo.jogador

    @property
    def mapa(self) -> Mapa:
        return self.jogo.mapa


class Menu(Estado):
    """A tela inicial: aperte uma tecla para comecar."""

    def atualizar(self, delta: float) -> None:
        self.jogo.tempo_no_menu += delta

    def atualizar_eventos(self) -> None:
        """Qualquer tecla comeca o jogo.

        Voltar ao menu a partir de uma tela de jogo e uma mudanca de
        estado, e nao um reinicio: o jogador continua com a vida e o
        inventario que tinha.
        """
        for evento in pygame.event.get():
            if evento.type == pygame.KEYDOWN:
                self.jogo.ir_para(Exploracao)
                return

    def desenhar(self, tela: pygame.Surface) -> None:
        tela.fill(settings.PRETO)

        # O titulo e a unica coisa que o jogador ve com certeza, entao
        # ele e o maior texto da tela. O "aperte para comecar" pisca:
        # piscar e o jeito mais barato de dizer "estou esperando algo"
        # sem ocupar espaco.
        _texto_centro(
            tela, settings.TITULO, int(tela.get_height() * 0.36),
            settings.OURO,
        )
        if int(self.jogo.tempo_no_menu * 2) % 2 == 0:
            _texto_centro(
                tela, "aperte uma tecla para comecar",
                int(tela.get_height() * 0.52), settings.CINZA,
            )
        _texto_centro(
            tela, "WASD ou setas para andar   shift para correr",
            int(tela.get_height() * 0.80), settings.CINZA,
        )


class Exploracao(Estado):
    """O mundo aberto: andar, pegar item, entrar em combate, sair."""

    def __init__(self, jogo: "Jogo") -> None:
        super().__init__(jogo)
        # O combate ainda esta sendo montado. Um inimigo encontrado
        # entra na luta; um bau de arma abre a tela de escolha. Sao as
        # duas coisas que levam do mundo para a briga.
        self.luta_pendente: str | None = None

    def atualizar(self, delta: float) -> None:
        # A ordem importa: PRIMEIRO os eventos (inclusive o "qualquer
        # tecla comeca", do menu). Sem isto, o jogo comeca no menu, o
        # menu le o evento e troca de estado, e o `atualizar` desta
        # exploracao roda com um quadro de atraso — e um teste que so
        # poste um evento e chama `atualizar` uma vez pegava o estado
        # antigo, como se o menu nao respondesse.
        super().atualizar_eventos()

        self.jogador.atualizar(delta, self.mapa, pygame.key.get_pressed())
        self.jogo.camera_seguir_o_jogador()

        # Pegar item: o jogador tem que ESTAR sobre o item. A celula do
        # jogador e comparada com a celula do item, e nao a distancia em
        # pixels — comparar pixels exigiria um raio arbitrario, e um raio
        # grande demais deixa o jogador pegar de longe, o que le como
        # bug.
        coluna, linha = self.jogador.na_celula(self.mapa)
        celula = self.mapa.em(coluna, linha)

        if celula == Mapa.ITEM:
            self.mapa.linhas[linha] = (
                self.mapa.linhas[linha][:coluna]
                + Mapa.CHAO
                + self.mapa.linhas[linha][coluna + 1:]
            )
            self.jogador.pegar("item")
            self.jogo.avisar("pegou um item")
            return

        # Bater num inimigo abre o combate. O tile `b` do mapa e um
        # inimigo parado: e o mesmo cuidado que o item, e pelo mesmo
        # motivo — o jogador tem que chegar em cima dele.
        if celula == Mapa.INIMIGO:
            # o tile vira chao ANTES de trocar de estado. Se a luta
            # devolvesse o jogador ao mesmo tile, ele entraria em
            # combate de novo no mesmo quadro, e a briga recomeçaria
            # sozinha.
            self.mapa.linhas[linha] = (
                self.mapa.linhas[linha][:coluna]
                + Mapa.CHAO
                + self.mapa.linhas[linha][coluna + 1:]
            )
            self.jogo.ir_para(Combate)
            return

        # Chegar na saida: e a unica forma de trocar de estado nesta
        # versao. Um portal de verdade viria com uma cena propria; aqui a
        # saida devolve ao menu, o que ja prova a transicao.
        if self.mapa.em(coluna, linha) == Mapa.SAIDA:
            self.jogo.ir_para(FimDeJogo, vitoria=False, motivo="achou a saida")

    def desenhar(self, tela: pygame.Surface) -> None:
        cenario.desenhar(tela, self.mapa, self.jogo.camera)
        self.jogador.desenhar(tela)

        # O rodape fica por cima do mundo, nunca atras: e onde o jogador
        # olha para conferir vida e inventario.
        _texto(
            tela, f"vida {self.jogador.vida}/{self.jogador.vida_maxima}",
            (10, settings.ALTURA - 24), settings.BRANCO,
        )
        _texto(
            tela, f"itens {len(self.jogador.inventario)}"
                  f"/{settings.MAXIMO_DE_ITENS}",
            (10, settings.ALTURA - 44), settings.CINZA,
        )
        if self.jogo.aviso:
            _texto_centro(
                tela, self.jogo.aviso,
                int(settings.ALTURA * 0.12), settings.OURO,
            )


class Combate(Estado):
    """A tela de briga.

    Ela nao e um estado com metodos proprios: ela e uma cena que sabe se
    desenhar e se atualizar, e este estado so repassa. A razao e que a
    cena de combate tem uma maquina propria (a fila de eventos com pausa)
    que nao cabe no `atualizar(delta)` de um estado comum — e esconder
    essa maquina dentro do estado tornaria o resto do jogo mais dificil
    de ler, porque o estado de combate teria quatro metodos e os outros
    teriam tres.
    """

    def __init__(self, jogo: "Jogo") -> None:
        super().__init__(jogo)
        self.cena = combat_scene.Combate(jogo)
        self.jogo.luta = self.cena.luta

    def atualizar(self, delta: float) -> None:
        self.cena.atualizar(delta)

    def desenhar(self, tela: pygame.Surface) -> None:
        self.cena.desenhar(tela)

    def tratar_tecla(self, tecla: int) -> None:
        self.cena.tratar_tecla(tecla)


class Pausa(Estado):
    """O menu de pausa. E daqui que se salva."""

    def atualizar(self, delta: float) -> None:
        pass

    def atualizar_eventos(self) -> None:
        """ESC volta, S salva."""
        for evento in pygame.event.get():
            if evento.type != pygame.KEYDOWN:
                continue
            if evento.key == pygame.K_ESCAPE:
                self.jogo.ir_para(Exploracao)
            elif evento.key == pygame.K_s:
                self.jogo.salvar()
                self.jogo.avisar("partida salva")

    def desenhar(self, tela: pygame.Surface) -> None:
        tela.fill(settings.PRETO)
        _texto_centro(tela, "PAUSA", int(settings.ALTURA * 0.35), settings.OURO)
        _texto_centro(
            tela, "esc para voltar   s para salvar",
            int(settings.ALTURA * 0.50), settings.CINZA,
        )


class FimDeJogo(Estado):
    """Fim de partida: grava no ranking e mostra a posicao."""

    def __init__(self, jogo: "Jogo", vitoria: bool, motivo: str = "") -> None:
        super().__init__(jogo)
        self.vitoria = vitoria
        self.motivo = motivo
        self.resultado: api_client.Resultado | None = None
        self.ja_registrou = False

    def atualizar(self, delta: float) -> None:
        pass

    def atualizar_eventos(self) -> None:
        """Qualquer tecla volta ao menu."""
        for evento in pygame.event.get():
            if evento.type == pygame.KEYDOWN:
                self.jogo.ir_para(Menu)
                return

    def desenhar(self, tela: pygame.Surface) -> None:
        tela.fill(settings.PRETO)
        _texto_centro(
            tela, "VITORIA" if self.vitoria else "FIM DE JOGO",
            int(settings.ALTURA * 0.28),
            settings.OURO if self.vitoria else settings.VERMELHO,
        )
        if self.motivo:
            _texto_centro(
                tela, self.motivo, int(settings.ALTURA * 0.40), settings.BRANCO
            )
        _texto_centro(
            tela, f"itens coletados: {len(self.jogador.inventario)}",
            int(settings.ALTURA * 0.50), settings.CINZA,
        )

        # O resultado do envio so aparece DEPOIS que ele volta. Sem isso,
        # a tela mostraria "salvando..." e o jogador fecharia o jogo sem
        # saber se gravou.
        if self.resultado is None:
            texto = "enviando para o ranking..."
            cor = settings.CINZA
        elif self.resultado.ok:
            texto = "pontuacao registrada no ranking"
            cor = settings.VERDE
        else:
            texto = f"nao gravou no ranking: {self.resultado.erro}"
            cor = settings.VERMELHO

        _texto_centro(tela, texto, int(settings.ALTURA * 0.62), cor)
        _texto_centro(
            tela, "aperte uma tecla para voltar ao menu",
            int(settings.ALTURA * 0.78), settings.CINZA,
        )


# --- o jogo ----------------------------------------------------------------


MAPA_INICIAL = """
    ##########################
    #........................#
    #..................b.....#
    #.....i..................#
    #........................#
    #.......########.........#
    #.......#......#.........#
    #.......#......#.........#
    #.......#......#.........#
    #.......#......#.........#
    #....................E...#
    ##########################
"""


class Jogo:
    """A janela, o estado atual e o loop."""

    def __init__(self) -> None:
        pygame.init()

        self.tela = pygame.display.set_mode(
            (settings.LARGURA, settings.ALTURA)
        )
        pygame.display.set_caption(settings.TITULO)

        # O icone e opcional de verdade: se o arquivo nao existir, o
        # pygame aceita `None` e usa o icone padrao. Um `try/except`
        # custa tres linhas e evita que um asset faltando derrube o jogo
        # na hora de abrir.
        if settings.ICONE.is_file():
            pygame.display.set_icon(pygame.image.load(str(settings.ICONE)))

        self.relogio = pygame.time.Clock()
        self.rodando = True

        # --- o mundo ---
        self.mapa = Mapa.de_texto(MAPA_INICIAL)
        self.jogador = Jogador(1, 1)
        self.camera = pygame.Vector2(0, 0)
        self.camera_seguir_o_jogador()

        # --- a transicao de estado ---
        self.estado: Estado = Menu(self)

        # --- o cliente da API ---
        # `None` ate a primeira partida terminar. Criar a sessao HTTP
        # aqui abriria uma conexao mesmo se o jogador nunca chegasse ao
        # fim de jogo, e o recurso ficaria preso sem uso.
        self.cliente: api_client.Cliente | None = None

        # --- avisos e tempo ---
        self.aviso = ""
        self.tempo_do_aviso = 0.0
        self.tempo_no_menu = 0.0

        # O tempo de mundo, em segundos desde o inicio. Vale para o tempo
        # da partida que vai para o ranking, e nao e um relogio a mais:
        # e o mesmo tempo que ja conta para o cenario animar.
        self.relogio_wang = 0.0

        # Quantos inimigos a partida derrubou. Comeca em zero porque o
        # jogo ainda nao tem combate — o campo existe no modelo e na API
        # desde o inicio para que o formato do dado nao mude quando o
        # combate chegar.
        self.inimigos_derrotados = 0

    # --- transicao de estado ------------------------------------------

    def ir_para(self, novo: type[Estado], **argumentos) -> None:
        """Troca de estado.

        Aceita a CLASSE do estado, e a instancia e criada aqui — com o
        jogo certo e com os argumentos que o estado novo precisa.

        Chamar com a classe e mais seguro do que chamar com uma instancia
        pronta: `Exploracao()` sem o `jogo` quebra na hora, e o erro
        aparece longe de quem escreveu. Aceitar so a classe elimina essa
        possibilidade.

        O estado que SAI nao e avisado de nada, e o que entra nao recebe
        nenhum argumento especial alem dos que o chamador passou. Um
        estado que precisa de limpeza faz isso no proprio `atualizar`.
        """
        self.estado = novo(self, **argumentos)

    # --- camera --------------------------------------------------------

    def camera_seguir_o_jogador(self) -> None:
        """Centraliza o heroi, sem deixar a camera mostrar fora do mapa.

        O clamp e o que impede a tela de mostrar o vazio alem da borda do
        mapa. O `max` com `meio_tela` e o que impede a camera de centralizar
        a borda do mapa quando o mapa e menor que a tela — sem isso, um
        mapa pequeno aparecia no meio da janela com uma faixa preta dos
        dois lados.
        """
        lado = settings.TAMANHO_DO_TILE
        largura_mapa = self.mapa.largura * lado
        altura_mapa = self.mapa.altura * lado
        largura_tela, altura_tela = settings.LARGURA, settings.ALTURA

        alvo_x = int(self.jogador.posicao.x - largura_tela // 2)
        alvo_y = int(self.jogador.posicao.y - altura_tela // 2)

        self.camera.x = min(max(alvo_x, 0), max(0, largura_mapa - largura_tela))
        self.camera.y = min(max(alvo_y, 0), max(0, altura_mapa - altura_tela))

    # --- avisos -------------------------------------------------------

    def avisar(self, texto: str, duracao: float = 2.0) -> None:
        self.aviso = texto
        self.tempo_do_aviso = duracao

    # --- save e ranking -----------------------------------------------

    def salvar(self) -> None:
        """Guarda o progresso no arquivo de save.

        O save e um arquivo local, separado do backend. Sao coisas
        diferentes: o save e "onde eu parei", e o ranking e "como eu
        me saí". Um nao substitui o outro, e um backend fora do ar nao
        pode custar o progresso do jogador.
        """
        import json
        from pathlib import Path

        pasta = Path(__file__).parent / "saves"
        pasta.mkdir(exist_ok=True)
        arquivo = pasta / "slot1.json"
        arquivo.write_text(
            json.dumps(
                {
                    "coluna": self.jogador.posicao.x,
                    "linha": self.jogador.posicao.y,
                    "vida": self.jogador.vida,
                    "inventario": self.jogador.inventario,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _pontuar(self) -> int:
        """A pontuacao da partida.

        A formula e o tipo de coisa que nao deve ser mudada depois que o
        ranking tem linhas: mudar o peso de um termo faz o placar de
        ontem perder sentido. Mantida simples e explicita por isso.
        """
        return (
            len(self.jogador.inventario) * 100
            + self.jogador.vida * 2
            + self.inimigos_derrotados * 250
        )

    def registrar_vitoria(
        self, venceu: bool, fugiu: bool
    ) -> api_client.Resultado:
        """Manda a partida para o backend quando a luta acaba.

        Quem registra e o FIM DE COMBATE, e nao o fim de jogo: uma briga
        e um evento da partida, e o placar precisa contar inimigos
        derrubados. Uma fuga nao pontua — fugir e o que o jogador faz
        quando a luta esta feia, e dar pontos por isso incentiva a
        desistir.
        """
        if not venceu:
            if self.cliente is None:
                self.cliente = api_client.Cliente()
            return self.cliente.registrar_partida(
                nome="John",
                tempo=int(self.relogio_wang),
                inimigos_derrotados=self.inimigos_derrotados,
                pontuacao=self._pontuar(),
            )

        self.inimigos_derrotados += self.luta_derrotados()
        self.jogador.vida = min(
            self.jogador.vida_maxima,
            self.jogador.vida + 25,  # a vitoria cura um pouco
        )
        if self.cliente is None:
            self.cliente = api_client.Cliente()
        return self.cliente.registrar_partida(
            nome="John",
            tempo=int(self.relogio_wang),
            inimigos_derrotados=self.inimigos_derrotados,
            pontuacao=self._pontuar(),
        )

    def luta_derrotados(self) -> int:
        """Quantos inimigos cairam na ultima luta."""
        return getattr(self, "_derrotados_na_luta", 1)

    def registrar_no_ranking(self) -> api_client.Resultado:
        """Manda a partida para o backend. Devolve o que aconteceu."""
        if self.cliente is None:
            self.cliente = api_client.Cliente()

        return self.cliente.registrar_partida(
            nome="John",
            # `relogio_wang` e o tempo de mundo em segundos desde o
            # inicio. E o tempo da partida sem nenhum relogio a mais:
            # criar um `pygame.time.Clock` so para contar tempo seria
            # um objeto para isso, e ele seria o unico lugar do jogo que
            # nao guarda nada.
            tempo=int(self.relogio_wang),
            inimigos_derrotados=self.inimigos_derrotados,
            pontuacao=self._pontuar(),
        )

    # --- eventos ------------------------------------------------------

    def tratar_eventos(self) -> None:
        """Só o que o JOGO trata, e nao o que os estados tratam.

        O jogo cuida de dois eventos so: fechar a janela, e o ESC que
        ABANDONA o jogo (sai de um combate ou do fim de jogo). Tudo o
        mais e do estado.

        A separacao existe porque `event.get()` esvazia a fila. Se o
        jogo e o estado lessem a fila, um leria os eventos do outro. Por
        isso o jogo pega o que e dele com `event.get()` e o estado
        processa o que sobrou com `atualizar_eventos`.
        """
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                # Quit e o "fechar a janela do SO", e o unico evento que
                # desliga o jogo sem confirmacao: se o jogador fechou a
                # janela, a intencao dele ja foi clara.
                self.rodando = False

        # A tecla segue para o estado atual. O combate tem um menu
        # proprio, e sem este desvio o W e o S do menu seriam lidos como
        # "andar para cima" e "andar para baixo" — o jogador veria o
        # boneco sair andando no meio da luta.
        if evento.type == pygame.KEYDOWN:
            self.estado.tratar_tecla(evento.key)

    # --- atualizacao e desenho ---------------------------------------

    def atualizar(self, delta: float) -> None:
        # o contador do mundo, que o cenario usa para animar a agua e a
        # tocha. Vive no jogo e nao no estado: o tempo do mundo continua
        # correndo mesmo com o jogo pausado em um menu.
        self.relogio_wang += delta

        if self.tempo_do_aviso > 0:
            self.tempo_do_aviso -= delta
            if self.tempo_do_aviso <= 0:
                self.aviso = ""

        # Os eventos do ESTADO vem antes do `atualizar`. E o que garante
        # que uma tecla que muda de estado seja vista no mesmo quadro em
        # que chegou: se o `atualizar` rodasse primeiro, o estado novo
        # so entraria no quadro seguinte, e um teste que poste um evento
        # e chame `atualizar` uma vez veria o estado antigo — como se o
        # menu nao respondesse.
        self.estado.atualizar_eventos()

        # Um estado que precisa de um passo por quadro faz o registro do
        # ranking no seu PRIMEIRO quadro, e nao aqui: o registro pertence
        # a tela de fim de jogo, e a tela e que sabe quando ja pode
        # mostrar o resultado.
        if isinstance(self.estado, FimDeJogo) and not self.estado.ja_registrou:
            self.estado.ja_registrou = True
            self.estado.resultado = self.registrar_no_ranking()

        self.estado.atualizar(delta)

    def desenhar(self) -> None:
        self.estado.desenhar(self.tela)
        pygame.display.flip()

    # --- loop ---------------------------------------------------------

    def rodar(self) -> None:
        """O loop principal.

        O `dt` e limitado ANTES de ser entregue a cena. Sem isso, uma
        janela arrastada por 2 segundos entrega um `dt` de 2.0 e o
        jogador atravessa a parede oposta da sala num unico passo — o
        classico bug de "atravessou o mapa inteiro". Limitando o dt, o
        mundo anda mais devagar durante um engasgo, que e o correto.
        """
        while self.rodando:
            dt = self.relogio.tick(settings.FPS) / 1000.0
            dt = min(dt, settings.LIMITE_DE_QUADRO)

            self.tratar_eventos()
            if not self.rodando:
                break

            self.atualizar(dt)
            self.desenhar()

        if self.cliente is not None:
            self.cliente.fechar()
        pygame.quit()


# --- texto -----------------------------------------------------------------


def _texto(
    tela: pygame.Surface,
    conteudo: str,
    posicao: tuple[int, int],
    cor: tuple[int, int, int],
    tamanho: int = 18,
) -> None:
    """Escreve um texto na posicao dada.

    A fonte e criada a cada chamada, o que e desperdicio. Ela e pequena o
    bastante para passar: o jogo desenha no maximo meia duzia de textos por
    quadro, e criar uma fonte custa menos que um blit.
    """
    fonte = pygame.font.Font(None, tamanho)
    tela.blit(fonte.render(conteudo, True, cor), posicao)


def _texto_centro(
    tela: pygame.Surface,
    conteudo: str,
    y: int,
    cor: tuple[int, int, int],
    tamanho: int = 18,
) -> None:
    """Escreve um texto centralizado horizontalmente, na altura `y`."""
    fonte = pygame.font.Font(None, tamanho)
    desenho = fonte.render(conteudo, True, cor)
    tela.blit(desenho, ((tela.get_width() - desenho.get_width()) // 2, y))


def main() -> None:
    """Chamada padrao: cria o jogo e entra no loop."""
    Jogo().rodar()


if __name__ == "__main__":
    main()
