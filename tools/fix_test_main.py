"""Reconstroi o corpo do main() a partir de uma lista unica de testes.

Duas edicoes anteriores quebraram essa lista (uma chamada perdeu a
indentacao, outra 函数 foi parar dentro do main). Aqui a lista fica
escrita uma vez, e o corpo e gerado a partir dela. Assim nao existe mais
lugar para uma chamada ficar faltando ou torta.
"""
import ast
import pathlib
import re

P = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau\test_smoke.py")
texto = P.read_text(encoding="utf-8")
ls = texto.splitlines()

ORDEM = [
    "check_fps",
    "check_scenes",
    "check_config_roundtrip",
    "check_resolution_filter",
    "check_internal_resolution",
    "check_hud_shows_resolution",
    "check_options_video_options",
    "check_options_layout",
    "check_options_not_lockable",
    "check_equivalent_keys",
    "check_keybindings",
    "check_bindings_persist",
    "check_native_resolution",
    "check_fullscreen_cycle",
    "check_dungeon_map",
    "check_dungeon_intro",
    "check_dungeon_collision",
    "check_dungeon_save_cycle",
    "check_save_roundtrip",
    "check_store_fallback",
    "check_menu_items",
    "check_combat_bases",
    "check_combat_batalha",
    "check_combat_cena",
    "check_dynamic_resolution_persists",
    "check_rebinding_in_options",
    "check_all_scales",
    "check_all_resolutions",
    "check_entrypoint",
]

definidas = set(re.findall(r"^def (\w+)", texto, re.M))
faltando = [n for n in ORDEM if n not in definidas]
if faltando:
    raise SystemExit(f"testes chamados mas nao definidos: {faltando}")

corpo = ["def main() -> int:",
         "    # gerado por tools/fix_test_main.py: a lista abaixo e a unica",
         "    # fonte de verdade da ordem dos testes",
         ]
for i, nome in enumerate(ORDEM):
    if i:
        corpo.append("    print()")
    corpo.append(f"    {nome}()")
corpo += [
    "    print()",
    "    print(\"tudo certo\")",
    "    return 0",
    "",
    "",
    "if __name__ == \"__main__\":",
    "    sys.exit(main())",
    "",
]

# troca do def main() ate o fim do arquivo
i_main = next(i for i, l in enumerate(ls) if l.startswith("def main() -> int:"))
novo = ls[:i_main] + corpo

texto_novo = "\n".join(novo)
ast.parse(texto_novo)
P.write_text(texto_novo, encoding="utf-8")
print(f"main() reconstruido com {len(ORDEM)} testes")
print("ordem:", " -> ".join(ORDEM[:6]), "...")