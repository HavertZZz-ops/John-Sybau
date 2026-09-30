"""Mapa de acoes e teclas, editavel pelo jogador.

O jogo nao le teclas cruas. Cada acao (andar para cima, confirmar,
voltar...) tem um nome, e o config.json guarda quais teclas cada acao
aceita. Assim da para remapear tudo sem mexer no codigo das cenas.

As teclas sao salvas pelo nome do pygame ("up", "return", "left
shift"), e nao pelo numero da constante. O arquivo fica legivel e
continua valendo se o pygame mudar a numeracao.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import pygame

# grupos: as acoes ficam separadas em abas na tela de opcoes
GROUP_VIDEO = "video"
GROUP_TECLAS = "teclas"

# (id da acao, rotulo, grupo, teclas padrao)
ACTION_LIST: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    ("mover_cima", "Andar para cima", GROUP_TECLAS, ("up", "w")),
    ("mover_baixo", "Andar para baixo", GROUP_TECLAS, ("down", "s")),
    ("mover_esquerda", "Andar para esquerda", GROUP_TECLAS, ("left", "a")),
    ("mover_direita", "Andar para direita", GROUP_TECLAS, ("right", "d")),
    ("girar_esquerda", "Girar heroi (esq)", GROUP_TECLAS, ("a",)),
    ("girar_direita", "Girar heroi (dir)", GROUP_TECLAS, ("d",)),
    ("confirmar", "Confirmar", GROUP_TECLAS, ("return", "space")),
    ("voltar", "Voltar / sair", GROUP_TECLAS, ("escape",)),
    ("restaurar", "Restaurar padroes", GROUP_TECLAS, ("r",)),
)

ACTION_LABELS: Dict[str, str] = {a: label for a, label, _, _ in ACTION_LIST}
ACTION_GROUPS: Dict[str, str] = {a: group for a, _, group, _ in ACTION_LIST}
DEFAULT_BINDINGS: Dict[str, Tuple[str, ...]] = {
    action: keys for action, _, _, keys in ACTION_LIST
}

# nome agradavel para mostrar na tela; o que faltar usa pygame.key.name
PRETTY: Dict[str, str] = {
    "up": "seta cima",
    "down": "seta baixo",
    "left": "seta esq",
    "right": "seta dir",
    "return": "enter",
    "space": "espaco",
    "escape": "esc",
    "shift": "shift",
    "ctrl": "ctrl",
    "alt": "alt",
    "tab": "tab",
    "backspace": "backspace",
}


def key_name(key: int) -> str:
    """Nome legivel de uma tecla, para exibir na tela."""
    name = pygame.key.name(key)
    # pygame chama as setas de "up"/"left" etc.; fica mais claro assim
    return PRETTY.get(name, name)


def key_code(name: str) -> Optional[int]:
    """Constante pygame a partir do nome, ou None se o nome nao existir.

    `key_code` depende do subsistema de teclado estar pronto. Se o jogo
    ainda nao chamou `pygame.init()` (le o config antes de abrir a
    janela), inicializa aqui para a conversao nao falhar.
    """
    if not pygame.get_init():
        pygame.init()
    try:
        return pygame.key.key_code(name)
    except (ValueError, TypeError):
        return None


def is_bindable(key: int) -> bool:
    """True se a tecla pode ser usada como comando.

    F10 e as teclas de debug do Windows sao barradas porque roubam o
    foco da janela antes de chegar no jogo.
    """
    if key in (pygame.K_F10, pygame.K_F11, pygame.K_F12):
        return False
    return key >= 0


def actions_in(group: str) -> Tuple[str, ...]:
    """Ids das acoes de um grupo, na ordem de declaracao."""
    return tuple(a for a, _, g, _ in ACTION_LIST if g == group)


class InputMap:
    """Teclas associates a cada acao.

    Uma acao pode aceitar varias teclas (ex.: seta cima e W). Todas as
    acoes tem ao menos uma tecla, garantido pela validacao: sem isso o
    jogador poderia deixar o jogo sem forma de navegar.
    """

    def __init__(self, bindings: Optional[Dict[str, List[str]]] = None) -> None:
        self._bindings: Dict[str, List[str]] = {
            action: list(keys) for action, keys in DEFAULT_BINDINGS.items()
        }
        if bindings:
            self.update(bindings)
        self._code_index: Optional[Dict[int, List[str]]] = None

    # --- leitura ---------------------------------------------------
    def keys(self, action: str) -> List[str]:
        """Nomes das teclas de uma acao."""
        return list(self._bindings.get(action, ()))

    def labels(self, action: str) -> List[str]:
        """Teclas de uma acao, prontas para desenhar."""
        return [key_name(code) if (code := key_code(k)) else k for k in self.keys(action)]

    def has(self, action: str) -> bool:
        """True se a acao tem ao menos uma tecla real.

        Um slot vazio nao conta: `clear_slot` deixa a posicao para a
        tela desenhar, mas a acao segue valendo pelas outras teclas.
        """
        return any(self._bindings.get(action, ()))

    def index(self) -> Dict[int, List[str]]:
        """Mapa de constante pygame -> acoes que ela dispara.

        Montado sob demanda e guardado, porque o laco principal chama
        isso em todo KEYDOWN e nao vale reconstruir a cada tecla.
        """
        if self._code_index is None:
            index: Dict[int, List[str]] = {}
            for action, names in self._bindings.items():
                for name in names:
                    code = key_code(name)
                    if code is not None:
                        index.setdefault(code, []).append(action)
            self._code_index = index
        return self._code_index

    def actions_for(self, key: int) -> List[str]:
        """Acoes disparadas por uma tecla."""
        return self.index().get(key, [])

    def pressed(self, key: int, action: str) -> bool:
        """True se a teclarecem pressionada pertence a acao."""
        return action in self.actions_for(key)

    def pressed_any(self, key: int, actions: Iterable[str]) -> bool:
        return any(pressed for pressed in self.actions_for(key) if pressed in tuple(actions))

    # --- escrita ---------------------------------------------------
    def assign(self, action: str, slot: int, name: str) -> None:
        """Coloca a tecla `name` numa posicao da acao.

        Mantem o tamanho da lista: trocar a tecla de W pela tecla Q nao
        faz a acao perder a segunda tecla.
        """
        if action not in self._bindings:
            return
        keys = self._bindings[action]
        while len(keys) <= slot:
            keys.append("")
        keys[slot] = name
        self._dedupe(action)
        self._invalidate()

    def clear_slot(self, action: str, slot: int) -> bool:
        """Esvazia uma posicao. False se fosse a ultima tecla da acao.

        Recusar quando seria a ultima impede o jogador de ficar sem
        forma de navegar o jogo.
        """
        keys = self._bindings.get(action)
        if not keys or slot >= len(keys):
            return False
        filled = [k for k in keys if k]
        if len(filled) <= 1:
            return False
        # esvazia o slot sem compactar: a posicao na lista e a posicao
        # desenhada na tela, entao mexer na ordem mudaria o que o
        # jogador ve depois de remover do meio
        keys[slot] = ""
        self._invalidate()
        return True

    def _dedupe(self, action: str) -> None:
        """Nao deixa a mesma tecla duas vezes na mesma acao.

        Preserva a posicao de cada slot: a tela desenha a lista na
        ordem, entao compactar aqui mudaria o desenho.
        """
        seen: set[str] = set()
        for name in self._bindings[action]:
            if not name:
                continue
            if name in seen:
                continue
            seen.add(name)

    def _invalidate(self) -> None:
        self._code_index = None

    def update(self, bindings: Dict[str, Iterable[str]]) -> None:
        """Aplica um dicionario vindo do config.json, ignorando o que nao existe."""
        for action, names in bindings.items():
            if action not in self._bindings:
                continue
            clean = [n for n in names if isinstance(n, str) and key_code(n) is not None]
            if clean:
                self._bindings[action] = clean
        self.ensure_valid()
        self._invalidate()

    def ensure_valid(self) -> None:
        """Garante que toda acao conhecida tenha ao menos uma tecla valida."""
        for action, defaults in DEFAULT_BINDINGS.items():
            keys = self._bindings.get(action, [])
            usable = [k for k in keys if k and key_code(k) is not None]
            if not usable:
                usable = [k for k in defaults if key_code(k) is not None]
            self._bindings[action] = usable or list(defaults)

    def reset(self) -> None:
        self._bindings = {a: list(k) for a, k in DEFAULT_BINDINGS.items()}
        self._invalidate()

    def reset_action(self, action: str) -> None:
        if action in DEFAULT_BINDINGS:
            self._bindings[action] = list(DEFAULT_BINDINGS[action])
            self._invalidate()

    def to_dict(self) -> Dict[str, List[str]]:
        """Mapeamento para salvar. Acoes no padrao sao omitidas."""
        out: Dict[str, List[str]] = {}
        for action, keys in self._bindings.items():
            filled = [k for k in keys if k]
            if filled and tuple(filled) != DEFAULT_BINDINGS.get(action, ()):
                out[action] = filled
        return out

    def conflicts(self, name: str) -> List[str]:
        """Outras acoes que ja usam esta tecla.

        Duplicar e permitido de proposito: "a" anda para esquerda no
        jogo e gira o heroi no menu. A tela mostra isso como aviso.
        """
        return [a for a, keys in self._bindings.items() if name in keys]

    def __repr__(self) -> str:
        return f"InputMap({self.to_dict()})"
