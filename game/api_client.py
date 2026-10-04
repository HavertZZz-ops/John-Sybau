"""Cliente HTTP do jogo: fala com o backend Django.

Toda a conversa com o servidor passa por aqui. O resto do jogo nao
importa `requests` — ele chama este modulo. Isso e o que permite trocar
a base da URL (ou o transporte inteiro) num lugar so, e o que impede
`requests` de se espalhar pelo codigo como um-import-por-arquivo.

Duas regras que valem mais que o resto do arquivo:

**1. O jogo nunca trava porque a rede falhou.**
O backend e uma planilha com pontuacao. Perder a pontuacao de uma
partida e um contratempo; o jogo fechar sozinho, no meio de uma briga,
e um defeito. Toda chamada aqui tem prazo de expiracao e devolve um
resultado controlado na falha. O jogo pergunta "conseguiu?" e segue
jogando de qualquer jeito.

**2. O backend nao decide o que o jogo faz.**
Gravar pontuacao e o cliente pedir; ler o ranking e o cliente mostrar.
Se o servidor estiver fora do ar, o ranking simplesmente mostra "nao
foi possivel carregar" e o jogo continua. Nao ha tela de erro que
interrompe a partida.

Exemplo:

    from api_client import Cliente

    cliente = Cliente()
    resultado = cliente.registrar_partida(
        nome="John", tempo=431, inimigos_derrotados=12, pontuacao=8400
    )
    if resultado.ok:
        print(resultado.dados)
    else:
        print("guardado so na memoria:", resultado.erro)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests

# O endereco do backend. A porta 8000 e a padrao do `runserver`.
#
# Este valor aqui e o do DESENVOLVIMENTO. Num jogo distribuido, o
# endereco muda por maquina e nao pode estar fixo no codigo — mas
# para um projeto academico, com jogo e backend na mesma maquina, fixo
# funciona e evita uma tela de configuracao que ninguem usaria.
ENDERECO_BASE = "http://127.0.0.1:8000"

# Quanto tempo esperar por resposta, em segundos.
#
# Este numero precisa ser CURTO. Um `requests` sem prazo espera o
# servidor demorar para sempre; se o servidor esta parado, o jogador
# fica olhando uma tela congelada e nao sabe se o jogo travou ou a rede.
# Com 3 segundos, o pior caso e o jogo avisar "nao gravou" e seguir.
TEMPO_LIMITE = 3.0

# Quantas vezes tentar antes de desistir.
#
# Uma tentativa so. Repetir em cima de um erro de rede so demora mais
# para dar a mesma resposta, e o jogador nao pode ficar esperando por
# algo que nao vai acontecer. Uma unica tentativa com prazo curto tem o
# mesmo efeito em uma fraccao do tempo.
TENTATIVAS = 1


@dataclass
class Resultado:
    """O que aconteceu numa chamada. Nunca levanta excecao.

    Excecao e a forma errada de falar com a rede a partir de um jogo.
    Uma excecao nao behandada no meio do laco principal fecha o jogo;
    um valor de retorno com `ok = False` deixa quem chamou decidir, e o
    jogo decide continuar.
    """

    ok: bool
    # o que veio do servidor, ja convertido. None quando a chamada falhou
    dados: object | None = None
    # o motivo da falha, em palavras. None quando deu certo
    erro: str | None = None
    # o codigo HTTP, quando o servidor respondeu (mesmo com erro)
    status: int | None = None


class Cliente:
    """Fala com o backend.

    A sessao `requests` e criada uma vez e reaproveitada. Criar uma
    sessao por chamada descarta a conexao keep-alive a cada vez, e o
    jogo conversa com o servidor no fim de cada partida — nao thousands
    de vezes por segundo, mas o costume certo nao custa nada.
    """

    def __init__(self, endereco: str = ENDERECO_BASE) -> None:
        self.endereco = endereco.rstrip("/")
        self._sessao = requests.Session()
        # `headers` da sessao, e nao de cada chamada: sao sempre os
        # mesmos, e repetir a cada pedido e desperdicio.
        self._sessao.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    def fechar(self) -> None:
        """Libera a conexao. Chamar ao sair do jogo."""
        self._sessao.close()

    # --- chamadas -----------------------------------------------------

    def registrar_partida(
        self,
        nome: str,
        tempo: int,
        inimigos_derrotados: int,
        pontuacao: int,
    ) -> Resultado:
        """Grava uma partida terminada.

        `tempo` e em segundos, inteiro — o mesmo que o backend espera. O
        cliente converte os tipos aqui, e nao o jogo: assim o resto do
        jogo nunca precisa saber em que unidade o dado sai.
        """
        corpo = {
            "nome": nome,
            "tempo": int(tempo),
            "inimigos_derrotados": int(inimigos_derrotados),
            "pontuacao": int(pontuacao),
        }
        return self._postar("/api/ranking/registrar/", corpo)

    def buscar_ranking(self, limite: int = 20) -> Resultado:
        """Le o ranking. `limite` e quantas linhas trazer."""
        return self._getar(f"/api/ranking/?limite={int(limite)}")

    def esta_online(self) -> bool:
        """O backend responde? Para o menu poder avisar antes de tentar.

        Esta chamada e a unica que faz sentido perguntar "esta de pe":
        ela nao tenta gravar nada, so pergunta. Se demorar, o prazo curto
        de 3s ja resolve.
        """
        resultado = self._getar("/api/ranking/?limite=1")
        return resultado.ok

    # --- o motor das chamadas -----------------------------------------

    def _getar(self, caminho: str) -> Resultado:
        url = f"{self.endereco}{caminho}"
        try:
            resposta = self._sessao.get(url, timeout=TEMPO_LIMITE)
        except requests.exceptions.RequestException as erro:
            # `RequestException` e a base de toda falha de rede do
            # requests: DNS, conexao recusada, prazo estourado, TLS.
            # Pegar a base e nao cada subclass porque o jogo nao faz
            # diferenca entre "o servidor nao respondeu" e "nao achei o
            # endereco" — nos dois casos a resposta e a mesma: seguir.
            return Resultado(ok=False, erro=f"nao foi possivel falar com o servidor: {erro}")

        return self._interpretar(resposta)

    def _postar(self, caminho: str, corpo: dict) -> Resultado:
        url = f"{self.endereco}{caminho}"
        try:
            resposta = self._sessao.post(url, json=corpo, timeout=TEMPO_LIMITE)
        except requests.exceptions.RequestException as erro:
            return Resultado(ok=False, erro=f"nao foi possivel gravar: {erro}")

        return self._interpretar(resposta)

    @staticmethod
    def _interpretar(resposta: requests.Response) -> Resultado:
        """Traduz a resposta HTTP em `Resultado`.

        Um 400 do Django nao e excecao: o servidor respondeu, so que
        dizendo que o dado estava errado. Tratar isso como falha de
        rede esconderia o erro de verdade.
        """
        status = resposta.status_code

        # O backend pode devolver HTML (uma pagina de erro do Django)
        # onde o cliente espera JSON. Ler `.json()` sem protecao levanta
        # excecao, e essa e a falha mais comum quando se aponta o cliente
        # para o endereco errado.
        try:
            dados = resposta.json()
        except ValueError:
            if 200 <= status < 300:
                # deu certo mas veio outra coisa: raro, e um resultado
                # sem dado e melhor do que uma exception
                return Resultado(ok=False, status=status,
                                 erro="o servidor respondeu sem JSON")
            return Resultado(ok=False, status=status,
                             erro=f"erro {status} do servidor")

        if not (200 <= status < 300):
            # o Django manda {"erro": "..."} nas views; se vier outra
            # coisa, mostra o status mesmo assim
            mensagem = dados.get("erro", f"erro {status}") if isinstance(dados, dict) else f"erro {status}"
            return Resultado(ok=False, status=status, erro=str(mensagem))

        return Resultado(ok=True, dados=dados, status=status)