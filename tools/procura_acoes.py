"""Procura referencias a `acoes` fora de onde a variavel existe.

A masmorra trata tecla com `self.key(event, ...)`. A estrada e a
aldeia montam um conjunto `acoes` com
`manager.input.actions_for(event)`. Um script que copiou o bloco da
aldeia para a masmorra deixou um `if "interagir" in acoes:` onde nao
existe variavel nenhuma, e o jogo so quebra quando o jogador chega
nessa linha.
"""
import ast
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")
problemas = 0

for py in sorted((RAIZ / "src").glob("*.py")):
    t = py.read_text(encoding="utf-8")
    try:
        arvore = ast.parse(t)
    except SyntaxError as exc:
        print(f"[ERRO DE SINTAXE] {py.name}: {exc}")
        problemas += 1
        continue

    # todas as atribuicoes a `acoes` no arquivo, por linha
    define = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == "acoes":
                    define.add(no.lineno)
        if isinstance(no, ast.AnnAssign):
            if isinstance(no.target, ast.Name) and no.target.id == "acoes":
                define.add(no.lineno)

    # todo uso de `acoes` que nao e a propria atribuicao
    for no in ast.walk(arvore):
        nome = None
        if isinstance(no, ast.Name) and no.id == "acoes":
            nome = no.id
        elif (isinstance(no, ast.Compare)
              and isinstance(no.left, ast.Name)
              and no.left.id == "acoes"):
            nome = no.left.id
        if nome is None:
            continue
        if isinstance(getattr(no, "ctx", None), ast.Store):
            continue
        # procura a atribuicao mais proxima acima, no mesmo bloco
        achou = False
        for linha in define:
            if linha <= no.lineno:
                achou = True
                break
        if not achou:
            print(f"[BUG] {py.name}:{no.lineno} usa `acoes` sem "
                  f"nunca ter sido definida antes")
            problemas += 1

    # funcoes que usam `acoes` mas nao a recebem como parametro nem a
    # definem: e o caso da masmorra
    for cls in [n for n in ast.walk(arvore)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        usa = any(
            isinstance(n, ast.Name) and n.id == "acoes"
            and not isinstance(getattr(n, "ctx", None), ast.Store)
            for n in ast.walk(cls)
        )
        if not usa:
            continue
        # `acoes` pode ser PARAMETRO da funcao: ai nao e bug
        parametros = {a.arg for a in cls.args.args}
        parametros |= {a.arg for a in cls.args.kwonlyargs}
        if "acoes" in parametros:
            continue
        define_dentro = {
            no.lineno for no in ast.walk(cls)
            if isinstance(no, ast.Assign)
            for alvo in no.targets
            if isinstance(alvo, ast.Name) and alvo.id == "acoes"
        }
        if not define_dentro:
            print(f"[BUG] {py.name}:{cls.lineno} {cls.name}() usa `acoes` "
                  f"sem nunca definir")
            problemas += 1

print("problemas:", problemas)
sys.exit(1 if problemas else 0)