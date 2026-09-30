"""Tira de dentro do main() as funcoes de teste que foram inseridas nele.

O padrao se repete a cada edicao: a ancora `check_native_resolution()`
e uma CHAMADA indentada dentro do main(), entao colar um `def ... -> None:`
antes dela cria um def aninhado. O def aninhado so e definido quando o
main() roda, e o `if __name__` chama o main() antes do def existir
demais, dando NameError.

Aqui: qualquer `def check_*` com indentacao de dentro de funcao vira
`def` de modulo, movido para antes do main().
"""
import ast
import pathlib
import re

P = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau\test_smoke.py")
ls = P.read_text(encoding="utf-8").splitlines()

i_main = next(i for i, l in enumerate(ls) if l.startswith("def main() -> int:"))
# fim do main(): o `if __name__`
i_fim = next(i for i in range(i_main, len(ls)) if ls[i].startswith("if __name__"))

# defs aninhados dentro do main (4 espacos, com corpo de teste)
aninhados = [
    i for i in range(i_main, i_fim)
    if re.match(r"^    def (check_\w+)\(\) -> None:", ls[i])
]
if not aninhados:
    print("nenhum def aninhado")
    raise SystemExit(0)

print("defs aninhados em main():",
      ", ".join(ls[i].strip().split("(")[0][4:] for i in aninhados))

# recorta cada bloco: do def ate a proxima linha na MESMA indentacao
blocos = []
for i in aninhados:
    fim = i_fim
    for j in range(i + 1, i_fim):
        # proxima linha com indentacao de 4 que nao seja parte do corpo
        if ls[j].startswith("    ") and not ls[j].startswith("        "):
            if ls[j].strip():
                fim = j
                break
    blocos.append([ln[4:] if ln.startswith("    ") else ln
                   for ln in ls[i:fim]])

remover = set()
for i in aninhados:
    fim = i_fim
    for j in range(i + 1, i_fim):
        if ls[j].startswith("    ") and not ls[j].startswith("        "):
            if ls[j].strip():
                fim = j
                break
    remover.update(range(i, fim))

resto = [l for k, l in enumerate(ls) if k not in remover]
i_main_novo = next(i for i, l in enumerate(resto)
                   if l.startswith("def main() -> int:"))

novo = resto[:i_main_novo]
for b in blocos:
    novo += b + [""]
novo += resto[i_main_novo:]

texto = "\n".join(novo) + "\n"
ast.parse(texto)

# agora restaura a lista de chamadas pelo gerador
P.write_text(texto, encoding="utf-8")
print(f"movidos {len(blocos)} defs para o nivel do modulo")
import subprocess
r = subprocess.run(
    ["python", str(P.parent / "tools" / "fix_test_main.py")],
    capture_output=True, text=True, cwd=str(P.parent),
)
print(r.stdout.strip())
print(r.stderr.strip()[-300:] if r.returncode else "")