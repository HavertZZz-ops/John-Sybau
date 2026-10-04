"""Teste manual do api_client contra o backend de verdade.

Este arquivo NAO faz parte do jogo. Ele existe para provar que o cliente
conversa com o Django, e roda fora do loop do pygame para que uma falha
de rede apareca como erro de verdade e nao como um jogo congelado.

    python tools/testar_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import api_client  # noqa: E402


def main() -> int:
    cliente = api_client.Cliente()

    print("=" * 60)
    print(f"falando com {cliente.endereco}")

    # --- o servidor esta de pe? -----------------------------------
    online = cliente.esta_online()
    print(f"backend online? {online}")
    if not online:
        print()
        print("O backend nao respondeu. Suba com:")
        print("    cd backend && python manage.py runserver")
        print()
        print("E mesmo assim, veja o que o cliente faz sem servidor:")
        cliente.fechar()
        return 0

    # --- gravar ----------------------------------------------------
    resultado = cliente.registrar_partida(
        nome="Teste", tempo=999, inimigos_derrotados=7, pontuacao=1234
    )
    print(f"gravar: ok={resultado.ok} status={resultado.status} {resultado.dados}")

    # dado invalido: o tempo negativo tem de ser recusado pelo backend
    ruim = cliente.registrar_partida(
        nome="", tempo=-5, inimigos_derrotados=0, pontuacao=0
    )
    print(f"dado invalido: ok={ruim.ok} status={ruim.status} erro={ruim.erro}")

    # --- ler --------------------------------------------------------
    leitura = cliente.buscar_ranking(limite=5)
    print(f"ler ranking: ok={leitura.ok} status={leitura.status}")
    if leitura.ok:
        for linha in (leitura.dados or {}).get("ranking", []):
            print(
                f"   {linha['posicao']}. {linha['nome']:12}"
                f" {linha['pontuacao']:>7} pts  {linha['tempo']:>5}s"
                f"  {linha['inimigos_derrotados']} inimigos"
            )

    # --- endereco que nao existe ------------------------------------
    errado = api_client.Cliente("http://127.0.0.1:9")
    falhou = errado.esta_online()
    print(f"endereco inexistente responde? {falhou} (esperado: False, sem crash)")
    errado.fechar()

    cliente.fechar()
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())