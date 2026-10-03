"""Modelo de pontuacao e de save.

Uma linha por partida terminada. A linha guarda as quatro coisas que
definem o resultado de uma partida — quem jogou, quanto tempo levou,
quantos inimigos derrubou e quantos pontos fez — e essas quatro juntas
sao o suficiente para o ranking inteiro.

Decisao de modelagem que vale registrar, porque e a que costuma ser
refeita:

**Por que um so modelo e nao dois (Ranking e Save separados).**
A primeira versao deste projeto tinha os dois, e eles guardavam os MESMOS
campos nas MESMAS linhas. O save gravava uma partida, e o ranking lia
"as ultimas partidas" da mesma tabela. Sao o mesmo dado com dois nomes.
Toda vez que um campo novo entrava no save, o ranking ficava errado sem
nenhum erro aparecer — o bug so aparecia na tela de pontuacao, semanas
depois. Um modelo, uma tabela, uma fonte da verdade.

Se um dia o save virar de verdade (o progresso do jogador em
qualquer momento, e nao so no fim da partida), ai sim sao dois: save e
ranking passam a ter ciclos de vida diferentes. A separacao aqui seria
por necessidade, e nao por organizacao.

**Por que o tempo e um inteiro e nao um `DurationField` ou string.**
O tempo de partida e uma duracao que nunca passa de algumas horas, e
so interessa em segundos. Guardar como inteiro impede dois erros de
classe: comparar string ("9:00" vs "10:00" — que ordena errado) e
converter string ("01:02:03" — que quebra em um numero). Um `IntegerField`
com o nome(SelfContained e claro sobre a unidade, e o comentario do
campo confirma.
"""
from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models


class Ranking(models.Model):
    """Uma partida terminada, com o resultado dela."""

    # --- quem jogou -------------------------------------------------

    nome = models.CharField(
        max_length=24,
        verbose_name="Nome do jogador",
        help_text="Como o jogador aparece no ranking. ate 24 caracteres.",
    )

    # --- quanto tempo levou ------------------------------------------

    # Segundos, e nao "mm:ss". Ver o comentario do modulo: a unidade
    # fica no nome do campo para ninguem ler como um numero solto.
    tempo = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Tempo (segundos)",
        help_text="Duracao da partida em segundos.",
    )

    # --- o que o jogador fez -----------------------------------------

    inimigos_derrotados = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Inimigos derrotados",
        help_text="Quantos inimigos foram derrubados na partida.",
    )

    # --- o resultado --------------------------------------------------

    pontuacao = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Pontuacao final",
        help_text="Pontos da partida, ja calculado pelo jogo.",
    )

    # --- metadados ---------------------------------------------------

    # Data e hora do registro, em UTC. `auto_now_add` preenche sozinho e
    # nao aceita valor no `create()` — passar um seria ignorado, o que
    # e melhor do que aceitar e mentir sobre quando a partida acabou.
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Registrado em",
    )

    class Meta:
        # O ranking e lido do maior para o menor SEMPRE. Deixar isso no
        # modelo, e nao em cada consulta, e o que impede o esquecimento
        # que faz a tela mostrar o ranking em ordem aleatoria e ninguem
        # entender o porque.
        ordering = ["-pontuacao", "tempo"]
        verbose_name = "Partida no ranking"
        verbose_name_plural = "Ranking"

    def __str__(self) -> str:
        """Como a linha aparece no admin do Django.

        O formato e "nome — N pontos". Nome primeiro porque e o que o
        jogador procura na tela; pontuacao porque e o numero que importa.
        """
        return f"{self.nome} — {self.pontuacao} pontos"