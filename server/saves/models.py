"""Modelo do save.

Uma linha so, com o slot como chave natural. O jogo tem um slot
continuavel; a tabela ja fica pronta para varios, porque e o mesmo
modelo e muda so a consulta.
"""
from __future__ import annotations

from django.db import models


class Slot(models.Model):
    """Um ponto de continuacao do jogador."""

    # "1" e o slot do jogo. Unico por linha: dois saves no mesmo slot
    # sem querer sobrescreveriam um ao outro em silencio.
    slot = models.CharField(max_length=16, unique=True, default="1")

    # onde o jogador esta
    area = models.CharField(max_length=64, default="catacumbas")
    x = models.FloatField(default=0.0)
    y = models.FloatField(default=0.0)
    direcao = models.CharField(max_length=8, default="sul")

    # progresso
    tempo_jogado = models.FloatField(default=0.0)
    versao = models.IntegerField(default=1)

    # o resto do estado, em JSON. Guarda o que ainda nao tem coluna, para
    # o save carregar campos novos sem precisar de migration a cada vez.
    extra = models.JSONField(default=dict, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "slot de save"
        verbose_name_plural = "slots de save"
        ordering = ["-atualizado_em"]

    def __str__(self) -> str:
        return f"slot {self.slot} ({self.area})"

    def para_dict(self) -> dict:
        return {
            "area": self.area,
            "x": self.x,
            "y": self.y,
            "direcao": self.direcao,
            "tempo_jogado": self.tempo_jogado,
            "versao": self.versao,
            "extra": self.extra,
            "criado_em": self.criado_em.isoformat(),
        }