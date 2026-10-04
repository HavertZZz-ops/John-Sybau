"""Uma ferramenta para rodar TODOS os testes do projeto.

    python tools/testar_tudo.py

O que ela faz, e por que existe:

- **Roda tudo e sai com codigo de erro se algo falhar.** Cada suite ja
  devolvia 0 ou 1; esta junta. Um `&&` nao funciona no PowerShell como
  no bash, e depender disso e deixar a verificacao a cargo de quem roda.

- **Limpa o banco de teste antes.** As suites gravam linhas de teste no
  `db.sqlite3`. Rodar duas vezes seguidas dobra o numero de linhas do
  ranking, e um teste que confere contagem passa a falhar na segunda
  execucao — e a primeira execucao e sempre a que passa. Limpar antes
  deixa o resultado igual em qualquer ordem.

- **Mostra o tempo de cada suite.** A suite lenta e a que o operador
  para para olhar; sem o tempo, nao ha como saber.

O `db.sqlite3` e o arquivo de DESENVOLVIMENTO. Se alguem estiver
trabalhando com dados de verdade nele, esta ferramenta apaga. Por isso
ela avisa antes, e por isso ela nao apaga nada quando o arquivo tem
linhas que nao sejam de teste.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# As suites, na ordem em que devem rodar. A ordem importa: a do jogo
# vem primeiro porque e a mais rapida e a que mais quebra quando ha
# erro de digitacao — e o operador precisa ver o erro de digitacao
# antes de olhar qualquer outra coisa.
SUITES = (
    ("jogo: movimento e colisao", RAIZ / "game/tools/testar_player.py", RAIZ / "game"),
    ("jogo: estados e camera", RAIZ / "game/tools/testar_jogo.py", RAIZ / "game"),
    ("jogo: combate", RAIZ / "game/tools/testar_combate.py", RAIZ / "game"),
    ("backend: API e banco", RAIZ / "backend/tools/testar_backend.py", RAIZ / "backend"),
    ("cliente: API do jogo", RAIZ / "game/tools/testar_api.py", RAIZ / "game"),
)


def limpar_banco_de_teste() -> bool:
    """Apaga as linhas de teste do SQLite.

    Devolve False quando o banco tem dados que NAO sao de teste, e nesse
    caso nao apaga. Apagar o trabalho de quem esta desenvolvendo seria
    pior do que uma verificacao falhar.
    """
    caminho = RAIZ / "backend" / "db.sqlite3"
    if not caminho.is_file():
        return True

    conexao = sqlite3.connect(caminho)
    try:
        tabelas = [
            linha[0] for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
        if "ranking_ranking" not in tabelas:
            return True

        # O nome de quem gravou e a pista: as linhas de teste vem de
        # "Testador", "Teste" ou "John" do teste automatico.
        nomes = [
            linha[0] for linha in conexao.execute(
                "SELECT DISTINCT nome FROM ranking_ranking"
            )
        ]
        de_teste = {"Testador", "Teste", "John", "Contagem"}
        estranhos = [n for n in nomes if n not in de_teste]

        if estranhos:
            print(f"    banco tem linhas de: {', '.join(estranhos)}")
            print("    nao foi limpo, para nao apagar dados de verdade")
            return False

        total = conexao.execute(
            "SELECT COUNT(*) FROM ranking_ranking"
        ).fetchone()[0]
        conexao.execute("DELETE FROM ranking_ranking")
        conexao.commit()
        print(f"    {total} linha(s) de teste apagada(s)")
        return True
    finally:
        conexao.close()


def main() -> int:
    print("=" * 62)
    print("rodando todas as suites do projeto")

    limpo = limpar_banco_de_teste()
    if not limpo:
        print()
        print("AVISO: o banco nao foi limpo. As suites podem reprovar por")
        print("contagem. Rodar mesmo assim?")

    resultados: list[tuple[str, bool, float]] = []

    for nome, caminho, pasta in SUITES:
        if not caminho.is_file():
            print(f"\n[{nome}] nao encontrado em {caminho}")
            resultados.append((nome, False, 0.0))
            continue

        inicio = time.perf_counter()
        try:
            processo = subprocess.run(
                [sys.executable, str(caminho)],
                cwd=pasta,
                capture_output=True,
                text=True,
                timeout=300,
            )
            passou = processo.returncode == 0
            saida = processo.stdout
            erro = processo.stderr
        except subprocess.TimeoutExpired:
            passou = False
            saida = ""
            erro = "tempo esgotado (300s)"

        duracao = time.perf_counter() - inicio
        resultados.append((nome, passou, duracao))

        marca = "ok  " if passou else "FALHA"
        print(f"\n[{marca}] {nome}  ({duracao:.1f}s)")

        if not passou:
            # so a parte que importa: as linhas de falha. A saida
            # inteira de uma suite que passou nao diz nada.
            for linha in (erro + saida).splitlines():
                if "FALHA" in linha or "Error" in linha or "Traceback" in linha:
                    print(f"    {linha.strip()}")

    # --- resumo ------------------------------------------------------
    print()
    print("=" * 62)
    total = len(resultados)
    passaram = sum(1 for _, ok, _ in resultados if ok)

    for nome, ok, duracao in resultados:
        print(f"  {'ok  ' if ok else 'FALHA'}  {nome:32} {duracao:5.1f}s")

    print("=" * 62)
    if passaram == total:
        print(f"todas as {total} suites passaram")
        return 0

    print(f"{total - passaram} de {total} suites falharam")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())