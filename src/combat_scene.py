"""Cena de combate por turnos, com medidor de tempo.

O Chrono Trigger nao alterna turnos: todo mundo tem uma barra que enche
sozinha, e age quando ela chega no fim. Aqui a tela mostra essas barras,
o jogador escolhe o que fazer quando a vez dele chega, e o esqueleto age
na dele sem perguntar.

A cena cuida do desenho (barras, poses, numeros de dano) e do menu; as
regras estao em `src/combat.py`.
"""
from __future__ import annotations

import pygame

from . import assets, combat, itens, theme, ui_arte
from .scene import Scene

DT_FIXO = 1 / 60

# quanto tempo o numero de dano sobe na tela
DANO_VIDA = 1.0

# posicoes na tela (fracao), para o layout acompanhar a resolucao
HEROI_POS = (0.30, 0.62)
INIMIGO_X = (0.58, 0.72, 0.86)


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
        self.log: list[str] = []
        self.resultado = ""

        self._quadros_heroi: dict[str, list[pygame.Surface]] = {}
        self._quadros_efeito: list[pygame.Surface] = []
        self._quadros_inimigo: dict[str, dict[str, list[pygame.Surface]]] = {}

    # ciclo de vida -------------------------------------------------
    def on_enter(self) -> None:
        self._carregar()
        self.menu_aberto = self.batalha.turno_heroi
        self.index = 0

    def _carregar(self) -> None:
        escala = assets.get_sprite_scale()
        base = (assets.HERO_BASE[0] * 6, assets.HERO_BASE[1] * 6)
        for estado in ("idle", "walk", "attack", "hit", "death"):
            self._quadros_heroi[estado] = assets.carregar_animacao(
                "leste", estado, box=base, scale=escala
            )
        # a espada do golpe e maior que o corpo: entra por cima
        self._quadros_efeito = assets.carregar_animacao(
            "leste", "attack", box=(base[0] * 3, base[1] * 3), scale=escala
        )
        for i, inimigo in enumerate(self.batalha.inimigos):
            kind = assets.FOE_KINDS[i % len(assets.FOE_KINDS)]
            self._quadros_inimigo[id(inimigo)] = {
                estado: assets.load_foe(kind, "oeste", estado, scale=escala)
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

        eventos = self.batalha.avancar(dt)
        if eventos:
            self.log = [e.texto for e in eventos]
            self._flutuar(eventos)
            if any(e.tipo == "dano" for e in eventos):
                self.anim_acao = "inimigo"
                self.anim_quadro = 0

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
    def draw(self, surface: pygame.Surface) -> None:
        w, h = self.size
        surface.fill(theme.BACKGROUND)

        # fundo: um chao escuro, para nao parecer a tela vazia
        pygame.draw.rect(
            surface, theme.BACKGROUND_SOFT,
            pygame.Rect(0, int(h * 0.72), w, h),
        )
        theme.hairline(surface, 0, int(h * 0.72), w)

        self._desenhar_inimigos(surface, w, h)
        self._desenhar_heroi(surface, w, h)
        self._desenhar_barras(surface, w, h)
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
        pos = (int(w * HEROI_POS[0]), int(h * HEROI_POS[1]))
        rect = sprite.get_rect(center=pos)
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
            y = h * (0.50 + 0.07 * (i % 3))
            # o esqueleto e mais alto que largo: o rect centrado o
            # deixava flutuando, porque o pe dele ficava no meio da
            # linha de chao. Pinar pelo pe e o que coloca todo mundo
            # apoiado no mesmo chao
            chao = int(h * (0.66 + 0.07 * (i % 3)))
            rect = sprite.get_rect(midbottom=(int(x), chao))

            if inimigo.vivo:
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
        """
        theme.text_tracked_at(
            surface, lutador.nome.upper(), 13,
            (rect.centerx, rect.top - 30), theme.TEXT_DIM,
        )
        largura = max(52, rect.width)
        barra = pygame.Rect(
            rect.centerx - largura // 2, rect.top - 18, largura, 5
        )
        pygame.draw.rect(surface, (24, 22, 20), barra.inflate(2, 2))
        pygame.draw.rect(surface, theme.HAIRLINE, barra)
        cheio = pygame.Rect(
            barra.x, barra.y, int(barra.width * lutador.fracao_vida), barra.height
        )
        cor = theme.GOLD if lutador.vivo else theme.TEXT_DIM
        pygame.draw.rect(surface, cor, cheio)

    def _desenhar_barras(self, surface, w, h) -> None:
        """Os medidores de tempo: a regra do combate, na tela."""
        y = int(h * 0.80)
        self._barra_de_tempo(
            surface, pygame.Rect(int(w * 0.08), y, int(w * 0.34), 7),
            self.batalha.heroi,
        )
        theme.text_tracked_at(
            surface, "TEMPO", 12, (int(w * 0.08), y - 14), theme.HAIRLINE
        )

        for i, inimigo in enumerate(self.batalha.inimigos_vivos()):
            x = int(w * (0.52 + 0.16 * i))
            self._barra_de_tempo(
                surface, pygame.Rect(x, y, int(w * 0.13), 5), inimigo
            )

    def _barra_de_tempo(self, surface, rect, lutador) -> None:
        """Medidor de quem pode agir.

        O medidor enche e transborda: enquanto o jogador nao escolhe, a
        barra fica cheia e piscando, para ficar claro que o tempo parou
        de andar e nao e a barra que travou.
        """
        pygame.draw.rect(surface, theme.HAIRLINE, rect)
        frac = 1.0 if lutador is self.batalha.heroi and self.batalha.turno_heroi \
            else lutador.barra.fracao
        cheio = pygame.Rect(rect.x, rect.y, int(rect.width * frac), rect.height)
        cor = theme.GOLD
        if lutador is self.batalha.heroi and self.batalha.turno_heroi:
            # piscando enquanto aguarda a escolha
            if int(self.anim_tempo * 4) % 2:
                cor = theme.GOLD_BRIGHT
        pygame.draw.rect(surface, cor, cheio)

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