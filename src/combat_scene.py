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

from . import assets, combat, theme
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
        self.batalha = combat.Batalha(
            heroi=combat.novo_heroi(),
            inimigos=[combat.novo_esqueleto(i) for i in range(inimigos)],
        )
        self.index = 0
        self.menu_aberto = False
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

        if self.key(event, "voltar"):
            # fugir sai da luta com a vida que tinha
            self.resultado = "fuga"
            self.manager.switch("dungeon")
            return

        if not self.menu_aberto or self.batalha.concluida:
            return

        opcoes = list(combat.Acao)
        if self.key(event, "mover_cima"):
            self.index = (self.index - 1) % len(opcoes)
        elif self.key(event, "mover_baixo"):
            self.index = (self.index + 1) % len(opcoes)
        elif self.key(event, "confirmar"):
            self._escolher(opcoes[self.index])

    def _escolher(self, acao: combat.Acao) -> None:
        eventos = self.batalha.acao_do_heroi(acao)
        self.log = [e.texto for e in eventos]
        self._flutuar(eventos)
        self.anim_acao = "heroi"
        self.anim_quadro = 0
        self.menu_aberto = False

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

        # anima da acao: o golpe tem duracao fixa e depois volta a pose
        if self.anim_acao:
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
            self._desenhar_menu(surface, w, h)
        elif self.batalha.concluida:
            self._desenhar_resultado(surface, w, h)

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

            # caido: o sprite some sob um véu escuro, o que dá menos
            # trabalho do que ter uma pose de morte e marca o estado sem
            # depender de cor
            chapa = pygame.Surface(rect.size, pygame.SRCALPHA)
            chapa.fill((0, 0, 0, 190))
            surface.blit(chapa, rect)

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
        """Menu de acoes, embaixo, como o Chrono Trigger."""
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