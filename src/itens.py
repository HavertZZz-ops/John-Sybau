"""Itens que o jogador carrega e usa na hora da luta.

Comeca com um item so, a pocao de cura, porque e a unica coisa que a
sala da pocao precisa ensinar. O formato ja e de lista, para caber
mais itens sem mexer no combate.

Um item tem cura e consome a vez. Gastar a vez e o que impede o
jogador de curar infinitamente em um turno so.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    id: str
    nome: str
    descricao: str
    cura: int = 0

    @property
    def e_cura(self) -> bool:
        return self.cura > 0


ITENS: dict[str, Item] = {
    "pocao": Item(
        id="pocao",
        nome="Pocao de cura",
        descricao="Restaura um pouco de vida.",
        cura=30,
    ),
}


def obter(item_id: str) -> Item | None:
    return ITENS.get(item_id)


def usar(item_id: str, alvo) -> int:
    """Aplica o item e devolve quanto curou (0 se nao curou nada).

    Devolver o valorcurado, e nao um booleano, permite dizer "a vida
    ja estava cheia" sem checar a vida antes e depois.
    """
    item = ITENS.get(item_id)
    if item is None or not item.e_cura:
        return 0
    return alvo.curar(item.cura)


# o que o jogador ve quando abre o inventario na luta
def rotulos(inventario: dict[str, int]) -> list[tuple[str, Item, int]]:
    """`(id, item, quantidade)`, so do que o jogador tem de verdade."""
    linhas = []
    for item_id, quantidade in sorted(inventario.items()):
        if quantidade <= 0:
            continue
        item = ITENS.get(item_id)
        if item is None:
            continue
        linhas.append((item_id, item, quantidade))
    return linhas


def tem_usaveis(inventario: dict[str, int]) -> bool:
    return any(item.e_cura for _id, item, _qtd in rotulos(inventario))