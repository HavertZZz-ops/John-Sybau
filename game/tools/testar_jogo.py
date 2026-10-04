"""Testes da maquina de estados, da camera e do desenho.

Roda o jogo de verdade, sem abrir janela para sempre: cria o jogo, simula
teclas, avanca alguns quadros e confere o que mudou.

    python tools/testar_jogo.py

O que estes testes pegam, e por que cada caso existe:

- **Menu nao sai com o tempo.** O menu precisa de uma TECLA. Um teste que
  so roda quadros sem apertar nada passa mesmo com o menu travado.
- **Exploracao anda quando a tecla esta apertada.** Se `get_pressed`
  estiver mal ligado, o jogador nunca sai do lugar e nada mais disso
  aparece.
- **A camera nao mostra fora do mapa.** Com a tela maior que o mapa, a
  camera centraliza e aparece o vazio nas bordas.
- **Chegar na saida troca de estado.** E a mecanica que faz o mapa ter
  sentido; sem ela o mapa e um cenario para andar sem objetivo.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((64, 64))

import main  # noqa: E402
import settings  # noqa: E402

FALHAS: list[str] = []


def checar(descricao: str, condicao: bool, detalhe: str = "") -> None:
    if condicao:
        print(f"  [ok]   {descricao}")
    else:
        print(f"  [FALHA] {descricao} {detalhe}")
        FALHAS.append(descricao)


def novo_jogo() -> "main.Jogo":
    """Um jogo novo, no menu, com a fila de eventos limpa."""
    pygame.event.clear()
    return main.Jogo()


def andar(jogo: "main.Jogo", teclas: dict[str, bool], quadros: int = 60) -> None:
    """Avanca quadros com um conjunto de teclas apertadas.

    Sem isto, nao ha como testar movimento: `get_pressed` le o estado
    REAL do teclado, e um teste so pode apertar de verdade. Aqui o
    jogo recebe um dicionario e o `pygame.key.get_pressed` e
    substituido durante os quadros.
    """
    original = pygame.key.get_pressed
    falso = type("Teclas", (), {
        "__getitem__": lambda self, k: teclas.get(k, False),
    })()
    pygame.key.get_pressed = lambda: falso
    try:
        for _ in range(quadros):
            jogo.atualizar(1 / 60)
    finally:
        pygame.key.get_pressed = original


def main_teste() -> int:
    print("=" * 62)
    print("testes do jogo: estados, camera e desenho")

    # --- o menu ------------------------------------------------------
    print("\nMenu")
    jogo = novo_jogo()
    checar("comeca no menu", isinstance(jogo.estado, main.Menu))

    # O menu nao sai sozinho com o tempo. Um quadro sem tecla tem de
    # deixar o estado igual.
    jogo.atualizar(1 / 60)
    checar("nao sai sem tecla", isinstance(jogo.estado, main.Menu))

    # Uma tecla comeca.
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)
    checar("tecla comeca o jogo", isinstance(jogo.estado, main.Exploracao))

    # --- movimento ---------------------------------------------------
    print("\nMovimento")
    jogo = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)

    inicio = jogo.jogador.posicao.copy()
    andar(jogo, {pygame.K_d: True}, quadros=30)
    andou = jogo.jogador.posicao.x > inicio.x
    checar("anda para a direita", andou,
           f"({inicio.x:.0f} -> {jogo.jogador.posicao.x:.0f})")

    inicio = jogo.jogador.posicao.copy()
    andar(jogo, {pygame.K_s: True}, quadros=30)
    checar("anda para baixo", jogo.jogador.posicao.y > inicio.y,
           f"({inicio.y:.0f} -> {jogo.jogador.posicao.y:.0f})")

    # A parede da esquerda: nao pode atravessar.
    jogo2 = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo2.atualizar(1 / 60)
    andar(jogo2, {pygame.K_a: True}, quadros=200)
    checar("nao atravessa a parede",
           jogo2.jogador.posicao.x > settings.TAMANHO_DO_TILE // 2,
           f"(x={jogo2.jogador.posicao.x:.0f})")

    # --- a camera ----------------------------------------------------
    print("\nCamera")
    jogo = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)
    jogo.camera_seguir_o_jogador()

    largura_mapa = jogo.mapa.largura * settings.TAMANHO_DO_TILE
    checar("camera nao passa da esquerda", jogo.camera.x >= 0,
           f"({jogo.camera.x})")
    checar("camera nao passa da direita",
           jogo.camera.x <= max(0, largura_mapa - settings.LARGURA),
           f"({jogo.camera.x}, max {largura_mapa - settings.LARGURA})")

    # --- a saida troca de estado ------------------------------------
    print("\nSaida")
    jogo = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)

    # Teleporta o heroi para a saida, que e o que o jogador faz depois
    # de andar ate la.
    saidas = jogo.mapa.saidas()
    checar("o mapa tem saida", len(saidas) == 1, f"({len(saidas)})")
    if saidas:
        coluna, linha = saidas[0]
        lado = settings.TAMANHO_DO_TILE
        jogo.jogador.posicao = pygame.Vector2(
            coluna * lado + lado // 2, linha * lado + lado // 2
        )
        jogo.atualizar(1 / 60)
        checar("chegar na saida termina o jogo",
               isinstance(jogo.estado, main.FimDeJogo),
               f"(estado {type(jogo.estado).__name__})")

    # --- entrando em combate ----------------------------------------
    print("\nCombate")
    jogo = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)
    checar("comeca explorando", isinstance(jogo.estado, main.Exploracao))

    # Bater num inimigo abre o combate. E o tile tem que sumir do mapa
    # ANTES: se voltasse com o tile la, o jogador entraria em combate de
    # novo no mesmo quadro.
    inimigos = jogo.mapa.inimigos()
    checar("o mapa tem inimigo", len(inimigos) > 0, f"({len(inimigos)})")
    if inimigos:
        coluna, linha = inimigos[0]
        lado = settings.TAMANHO_DO_TILE
        jogo.jogador.posicao = pygame.Vector2(
            coluna * lado + lado // 2, linha * lado + lado // 2
        )
        for _ in range(4):
            jogo.atualizar(1 / 60)

        checar("encostar no inimigo abre o combate",
               isinstance(jogo.estado, main.Combate),
               f"(estado {type(jogo.estado).__name__})")
        checar("o inimigo saiu do mapa",
           len(jogo.mapa.inimigos()) == len(inimigos) - 1,
               f"({len(inimigos)} -> {len(jogo.mapa.inimigos())})")

        # E a luta roda ate o fim, com o jogador atacando sempre.
        cena = jogo.estado.cena
        for _ in range(900):
            cena.atualizar(1 / 60)
            if cena.menu_aberto:
                cena.tratar_tecla(pygame.K_d)
            if cena.luta.concluida:
                break

        checar("a luta termina", cena.luta.concluida)
        checar("o heroi venceu", cena.luta.vencida)
        checar("a luta teve eventos", len(cena.luta.eventos) >= 3,
               f"({len(cena.luta.eventos)})")

    # --- pegando item -----------------------------------------------
    print("\nItem")
    jogo = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)

    itens = jogo.mapa.itens()
    checar("o mapa tem item", len(itens) > 0, f"({len(itens)})")
    if itens:
        coluna, linha = itens[0]
        lado = settings.TAMANHO_DO_TILE
        jogo.jogador.posicao = pygame.Vector2(
            coluna * lado + lado // 2, linha * lado + lado // 2
        )
        antes = len(jogo.jogador.inventario)
        jogo.atualizar(1 / 60)
        checar("pega o item", len(jogo.jogador.inventario) == antes + 1,
               f"({antes} -> {len(jogo.jogador.inventario)})")
        checar("o item sai do mapa",
               len(jogo.mapa.itens()) == len(itens) - 1,
               f"({len(itens)} -> {len(jogo.mapa.itens())})")

    # --- desenho ----------------------------------------------------
    print("\nDesenho")
    jogo = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)
    jogo.desenhar()
    cor = jogo.tela.get_at((settings.LARGURA // 2, settings.ALTURA // 2))[:3]
    checar("desenha cenario, nao preto", cor != settings.PRETO, f"({cor})")

    # --- transicoes de estado ---------------------------------------
    print("\nTransicoes")
    jogo = novo_jogo()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    jogo.atualizar(1 / 60)
    jogo.ir_para(main.Pausa)
    checar("vai para pausa", isinstance(jogo.estado, main.Pausa))

    # O ESC da pausa e tratado pelo ESTADO, e nao pelo jogo: por isso o
    # evento so passa pelo `atualizar` do estado. Chamar so o
    # `tratar_eventos` do jogo deixaria o evento na fila, e o proximo
    # `atualizar` consumiria — que e o caminho real de um jogador.
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    jogo.atualizar(1 / 60)
    checar("volta da pausa", isinstance(jogo.estado, main.Exploracao),
           f"(estado {type(jogo.estado).__name__})")

    # --- resumo ------------------------------------------------------
    print("=" * 62)
    if FALHAS:
        print(f"{len(FALHAS)} verificacao(oes) falharam:")
        for f in FALHAS:
            print(f"  - {f}")
        return 1

    print("tudo certo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_teste())
