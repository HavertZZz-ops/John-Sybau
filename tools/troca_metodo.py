"""Troca SO o corpo de um metodo, pelas arvores sintaticas.

Cortar metodos por busca de texto funciona ate o dia em que dois
metodos ficam vizinhos: o corte leva o seguinte junto. Este script
troca pelo intervalo exato que o `ast` calcula, e confere depois que
nenhum metodo sumiu.
"""
from __future__ import annotations

import ast
import pathlib
import sys

RAIZ = pathlib.Path(r"C:\Users\jhnnl\Music\PSOO\John-Sybau")


def metodos(caminho: pathlib.Path) -> dict[str, ast.FunctionDef]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    achados: dict[str, ast.FunctionDef] = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef):
            for filho in no.body:
                if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    achados[filho.name] = filho
    return achados


def trocar(caminho: pathlib.Path, nome: str, novo_corpo: str) -> bool:
    """Substitui o metodo `nome` por `novo_corpo`, sem tocar no resto."""
    if novo_corpo.strip() and not novo_corpo.rstrip().endswith((":", ")")):
        novo_corpo = novo_corpo.rstrip() + "\n"
    texto = caminho.read_text(encoding="utf-8")
    alvos = metodos(caminho)
    if nome not in alvos:
        raise SystemExit(f"{caminho.name}: nao tem o metodo {nome}")
    antigo = alvos[nome]
    linhas = texto.splitlines(keepends=True)
    # o intervalo vai do `def` ate a linha ANTES do proximo comando
    # do mesmo corpo de classe
    inicio = antigo.lineno - 1
    fim = len(linhas)
    for irma in ast.walk(ast.parse(texto)):
        if isinstance(irma, ast.ClassDef):
            for filho in irma.body:
                if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if filho.name != nome and filho.lineno - 1 > inicio:
                        fim = min(fim, filho.lineno - 1)
                        break
    novo_texto = "".join(linhas[:inicio]) + novo_corpo + "".join(linhas[fim:])
    ast.parse(novo_texto)
    caminho.write_text(novo_texto, encoding="utf-8")
    return True


if __name__ == "__main__":
    print("modulo de troca de metodo pronto")