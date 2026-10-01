"""Cena de combate por turnos.

A luta e por turnos: ha uma fila, o mais rapido age primeiro, cada um age
uma vez, e o jogo PARA enquanto o jogador escolhe. Nao ha cronometro e
nao ha medidor de tempo na tela: a unica pergunta e "de quem e a vez", e
ela esta escrita na tela em vez de ser deduzida de uma barra que corre.

Antes era ATB, no estilo Chrono Trigger, com uma barra por lutador
enquanto com o tempo. A foto do jogador mostrava as barras como riscos
dourados soltos no chao, com a etiqueta "TEMPO", e nada dizendo de quem
era a vez. O que a tela mostra agora e a VEZ, no alto, e a fila logo
abaixo: quem age agora, e quem vem depois.

A cena cuida do desenho (barras de vida, poses, numeros de dano) e do
menu; as regras estao em `src/combat.py`.
"""
from __future__ import annotations

import math

import pygame

from . import arena as arena_mod
from . import assets, cenarios, combat, equipamento as equip_mod, itens, theme, ui_arte
from .scene import Scene

DT_FIXO = 1 / 60

# quanto tempo o numero de dano sobe na tela
DANO_VIDA = 1.0

# posicoes na tela (fracao), para o layout acompanhar a resolucao
# o heroi: eixo horizontal em fracao da largura. O vertical vem da
# linha do chao, e o ancoramento e pelo pe.
HEROI_POS = 0.28
# A linha do chao da luta nao mora aqui. Ela e `arena.HORIZONTE`, e as
# duas needles usarem numeros diferentes era o que fazia o boneco
# boiar sobre a parede: o fundo cortava em 0.58 e o lutador era
# ancorado em 0.62, e o pe dele caia 29px dentro do chao.
#
# Estas fracoes sao a POSICAO no chao, acima da linha. O primeiro
# plano (o heroi) e o mais baixo e o maior; os inimigos ficam para tras,
# cada um um pouco mais alto e menor. E assim que se le um grupo de
# tres dimensoes numa tela de duas.
INIMIGO_X = (0.58, 0.72, 0.86)
# quanto cada inimigo sobe em relacao ao chao, e o quanto encolhe
INIMIGO_ATRAS = ((0.010, 0.92), (0.026, 0.84), (0.042, 0.76))
# quanto o heroi desce em relacao ao chao: ele e o mais perto
HEROI_A_FRENTE = 0.075
# a pausa entre um inimigo bater e o proximo bater. O golpe precisa ser
# visto: sem a pausa, os tres inimigos da sala batem em tres quadros
# seguidos e o log pisca sem ninguem ler.
PAUSA_ENTRE_INIMIGOS = 0.45


class CombatScene(Scene):
    """Batalha contra um grupo de esqueletos."""

    def __init__(self, manager, inimigos: int | None = None) -> None:
        super().__init__(manager)
        if inimigos is None:
            inimigos = manager.ui_state.get("inimigos", 1)
        # a masmorra diz se esta luta e contra o CHEFE da ultima sala.
        # O chefe nao e um esqueleto mais forte: ele tem barra rapida
        # e defesa alta, e muda o que o menu precisa oferecer.
        self.e_chefe = bool(manager.ui_state.get("e_chefe", False))
        # a primeira sala marca a luta como fraca: e onde se ensina o
        # golpe. Sem ler este sinal, `fracos` no progresso nao fazia
        # nada e o primeiro esqueleto era forte como os outros.
        fracos = bool(manager.ui_state.get("fracos", False))
        lista = (
            [combat.novo_chefe()]
            if self.e_chefe
            else [combat.novo_esqueleto(i, fraco=fracos)
                  for i in range(inimigos)]
        )
        self.batalha = combat.Batalha(
            heroi=combat.novo_heroi(),
            inimigos=lista,
        )
        self.index = 0
        self.menu_aberto = False
        # "acao" para as acoes, "item" para o inventario aberto
        self.modo = "acao"
        self.index_item = 0
        # a aula da sala da pocao: enquanto o jogador nao usou um item
        # nesta luta, o jogo aponta a opcao no menu
        self.ensinar_item = bool(manager.ui_state.get("ensinar_item", False))
        self.ja_usou_item = False
        self.anim_tempo = 0.0
        self.anim_acao = ""          # "heroi" ou "inimigo"
        self.anim_quadro = 0
        self.dano_flutuante: list[tuple[float, float, str, int]] = []
        # a pausa entre um inimigo e o proximo agirem
        self._espera_turno = 0.0
        self.log: list[str] = []
        self.resultado = ""

        self._quadros_heroi: dict[str, list[pygame.Surface]] = {}
        self._quadros_efeito: list[pygame.Surface] = []
        self._quadros_inimigo: dict[str, dict[str, list[pygame.Surface]]] = {}
        # o enlarge usado nesta luta, guardado para o desenho
        self.escala_luta = assets.escala_de_luta(self.size[1])
        # o cenario da luta, montado por `arena`. A cena precisa do
        # horizonte dele para ancorar os lutadores: se cada um usar a
        # sua conta, o fundo e o boneco discordam da linha e o boneco
        # fica boiando sobre a parede
        self.cenario_luta_arena = cenarios.POR_NOME.get("catacumbas")
        # o tile do chao e o vinhete sao fixos: montados uma vez
        # por tamanho de janela, senao a luta redesenha o cenario
        # inteiro sessenta vezes por segundo
        self._tile_cacheado: tuple = ()
        # o cenario onde a luta acontece, mandado pela masmorra: o
        # tileset da sala e os enfeites que ela tem. Sem isto a luta
        # acontece num limbo preto e o jogador nao reconhece o lugar.
        self.cenario_luta = manager.ui_state.get("cenario_luta") or {}
        self._vinhete_cache: dict = {}
        # parede e chao da sala, por tileset e tamanho de tile
        self._parede_cache: dict = {}

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        self._carregar()
        self.menu_aberto = self.batalha.turno_heroi
        self.index = 0

    def _carregar(self) -> None:
        # O enlarge e o da LUTA, calculado pela janela, e nao o global
        # das opcoes: com o global a arte de 40px de altura ficava com
        # 40px numa tela de 720p. O mesmo valor vai para o heroi e para
        # cada inimigo, senao os dois ficam de tamanhos diferentes.
        escala = assets.escala_de_luta(self.size[1])
        self.escala_luta = escala

        # O heroi da luta e o DESENHO EQUIPADO, o mesmo que anda no mapa,
        # e nao a folha de animacao do pacote de mercado.
        #
        # A folha tem 3 vezes a largura do corpo, porque a espada do
        # golpe entra por cima dela. Recortar o corpo para o box inteiro
        # punha o personagem no terço esquerdo de um desenho largo, e o
        # retangulo do sprite ficava com 180px de largura para 47px de
        # personagem: o boneco saia parecendo uma caixa, e a sombra e a
        # barra de vida mediam a caixa, nao o boneco.
        #
        # A arte do heroi e a mesma dos sprites do mapa, entao a
        # consistencia vem de graca: o que o jogador ve na luta e
        # exatamente o que ele ve na aldeia, so maior.
        progresso = self.manager.ui_state.get("progresso")
        conjunto = equip_mod.Conjunto(
            progresso.arma if progresso else None,
            progresso.escudo if progresso else None,
        )
        arte_heroi = assets.equipado_na_tela(conjunto.chave, escala)
        if arte_heroi is None:
            arte_heroi = assets.equipado_na_tela("punho", escala)

        # o golpe: o MESMO desenho, deslocado para a frente e para cima,
        # como um golpe que avanca. E assim que o boneco ataca: o corpo
        # vai para a direcao do alvo no quadro do golpe.
        if arte_heroi is not None:
            larg, alt = arte_heroi.get_size()
            parado: list[pygame.Surface] = [arte_heroi]
            golpe: list[pygame.Surface] = []
            # quatro passos de ataque: avanca, bate, volta
            for i, (dx, dy, esc) in enumerate((
                (0.10, -0.02, 1.06), (0.20, -0.04, 1.10),
                (0.14, -0.02, 1.05), (0.04, 0.00, 1.00),
            )):
                alvo = pygame.transform.scale(
                    arte_heroi, (int(larg * esc), int(alt * esc))
                )
                c = pygame.Surface((larg + int(larg * 0.34), alt))
                c.blit(alvo, (int(larg * dx), int(alt * dy)))
                golpe.append(c)
            self._quadros_heroi = {
                "idle": parado,
                "walk": parado,
                "hit": parado,
                "death": parado,
                "attack": golpe,
            }
            # a espada do golpe entra por cima, maior que o corpo
            arma = assets.carregar_animacao(
                "leste", "attack",
                box=(int(larg * 1.6), int(alt * 1.6)), scale=escala,
            )
            self._quadros_efeito = arma or []

        box_inimigo = (assets.FOE_BASE[0] * escala * 3,
                       assets.FOE_BASE[1] * escala * 3)
        for i, inimigo in enumerate(self.batalha.inimigos):
            # o chefe usa o esqueleto de chama, que e a variante mais
            # agressiva do pacote; os outros pegam os quatro na ordem
            kind = (assets.FOE_CHEFE if self.e_chefe
                    else assets.FOE_KINDS[i % len(assets.FOE_KINDS)])
            self._quadros_inimigo[id(inimigo)] = {
                estado: assets.load_foe(
                    kind, "oeste", estado, box=box_inimigo, scale=escala
                )
                for estado in ("walk", "attack")
            }

    # entrada -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        # Fim da batalha: QUALQUER tecla volta para a masmorra. O texto
        # na tela dizia "qualquer tecla para voltar" e so o Esc
        # respondia, entao a tela ficava presa ate o jogador adivinhar
        # que precisava de um botao especifico.
        if self.batalha.concluida:
            self._sair_para_masmorra()
            return

        # Com o inventario aberto as teclas sao do inventario, e o Esc
        # FECHA o inventario em vez de fugir. Este bloco vem ANTES do
        # tratamento de `voltar`: uma linha abaixo, o Esc com o
        # inventario aberto terminava a luta. Fechar um menu nao pode
        # custar a partida.
        if self.modo == "item" and self.menu_aberto:
            linhas = itens.rotulos(self._inventario())
            if self.key(event, "voltar"):
                self.modo = "acao"
                return
            if not linhas:
                self.modo = "acao"
                return
            if self.key(event, "mover_cima"):
                self.index_item = (self.index_item - 1) % len(linhas)
            elif self.key(event, "mover_baixo"):
                self.index_item = (self.index_item + 1) % len(linhas)
            elif self.key(event, "confirmar"):
                self._gastar_item(linhas[self.index_item][0])
            return

        if self.key(event, "voltar"):
            # fugir sai da luta com a vida que tinha
            self.resultado = "fuga"
            self.manager.switch("dungeon")
            return

        if not self.menu_aberto:
            return

        opcoes = list(combat.Acao)
        if self.key(event, "mover_cima"):
            self.index = (self.index - 1) % len(opcoes)
        elif self.key(event, "mover_baixo"):
            self.index = (self.index + 1) % len(opcoes)
        elif self.key(event, "confirmar"):
            self._escolher(opcoes[self.index])

    def _sair_para_masmorra(self) -> None:
        """Volta para a masmorra depois do fim da luta."""
        # A batalha termina dentro do `update`, e e la que o resultado
        # ganha o nome. Se a tecla chega ANTES desse `update` — o que
        # acontece quando o jogador esta martelando enter no fim da
        # luta — o resultado saia vazio, a masmorra nao reconhecia
        # nenhum dos tres casos e a vitoria nao pagava nem marcava a
        # sala. Aqui o resultado e decidido pela batalha, que ja sabe.
        if not self.resultado:
            if self.batalha.fugiu:
                self.resultado = "fuga"
            elif self.batalha.vencida:
                self.resultado = "vitoria"
            else:
                self.resultado = "derrota"
        # O resultado vai no estado do gerenciador, e nao na propria
        # cena. A masmorra e recriada quando a luta acaba, e uma cena
        # nova nao tem como saber o que aconteceu na anterior.
        self.manager.ui_state["resultado_combate"] = self.resultado
        self.manager.ui_state["combate_contra_chefe"] = self.e_chefe
        if self.resultado != "fuga":
            self.manager.salvar_progresso()
        self.manager.switch("dungeon")

    def _inventario(self) -> dict[str, int]:
        """O que o jogador carrega agora.

        O progresso vive no estado do gerenciador. A cena nao guarda
        copia: uma copia aqui desatualizaria na hora em que o jogador
        usasse o item, e o item volveria a aparecer no menu.
        """
        p = self.manager.ui_state.get("progresso")
        return dict(p.itens) if p is not None else {}

    def _gastar_item(self, item_id: str) -> None:
        p = self.manager.ui_state.get("progresso")
        if p is not None:
            p.usar_pocao() if item_id == "pocao" else None
        self.modo = "acao"
        self.batalha.item_escolhido = item_id
        eventos = self.batalha.acao_do_heroi(combat.Acao.ITEM)
        self.log = [e.texto for e in eventos]
        self.ja_usou_item = True
        self.ensinar_item = False
        self.menu_aberto = False
        self.anim_acao = ""
        self.anim_quadro = 0

    def _escolher(self, acao: combat.Acao) -> None:
        if acao is combat.Acao.ITEM:
            # "Usar item" nao executa nada sozinho: ele ABRE o
            # inventario. A cena e quem tem a lista na tela e quem
            # sabe qual item esta sob o cursor.
            if not itens.tem_usaveis(self._inventario()):
                self.log = ["Voce nao tem item"]
                return
            self.modo = "item"
            self.index_item = 0
            return

        eventos = self.batalha.acao_do_heroi(acao)
        self.log = [e.texto for e in eventos]
        self._flutuar(eventos)
        self.anim_acao = "heroi"
        self.anim_quadro = 0
        self.menu_aberto = False
        if self.batalha.fugiu:
            # Fugiu pelo menu e o mesmo que apertar Esc: a luta acaba e
            # o jogador volta para a masmorra com a vida que tinha. A
            # masmorra e quem decide se isso vira saida da masmorra,
            # porque so ela sabe em que sala a luta aconteceu.
            self.resultado = "fuga"

    # atualizacao ---------------------------------------------------
    def update(self, dt: float) -> None:
        self.anim_tempo += dt

        # os numeros de dano sobem e somem
        restantes = []
        for x, y, texto, cor in self.dano_flutuante:
            y -= dt * 42
            if y > -20:
                restantes.append((x, y, texto, cor))
        self.dano_flutuante = restantes

        if self.batalha.concluida:
            if self.resultado == "" and self.batalha.vencida:
                self.resultado = "vitoria"
            # A animacao do golpe precisa terminar MESMO com a batalha
            # acabada. O return abaixo vinha antes de desligar
            # `anim_acao`, entao a espada ficava congelada na tela de
            # vitoria para sempre.
            self._atualizar_animacao(dt)
            return

        # Um inimigo age por quadro. A fila e andada de um em um, para
        # que o jogador veja QUEM bateu: com tres inimigos batendo no
        # mesmo quadro, o log mostrava tres linhas de dano de uma vez e
        # nao dava para saber de quem foi. Um por quadro e o que a
        # leitura de "de quem e a vez" precisa.
        self._espera_turno = max(0.0, self._espera_turno - dt)
        eventos = self.batalha.avancar(dt) if self._espera_turno <= 0.0 else []
        if eventos:
            self.log = [e.texto for e in eventos]
            self._flutuar(eventos)
            if any(e.tipo == "dano" for e in eventos):
                self.anim_acao = "inimigo"
                self.anim_quadro = 0
            # a pausa entre um inimigo e o seguinte: o golpe precisa ser
            # visto antes do proximo. A espera so vale quando o proximo
            # da fila tambem e um inimigo: se for o heroi, o jogo abre
            # o menu na hora e nao ha nada para ver.
            proximo = self.batalha.de_quem_e_a_vez
            if (proximo is not None and proximo is not self.batalha.heroi
                    and not self.batalha.concluida):
                self._espera_turno = PAUSA_ENTRE_INIMIGOS
            else:
                self._espera_turno = 0.0

        if self._espera_turno <= 0.0:
            if self.batalha.turno_heroi and not self.menu_aberto:
                self.menu_aberto = True
                self.index = 0

        self._atualizar_animacao(dt)

    def _atualizar_animacao(self, dt: float) -> None:
        """Roda o golpe e volta para a pose quando ele acaba."""
        if not self.anim_acao:
            return
        self.anim_quadro += dt * 12
        if self.anim_quadro > 1.0:
            self.anim_acao = ""
            self.anim_quadro = 0.0

    def _flutuar(self, eventos) -> None:
        w, h = self.size
        for e in eventos:
            if e.tipo == "dano":
                self.dano_flutuante.append(
                    (w * 0.5, h * 0.4, e.texto.split()[-1], theme.GOLD)
                )

    # desenho -------------------------------------------------------
    def _cenarios_da_sala(self) -> dict | None:
        """A parede e o chao da sala onde a luta acontece.

        A parede usa as variantes de PAREDE do tileset e o chao as de
        CHAO, e as duas sao as mesmas da masmorra — a luta acontece no
        lugar certo e o jogador reconhece a pedra. Sem tileset no
        estado (luta chamada de fora, ou teste) cai no fundo generico.
        """
        nome = self.cenario_luta.get("tileset")
        if not nome:
            return None
        lado = max(16, int(self.size[1] * 0.09))
        chave = ("sala", nome, lado)
        if chave in self._parede_cache:
            return self._parede_cache[chave]
        partes = None
        try:
            from . import cenarios, dungeon_scene

            cenario = cenarios.POR_NOME.get(nome)
            tabela = (dungeon_scene._tabela_wang(cenario)
                      if cenario is not None else None)
            if tabela:
                chao = tabela.get((False, False, False, False))
                parede = tabela.get((True, True, True, True))
                if parede is None:
                    parede = next(
                        (v for k, v in tabela.items() if all(k)), None
                    )
                if chao is not None and parede is not None:
                    partes = {
                        "chao": pygame.transform.scale(chao, (lado, lado)),
                        "parede": pygame.transform.scale(parede, (lado, lado)),
                    }
        except Exception:  # noqa: BLE001 - o tileset e opcional
            partes = None
        self._parede_cache[chave] = partes
        return partes

    def _desenhar_parede_da_sala(self, surface: pygame.Surface,
                                horizonte: int) -> None:
        """A parede do fundo da sala, com a fiada de pedra de cima.

        E o que separa a tela de combate de um retangulo: o jogador ve
        a parede de tras, e ela e a MESMA parede da sala em que ele esta
        lutando.
        """
        partes = self._cenarios_da_sala()
        if partes is None:
            return
        parede = partes["parede"]
        w = surface.get_width()
        x = -(int(self.anim_tempo * 6) % parede.get_width())
        y = 0
        while x < w and y < horizonte:
            surface.blit(parede, (x, y))
            x += parede.get_width()
            y += parede.get_height()
        # fecha o que sobrou acima da ultima fiada
        if y < horizonte:
            pygame.draw.rect(
                surface, theme.BACKGROUND,
                pygame.Rect(0, y, w, horizonte - y),
            )

    def _desenhar_enfeites_da_sala(self, surface: pygame.Surface,
                                   horizonte: int) -> None:
        """Os mesmos barris e ossos que a sala tinha antes da luta.

        Sao distribuidos em DUAS fiadas para dar profundidade: a de
        tras fica um pouco acima da linha do chao e sai menor, a da
        frente fica na linha e sai do tamanho normal. Numa fiada so —
        que foi a primeira versao — os enfeites viravam um palito
        atravessado na tela, e nao um canto de sala.

        A faixa do meio fica livre: e onde os lutadores ficam, e um
        barril na frente da cara do heroi atrapalha a leitura do golpe.
        """
        enfeites = self.cenario_luta.get("enfeites") or []
        if not enfeites:
            return
        from . import cenario as cenario_mod

        w, h = self.size
        xs = [p[0] for p in enfeites]
        ys = [p[1] for p in enfeites]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        if x1 == x0 or y1 == y0:
            return

        # So uma PARTE dos enfeites entra, e so nos cantos. Mapear os
        # vinte e seis numa faixa dava um palito atravessado na tela;
        # e o meio e onde os lutadores ficam. Nos cantos, em duas
        # profundidades, le como um canto de sala.
        canto_esq, canto_dir = [], []
        for i, p in enumerate(sorted(enfeites, key=lambda q: q[1])):
            pos = (p[0] - x0) / (x1 - x0)
            if pos < 0.42:
                canto_esq.append(p)
            elif pos > 0.58:
                canto_dir.append(p)
        escolhidos = canto_esq[-4:] + canto_dir[-4:]

        for i, (cx, cy, nome) in enumerate(escolhidos):
            pos = (cx - x0) / (x1 - x0)
            # dentro de cada canto, duas fiadas: a de tras sobe e
            # encolhe, a da frente fica na linha do chao
            profundidade = i % 2
            px = int(w * (0.04 + pos * 0.92))
            if profundidade:
                py = horizonte - int(h * 0.012)
                lado = max(12, int(h * 0.040))
            else:
                py = horizonte + int(h * 0.045)
                lado = max(15, int(h * 0.062))
            arte = cenario_mod.carregar_enfeite(nome, lado)
            if arte is not None:
                surface.blit(arte, arte.get_rect(midbottom=(px, py)))

    def _desenhar_cenario(self, surface: pygame.Surface) -> None:
        """A sala da luta: parede em fiadas, chao em perspectiva, tochas.

        Este metodo era o responsavel por TUDO do fundo, e cada parte
        estava errada a sua maneira:

          - a parede usava a peca do tileset repetida em x e y, com a
            peca inteira em cada posicao, e virava um papel de parede
            com pontilhado;
          - o chao era o ladrilho repetido em linhas de tamanho igual,
            todas do mesmo tamanho, sem nenhuma fiada maior que a outra:
            um retangulo, nao um chao;
          - embaixo da linha do horizonte era desenhado
            `theme.BACKGROUND_SOFT`, que e quase preto: uma faixa preta
            de 300px embaixo dos lutadores, e o motivo de a foto do
            jogador mostrar o boneco em cima de um vazio;
          - o vinhete escurecia a tela toda em volta.

        Agora o fundo e `arena.arena`, que monta a parede em fiadas com
        a junta da propria arte, o chao em fiadas que crescem para a
        frente, e a luz das tochas. O horizonte vem de la, e e o mesmo
        que ancoreia os lutadores.
        """
        w, h = self.size
        horizonte = self._horizonte()
        surface.blit(
            arena_mod.arena(w, h, self.cenario_luta_arena, self.anim_tempo),
            (0, 0),
        )
        self._desenhar_enfeites_da_sala(surface, horizonte)

        vinhete = self._vinhete(w, h)
        if vinhete is not None:
            surface.blit(vinhete, (0, 0))

    def _horizonte(self) -> int:
        """A linha do chao da luta, em pixels.

        Vem da arena, e nao de uma conta da cena: as duas usando numeros
        diferentes era a forma de o fundo e os lutadores discordarem da
        linha, e o boneco ficar boiando sobre a parede.
        """
        return int(self.size[1] * arena_mod.HORIZONTE)

    def _tile_de_cenario(self) -> pygame.Surface | None:
        """O tile do chao das catacumbas, ou None se nao houver.

        Reaproveita a tabela Wang que a masmorra monta, para a luta
        acontecer no mesmo chao do mapa e nao num limbo preto.
        """
        if self._tile_cacheado:
            return self._tile_cacheado[0]
        tile = None
        try:
            from . import cenarios, dungeon_scene

            cenario = cenarios.POR_NOME.get("catacumbas")
            if cenario is not None:
                tabela = dungeon_scene._tabela_wang(cenario)
                if tabela:
                    # a chave (False, False, False, False) e o chao puro
                    chao = tabela.get((False, False, False, False))
                    if chao is None:
                        chao = next(iter(tabela.values()))
                    if chao is not None:
                        tile = pygame.transform.scale(chao, (48, 48))
        except Exception:  # noqa: BLE001 - o tileset e opcional
            tile = None
        self._tile_cacheado = (tile,)
        return tile

    def _vinhete(self, w: int, h: int) -> pygame.Surface | None:
        """A borda escura, montada uma vez por tamanho de janela."""
        chave = (w, h)
        if chave in self._vinhete_cache:
            return self._vinhete_cache[chave]
        toldo = max(24, min(w, h) // 6)
        v = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(toldo):
            alfa = int(120 * (1.0 - i / toldo) ** 2)
            pygame.draw.rect(
                v, (0, 0, 0, alfa),
                pygame.Rect(i, i, w - 2 * i, h - 2 * i),
                1,
            )
        self._vinhete_cache[chave] = v
        return v

    def draw(self, surface: pygame.Surface) -> None:
        w, h = self.size
        self._desenhar_cenario(surface)

        self._desenhar_inimigos(surface, w, h)
        self._desenhar_heroi(surface, w, h)
        self._desenhar_vez(surface, w, h)
        self._desenhar_dano(surface)
        self._desenhar_log(surface, w, h)

        if self.menu_aberto and not self.batalha.concluida:
            if self.modo == "item":
                self._desenhar_inventario(surface, w, h)
            else:
                self._desenhar_menu(surface, w, h)
        elif self.batalha.concluida:
            self._desenhar_resultado(surface, w, h)

    def _desenhar_inventario(self, surface, w, h) -> None:
        """O inventario aberto durante a luta.

        Fica por cima do menu de acoes, e nao em outra tela: o jogador
        precisa ver a barra de vida mudar no mesmo instante em que
        confirma, senao a pociao parece nao ter funcionado.
        """
        linhas = itens.rotulos(self._inventario())
        caixa = pygame.Rect(0, 0, min(360, w - 40), 74 + 30 * max(1, len(linhas)))
        caixa.center = (w // 2, h // 2)
        pygame.draw.rect(surface, theme.BACKGROUND, caixa.inflate(12, 12))
        pygame.draw.rect(surface, theme.HAIRLINE, caixa.inflate(12, 12), 1)

        theme.text_tracked_at(
            surface, "ITENS", 17,
            (caixa.x, caixa.y - 26), theme.GOLD)

        if not linhas:
            theme.text_tracked_at(
                surface, "Voce nao tem item", 16,
                (caixa.x, caixa.y), theme.TEXT_DIM)
            theme.text_tracked_at(
                surface, "esc para voltar", 13,
                (caixa.x, caixa.bottom + 8), theme.TEXT_DIM)
            return

        for i, (item_id, item, qtd) in enumerate(linhas):
            y = caixa.y + i * 30
            marcado = i == self.index_item
            cor = theme.GOLD if marcado else theme.TEXT
            pygame.draw.rect(
                surface, theme.BACKGROUND_SOFT,
                pygame.Rect(caixa.x - 4, y - 4, caixa.width + 8, 28),
            )
            if marcado:
                pygame.draw.rect(
                    surface, theme.GOLD,
                    pygame.Rect(caixa.x - 4, y - 4, 3, 28),
                )
            theme.text_tracked_at(
                surface, f"{item.nome} x{qtd}", 16, (caixa.x + 4, y), cor)
            theme.text_tracked_at(
                surface, item.descricao, 12,
                (caixa.x + 4, y + 16), theme.TEXT_DIM)

        theme.text_tracked_at(
            surface, "enter usa   esc volta", 13,
            (caixa.x, caixa.bottom + 10), theme.TEXT_DIM)

    def _desenhar_heroi(self, surface, w, h) -> None:
        estado = "idle"
        if not self.batalha.heroi.vivo:
            estado = "death"
        elif self.anim_acao == "heroi":
            estado = "attack"
        elif self.anim_acao == "inimigo":
            estado = "hit"

        quadros = self._quadros_heroi.get(estado) or self._quadros_heroi.get("idle")
        if not quadros:
            return
        idx = int(self.anim_tempo * assets.fps_do_estado(estado)) % len(quadros)
        sprite = quadros[idx]
        # pelo PE, e o pe na linha do chao DA ARENA mais o quanto o
        # heroi avanca para a camera. A versao anterior ancorava numa
        # conta da cena (0.62) e o fundo cortava em 0.58: o boneco
        # estava 29px dentro do chao, boiando sobre a parede.
        chao = int(h * (arena_mod.HORIZONTE + HEROI_A_FRENTE))
        pos = (int(w * HEROI_POS), chao)
        rect = sprite.get_rect(midbottom=pos)
        # a sombra vem antes do boneco, e no chao: e ela que diz que o
        # personagem esta apoiado e nao colado na parede
        arena_mod.sombra_chao(surface, rect.centerx, chao, rect.width)
        surface.blit(sprite, rect)

        # a espada entra por cima do corpo enquanto o golpe roda
        if self.anim_acao == "heroi" and self._quadros_efeito:
            ei = min(int(self.anim_quadro * len(self._quadros_efeito)),
                     len(self._quadros_efeito) - 1)
            surface.blit(self._quadros_efeito[ei], self._quadros_efeito[ei]
                         .get_rect(center=(rect.centerx + 26, rect.centery - 18)))

        self._desenhar_nome(surface, self.batalha.heroi, rect)

    def _desenhar_inimigos(self, surface, w, h) -> None:
        for i, inimigo in enumerate(self.batalha.inimigos):
            quadros = self._quadros_inimigo.get(id(inimigo), {})
            estado = "attack" if (self.anim_acao == "inimigo"
                                  and inimigo.vivo) else "walk"
            lista = quadros.get(estado) or quadros.get("walk")
            if not lista:
                continue
            idx = int(self.anim_tempo * assets.fps_do_estado(estado)) % len(lista)
            sprite = lista[idx]

            x = w * INIMIGO_X[i % len(INIMIGO_X)]
            # cada inimigo fica um pouco mais ATRAS na tela e um pouco
            # MENOR. E a profundidade em duas dimensoes: sem isso os
            # tres ficam na mesma linha, do mesmo tamanho, e a tela le
            # como tres bonecos colados num retangulo.
            tras, encolhe = INIMIGO_ATRAS[i % len(INIMIGO_ATRAS)]
            if encolhe < 1.0:
                sprite = pygame.transform.smoothscale(
                    sprite,
                    (max(1, int(sprite.get_width() * encolhe)),
                     max(1, int(sprite.get_height() * encolhe))),
                )
            chao = int(h * arena_mod.HORIZONTE) + int(h * tras)
            rect = sprite.get_rect(midbottom=(int(x), chao))

            if inimigo.vivo:
                arena_mod.sombra_chao(surface, rect.centerx, chao, rect.width)
                surface.blit(sprite, rect)
                self._desenhar_nome(surface, inimigo, rect)
                continue

            # Caido: o sprite simplesmente nao e desenhado. A versao
            # anterior punha um retangulo escuro no lugar dele, que
            # aparecia como um bloco preto solto no chao e nao lia
            # como nada. O que sobra e o nome com o risco zerado, que
            # e o que diz que o inimigo caiu.
            pygame.draw.rect(
                surface, theme.HAIRLINE,
                pygame.Rect(rect.centerx - 24, rect.top - 18, 48, 3),
            )
            theme.text_tracked_at(
                surface, inimigo.nome.upper(), 12,
                (rect.centerx, rect.top - 30), theme.HAIRLINE,
            )

    def _desenhar_nome(self, surface, lutador, rect) -> None:
        """Nome e barra de vida em cima do sprite.

        A barra tem fundo escuro desenhado primeiro: sem ele, a parte
        vazia e tao escura quanto a tela e o que sobra e so um risco
        dourado, que parece um sublinhado em vez de medidor.

        A barra e de VIDA, e nao de tempo: mede o quanto o lutador tem
        de HP, nao o quanto falta para ele agir. A etiqueta "TEMPO" e a
        barra de ATB que existiram antes sairam daqui; o que diz de quem
        e a vez esta em `_desenhar_vez`, no alto da tela.

        De quem e a vez o lutador recebe uma moldura dourada em volta
        do nome. E o unico lugar da tela que se move quando muda a vez,
        e e o que o jogador olha para saber o que fazer.
        """
        de_vez = self.batalha.de_quem_e_a_vez is lutador
        cor_nome = theme.GOLD if de_vez else theme.TEXT_DIM
        theme.text_tracked_at(
            surface, lutador.nome.upper(), 13,
            (rect.centerx, rect.top - 30), cor_nome,
        )
        if de_vez:
            # a moldura da vez: um quadrado aberto embaixo do nome,
            # apontando para o lutador, e uma barra fina em volta
            larg, alt = self._largura_do_nome(lutador.nome)
            caixa = pygame.Rect(
                rect.centerx - larg // 2 - 6, rect.top - 36,
                larg + 12, 20,
            )
            pygame.draw.rect(surface, theme.GOLD, caixa, 1)

        largura = max(52, rect.width)
        barra = pygame.Rect(
            rect.centerx - largura // 2, rect.top - 12, largura, 6
        )
        pygame.draw.rect(surface, (18, 16, 15), barra.inflate(2, 2))
        pygame.draw.rect(surface, (58, 52, 44), barra)
        cheio = pygame.Rect(
            barra.x, barra.y,
            max(0, int(barra.width * lutador.fracao_vida)), barra.height,
        )
        # a barra e de vida: cheia e dourada, e fica vermelha quando o
        # lutador esta perto de cair
        if lutador.fracao_vida > 0.5:
            cor = theme.GOLD
        elif lutador.fracao_vida > 0.22:
            cor = theme.lerp(theme.GOLD, (176, 62, 52), 0.6)
        else:
            cor = (196, 68, 56)
        pygame.draw.rect(surface, cor, cheio)

    def _largura_do_nome(self, nome: str) -> tuple[int, int]:
        """`(largura, altura)` que o nome ocupa na fonte da tela."""
        fonte = pygame.font.Font(None, 13)
        larg, alt = fonte.size(nome.upper())
        return larg + len(nome.upper()) * 2, alt

    def _desenhar_vez(self, surface, w, h) -> None:
        """De quem e a vez, e a fila inteira, no alto da tela.

        Este era o lugar das barras de tempo do ATB: a etiqueta "TEMPO"
        e um medidor por lutador no rodape da tela. A foto do jogador
        mostrou o resultado, dois riscos dourados no chao com nada
        dizendo a que se referiam.

        A vez e um texto: "SUA VEZ" quando o heroi age, e o nome do
        inimigo quando ele age. E a fila logo abaixo, em ordem, com o
        que vem agora marcado. Uma tela de briga precisa responder a
        "de quem e a vez" num olhar, e um medidor que corre nao
        responde a nada.
        """
        de_quem = self.batalha.de_quem_e_a_vez
        if self.batalha.concluida or de_quem is None:
            return

        topo = int(h * 0.055)
        if de_quem is self.batalha.heroi:
            texto, cor = "SUA VEZ", theme.GOLD
        else:
            texto, cor = f"VEZ DE {de_quem.nome.upper()}", theme.TEXT_DIM

        larg_texto = self._largura_do_nome(texto)[0]
        caixa = pygame.Rect(0, topo - 12, larg_texto + 28, 24)
        caixa.centerx = w // 2
        pygame.draw.rect(surface, (14, 13, 12), caixa)
        pygame.draw.rect(surface, theme.HAIRLINE, caixa, 1)
        theme.text_tracked_at(
            surface, texto, 15,
            (caixa.centerx - larg_texto // 2, caixa.centery), cor,
        )

        # a fila: quem age agora, e quem vem depois. So os vivos.
        fila = [c for c in self.batalha.fila if c.vivo]
        if len(fila) < 2:
            return
        y = caixa.bottom + 16
        x = w // 2 - (len(fila) - 1) * (w * 0.09)
        for i, c in enumerate(fila):
            e_agora = i == 0
            cor_fila = theme.GOLD if e_agora else theme.TEXT_DIM
            cx = int(x + i * w * 0.18)
            # a seta marca quem age: e o que diz "agora", sem texto
            if e_agora:
                pygame.draw.polygon(
                    surface, theme.GOLD,
                    [(cx, y - 8), (cx - 5, y - 16), (cx + 5, y - 16)],
                )
            pygame.draw.circle(
                surface, cor_fila,
                (cx, y + 4), 8, 0, 2,
            )
            pygame.draw.circle(
                surface, cor_fila,
                (cx, y + 4), 8, 0 if e_agora else 1,
            )
            # a fracao de vida dentro do circulo: da para ver quem esta
            # machucado sem desviar o olho do meio da tela
            pygame.draw.arc(
                surface, theme.GOLD,
                pygame.Rect(cx - 8, y - 4, 16, 16),
                math.pi / 2, math.pi / 2 + math.tau * c.fracao_vida, 2,
            )
            theme.text_tracked_at(
                surface, c.nome.split()[0].upper(), 10,
                (cx, y + 22), cor_fila,
            )

    def _desenhar_dano(self, surface) -> None:
        for x, y, texto, cor in self.dano_flutuante:
            theme.text_tracked_at(surface, texto, 22, (int(x), int(y)), cor)

    def _desenhar_log(self, surface, w, h) -> None:
        if not self.log:
            return
        theme.text_tracked_at(
            surface, self.log[-1], 16, (int(w * 0.08), int(h * 0.90)),
            theme.TEXT_DIM,
        )

    def _desenhar_menu(self, surface, w, h) -> None:
        """As cinco acoes, nos slots da fileira do Action_panel.

        A arte traz uma barra de madeira com slots vazios. O que falta e
        o CONTEUDO. Dentro do slot cabe um ICONE e nao o nome:
        "HABILIDADE" com 13px passa de 70px de largura e o nome invadia
        o slot vizinho. O nome da acao escolhida fica na faixa de cima,
        que e larga de verdade para isso.
        """
        opcoes = list(combat.Acao)
        ICONES = {
            combat.Acao.ATACAR: "espada",
            combat.Acao.DEFENDER: "escudo",
            combat.Acao.HABILIDADE: "rosto",
            combat.Acao.ITEM: "pocao_azul",
            combat.Acao.FUGIR: "olho",
        }

        barra = ui_arte.desenhar(
            surface, ui_arte.PAINEL_ACAO_BAR,
            (w // 2, int(h * 0.88)), int(w * 0.34),
        )
        if barra is None:
            self._desenhar_menu_simples(surface, w, h)
            return

        escolhido = opcoes[self.index] if self.index < len(opcoes) else None

        header = ui_arte.desenhar(
            surface, ui_arte.PAINEL_ACAO_HEADER,
            (w // 2, barra.y - int(h * 0.05)), int(w * 0.30),
        )
        if header is not None:
            nome = escolhido.value.upper() if escolhido is not None else ""
            theme.text_tracked_at(
                surface, nome, 17,
                (header.centerx - 5 * len(nome), header.centery - 8),
                theme.GOLD)

        caixas = ui_arte.slots_da_barra(barra, len(opcoes))
        for i, acao in enumerate(opcoes):
            if i >= len(caixas):
                break
            caixa = caixas[i]
            selecionado = i == self.index

            arte = ui_arte.icone(ICONES.get(acao, ""))
            if arte is not None:
                # o icone AMPLIA ate o slot: e um sprite de 14px num
                # slot de 70, deixado no tamanho original ele virava um
                # ponto minusculo no meio da madeira
                lado = max(8, min(caixa.width, caixa.height) - 12)
                if arte.get_width() != lado:
                    arte = pygame.transform.scale(arte, (lado, lado))
                surface.blit(arte, arte.get_rect(center=caixa.center))

            if selecionado:
                pygame.draw.rect(
                    surface, theme.GOLD, caixa.inflate(-8, -8), 2)

            # a aula da sala da pocao aponta a opcao, e some assim que
            # o jogador usa o item pela primeira vez
            if (self.ensinar_item and acao is combat.Acao.ITEM
                    and not self.ja_usou_item):
                cor_pulso = theme.lerp(
                    theme.GOLD, theme.TEXT, theme.pulse(self.anim_tempo)
                )
                pygame.draw.rect(
                    surface, cor_pulso, caixa.inflate(-8, -8), 2)
                theme.text_tracked_at(
                    surface, "aqui", 13,
                    (caixa.centerx - 18, caixa.y - 18), cor_pulso)

        theme.text_tracked_at(
            surface, "setas movem   enter confirma   esc foge",
            13, (barra.x, barra.bottom + 14), theme.TEXT_DIM)

        if self.ensinar_item and not self.ja_usou_item:
            theme.text_tracked_at(
                surface,
                "Escolha USAR ITEM com as setas e enter. O inventario abre.",
                15, (int(w * 0.30), header.y - 24 if header is not None
                     else barra.y - 40), theme.GOLD)

    def _desenhar_menu_simples(self, surface, w, h) -> None:
        """O menu em texto, so quando a arte dos slots nao veio."""
        opcoes = list(combat.Acao)
        base_y = int(h * 0.86)
        passo = 26
        x = int(w * 0.30)
        for i, acao in enumerate(opcoes):
            selecionado = i == self.index
            cor = theme.GOLD if selecionado else theme.TEXT_DIM
            y = base_y + i * passo
            theme.text_tracked_at(surface, acao.value.upper(), 18, (x, y), cor)
            if selecionado:
                pygame.draw.polygon(
                    surface, cor,
                    [(x - 18, y), (x - 12, y - 5), (x - 18, y - 10)],
                )
    def _desenhar_menu_simples(self, surface, w, h) -> None:
        """O menu em texto, so quando a arte dos slots nao veio."""
        opcoes = list(combat.Acao)
        base_y = int(h * 0.86)
        passo = 26
        x = int(w * 0.30)
        for i, acao in enumerate(opcoes):
            selecionado = i == self.index
            cor = theme.GOLD if selecionado else theme.TEXT_DIM
            y = base_y + i * passo
            theme.text_tracked_at(surface, acao.value.upper(), 18, (x, y), cor)
            if selecionado:
                pygame.draw.polygon(
                    surface, cor,
                    [(x - 18, y), (x - 12, y - 5), (x - 18, y - 10)],
                )
    def _desenhar_menu_simples(self, surface, w, h) -> None:
        """O menu em texto, so quando a arte dos slots nao veio."""
        opcoes = list(combat.Acao)
        base_y = int(h * 0.86)
        passo = 26
        x = int(w * 0.30)
        for i, acao in enumerate(opcoes):
            selecionado = i == self.index
            cor = theme.GOLD if selecionado else theme.TEXT_DIM
            y = base_y + i * passo
            theme.text_tracked_at(surface, acao.value.upper(), 18, (x, y), cor)
            if selecionado:
                pygame.draw.polygon(
                    surface, cor,
                    [(x - 18, y), (x - 12, y - 5), (x - 18, y - 10)],
                )
    def _desenhar_resultado(self, surface, w, h) -> None:
        texto = "VITORIA" if self.batalha.vencida else "VOCE CAIU"
        theme.text_tracked(
            surface, texto, int(h * 0.07), (w // 2, int(h * 0.28)),
            theme.GOLD if self.batalha.vencida else theme.TEXT_DIM,
            tracking=6,
        )
        theme.text_tracked_at(
            surface, "qualquer tecla para voltar", 15,
            (w // 2, int(h * 0.36)), theme.HAIRLINE,
        )





