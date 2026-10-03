"""Registro do model no admin do Django.

O admin sozinho ja resolve o lado humano do projeto: da para criar um
usuario, ver o ranking inteiro e conferir se a API gravou o que deveria,
sem escrever uma linha de codigo.

O que este arquivo faz e dizer ao admin como mostrar cada campo. A
diferencia entre a lista padrao e a de abaixo nao e decorativa: a lista
padrao mostra os campos na ordem em que foram declarados no model, que
aqui e "nome, tempo, inimigos, pontuacao" — e quem abre a tela para
conferir o resultado de uma partida quer ver a pontuacao primeiro, e
o tempo em segundo.
"""
from __future__ import annotations

from django.contrib import admin

from .models import Ranking


@admin.register(Ranking)
class RankingAdmin(admin.ModelAdmin):
    """Tela de administracao do ranking."""

    # Colunas da listagem, na ordem em que aparecem. `posicao` nao e um
    # campo do banco: e a posicao no ranking, e ela e util demais para
    # nao ter.
    list_display = ("posicao", "nome", "pontuacao", "tempo",
                    "inimigos_derrotados", "criado_em")

    # Campos pelos quais se pode filtrar. `criado_em` ganha um filtro de
    # data de graca so por estar no `list_filter`.
    list_filter = ("criado_em",)

    # Busca por texto nos campos marcados. Um ranking de milhares de
    # linhas sem busca e uma tabela para rolar com o mouse.
    search_fields = ("nome",)

    # Ordena a listagem do mais novo para o mais antigo. O
    # `Meta.ordering` do model (maior pontuacao primeiro) e melhor para
    # o RANKING; no admin, o mais recente primeiro e melhor para
    # "o que aconteceu por ultimo".
    ordering = ("-criado_em",)

    # Campo de leitura apenas. `posicao` e calculado na listagem e nao
    # existe no banco, entao aparece como texto.
    readonly_fields = ("posicao",)

    @admin.display(description="Posicao")
    def posicao(self, objeto: Ranking) -> int:
        """A posicao do jogador no ranking geral (1 = primeiro).

        "Quantas linhas tem pontuacao MAIOR que a minha" e a definicao de
        estar acima de alguem, entao a posicao e essa contagem mais um.
        Em empate, quem entra antes conta como acima — o desempate do
        model e por tempo, e este metodo nao repete essa regra porque o
        admin so precisa de uma leitura aproximada.
        """
        return Ranking.objects.filter(pontuacao__gt=objeto.pontuacao).count() + 1