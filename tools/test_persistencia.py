"""Teste da persistencia da campanha.

O que mais some nao e o que quebra com erro: e o que simplesmente
volta ao zero sem reclamar. Um save que grava a posicao mas nao a sala
faz o jogador refazer a campanha inteira sem entender por que.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

import pygame

sys.path.insert(0, r"C:\Users\jhnnl\Music\PSOO\John-Sybau")

from src import saves  # noqa: E402
from src.progresso import CHEFE, PRIMEIRA, Progresso  # noqa: E402

FALHOU = 0


def checa(condicao: bool, mensagem: str) -> None:
    global FALHOU
    if condicao:
        print(f"[ok] {mensagem}")
    else:
        FALHOU += 1
        print(f"[FALHOU] {mensagem}")


# --- a campanha inteira dentro do Save -------------------------------
p = Progresso()
p.vencer(1)
p.vencer(2)
p.sala = 3
p.itens["pocao"] = 2
p.fugir_do_chefe()
p.sair_da_masmorra()
p.sair_da_masmorra()
p.mundo = "cidade"

s = saves.Save(area="catacumbas", x=100.0, y=200.0, extra={"progresso": p.para_extra()})
d = s.para_dict()

checa("progresso" in d["extra"], "o save carrega o progresso em extra")
checa(d["extra"]["progresso"]["sala"] == 3, "a sala vai no save")
checa(d["extra"]["progresso"]["vencidas"] == [1, 2], "as salas vencidas vao no save")
checa(d["extra"]["progresso"]["itens"] == {"pocao": 2}, "os itens vao no save")
checa(d["extra"]["progresso"]["vezes_saida"] == 2, "as saidas vao no save")
checa(d["extra"]["progresso"]["chefe_fugiu"] is True, "a fuga do chefe vai no save")

# volta pelo caminho oficial de leitura
voltou = Progresso.de_extra(saves.Save.de_dict(d).extra.get("progresso"))
checa(voltou == p, f"o progresso volta igual apos o save: {voltou} != {p}")
checa(voltou.onde_esta_o_chefe() == PRIMEIRA.numero,
      "depois de carregar, o chefe continua na primeira sala")
checa(voltou.mundo == "cidade", "o mundo aberto sobrevive ao save")

# --- ida e volta pelo arquivo de verdade ----------------------------
with tempfile.TemporaryDirectory() as pasta:
    store = saves.ArquivoSaveStore(pathlib.Path(pasta) / "save1.json")
    gravado = store.salvar(s)
    checa(gravado, "o store local aceitou o save")
    lido = store.carregar()
    checa(lido is not None, "o save foi lido de volta")
    if lido is not None:
        p2 = Progresso.de_extra((lido.extra or {}).get("progresso"))
        checa(p2 == p, "a campanha sobrevive ao arquivo em disco")
        checa(p2.itens == {"pocao": 2}, f"os itens sobreviveram: {p2.itens}")
        checa(p2.vencidas == [1, 2], f"as salas sobreviveram: {p2.vencidas}")

# --- save sem progresso nenhum nao quebra --------------------------
vazio = saves.Save.de_dict({"area": "catacumbas", "x": 1, "y": 2})
pv = Progresso.de_extra((vazio.extra or {}).get("progresso"))
checa(pv == Progresso(), "save antigo sem progresso abre um progresso novo")
checa(pv.sala == 1, "o progresso novo comeca na sala 1")
checa(not pv.ja_saiu_da_masmorra(), "o progresso novo nao diz que a masmorra foi concluida")
checa(pv.onde_esta_o_chefe() == CHEFE.numero,
      "num save novo o chefe comeca na ultima sala")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\npersistencia: tudo certo")
