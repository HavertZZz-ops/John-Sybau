"""Testes do progresso da campanha.

O que importa aqui nao e o desenho: e a REGRA do chefe. Ela depende de
duas condicoes que o jogador controla em ordem, e uma delas e facil de
inverter sem o jogo reclamar.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.progresso import (  # noqa: E402
    CHEFE,
    PRIMEIRA,
    SAIDA,
    SALAS,
    Progresso,
)

FALHOU = 0


def checa(condicao: bool, mensagem: str) -> None:
    global FALHOU
    if condicao:
        print(f"[ok] {mensagem}")
    else:
        FALHOU += 1
        print(f"[FALHOU] {mensagem}")


# --- a sequencia de salas --------------------------------------------
checa(len(SALAS) == 5, f"a masmorra tem 5 salas, tem {len(SALAS)}")
checa([s.numero for s in SALAS] == [1, 2, 3, 4, 5], "as salas vao de 1 a 5")
mecanicas = [s.mecanica for s in SALAS]
checa(
    mecanicas == ["ataque", "defesa", "habilidade", "item", "fuga"],
    f"a ordem das mecanicas e ataque, defesa, habilidade, item, fuga; veio {mecanicas}",
)
checa(SALAS[0].fracos, "a primeira sala tem inimigo fraco")
checa(SALAS[0].fracos is True and all(not s.fracos for s in SALAS[1:]),
      "so a primeira sala tem inimigo fraco")
checa(SALAS[-1].tem_boss, "a ultima sala tem o chefe")
checa(sum(1 for s in SALAS if s.tem_boss) == 1, "so uma sala tem chefe")
checa(all(s.dica for s in SALAS), "toda sala tem a frase que ensina")

# --- o jogador avanca de sala em sala --------------------------------
p = Progresso()
checa(p.sala == 1, "comeca na sala 1")
checa(p.sala_atual() is SALAS[0], "sala_atual devolve a primeira")
checa(not p.concluida(1), "nada vencido no comeco")

p.vencer(1)
checa(p.avancar() == 2, "depois de vencer a 1, vai para a 2")
p.vencer(2)
checa(p.avancar() == 3, "depois de vencer a 2, vai para a 3")
checa(p.concluida(1) and p.concluida(2), "as salas vencidas ficam marcadas")
checa(not p.concluida(3), "a 3 ainda nao esta vencida")

# vencer duas vezes nao duplica
p.vencer(2)
checa(p.vencidas == [1, 2], f"vencer duas vezes nao duplica: {p.vencidas}")

# com todas vencidas, fica na ultima
for s in SALAS:
    p.vencer(s.numero)
checa(p.avancar() == CHEFE.numero, "todas vencidas: para na ultima sala")

# --- a regra do chefe ------------------------------------------------
novo = Progresso()
checa(not novo.ja_saiu_da_masmorra(), "no comecao nao saiu da masmorra")
checa(novo.onde_esta_o_chefe() == CHEFE.numero,
      "sem ter completado, o chefe fica na ultima sala")

novo.fugir_do_chefe()
checa(novo.chefe_fugiu, "a fuga fica marcada")
checa(novo.onde_esta_o_chefe() == CHEFE.numero,
      "fugir SEM ter completado a masmorra nao move o chefe")

novo.sair_da_masmorra()
checa(novo.ja_saiu_da_masmorra(), "sair marca que saiu da masmorra")
checa(novo.onde_esta_o_chefe() == PRIMEIRA.numero,
      "sair depois de fugir: ai sim o chefe vai para a primeira sala")

# as DUAS condicoes. Este bloco usa um progresso novo de proposito: o
# de cima ja tinha fugido, entao nao servia para provar que completar
# sozinho nao move o chefe.
so_saiu = Progresso(vezes_saida=1)
checa(so_saiu.onde_esta_o_chefe() == CHEFE.numero,
      "so ter saido nao move o chefe: falta ter fugido")

novo.fugir_do_chefe()
checa(novo.onde_esta_o_chefe() == PRIMEIRA.numero,
      "depois de fugir E ter completado, o chefe vai para a primeira sala")

# o portao e a ordem das duas condicoes
so_fuga = Progresso(chefe_fugiu=True)
checa(so_fuga.onde_esta_o_chefe() == CHEFE.numero,
      "so ter fugido nao move o chefe: falta ter saido da masmorra")

# --- a saida e a sala 6, e vale tanto por fuga quanto por vitoria -----
checa(SAIDA == 6, "a saida da masmorra e a sala 6")

# fugir da quinta E sair: o chefe recambia para a primeira
f = Progresso()
checa(f.onde_esta_o_chefe() == CHEFE.numero, "no comecao o chefe esta na quinta")
f.fugir_do_chefe()
f.sair_da_masmorra()
checa(f.mundo == "estrada", "sair da masmorra abre a estrada")
checa(f.onde_esta_o_chefe() == PRIMEIRA.numero,
      "depois de fugir e sair, o chefe esta na primeira sala")

# vencer o chefe tambem e sair
v = Progresso()
v.vencer(5)
v.sair_da_masmorra()
checa(v.mundo == "estrada", "vencer e sair tambem abre a estrada")
checa(v.onde_esta_o_chefe() == CHEFE.numero,
      "vencer sem ter fugido deixa o chefe na quinta")

# sair sem fugir: o portao exige as DUAS coisas
s = Progresso()
s.sair_da_masmorra()
checa(s.onde_esta_o_chefe() == CHEFE.numero,
      "sair sem fugir nao move o chefe")

# --- itens -----------------------------------------------------------
i = Progresso()
checa(not i.tem_pocao(), "comeca sem pocao")
checa(not i.usar_pocao(), "usar pocao sem ter nao faz nada")
i.itens["pocao"] = 1
checa(i.tem_pocao(), "com uma pocao, tem pocao")
checa(i.usar_pocao(), "usar a pocao funciona")
checa(not i.tem_pocao(), "a pocao acabou depois de usar")
checa("pocao" not in i.itens, "a pocao sai do inventario quando zera")
checa(not i.usar_pocao(), "nao da para usar duas vezes a mesma pocao")

# --- save: ida e volta, e lixo ---------------------------------------
ida = Progresso()
ida.sala = 4
ida.vencer(1)
ida.vencer(2)
ida.fugir_do_chefe()
ida.sair_da_masmorra()
ida.sair_da_masmorra()
ida.itens["pocao"] = 2
ida.mundo = "cidade"
voltou = Progresso.de_extra(ida.para_extra())
checa(voltou == ida, f"o progresso sobrevive ao save: {voltou} != {ida}")

for bruto in [
    None, [], "lixo", 42,
    {"sala": "quatro"},
    {"sala": 99},
    {"vencidas": [1, "dois", 42]},
    {"itens": {"pocao": -3, "elixir": 0}},
    {"vezes_saida": -1},
    {"vezes_saida": "muitas"},
    {"mundo": "marte"},
]:
    r = Progresso.de_extra(bruto)
    # `vencidas` mantem o que e valido e descarta o resto: perder a
    # sala 1 e o mesmo que nunca ter passado por ela, entao o filtro
    # tem de preservar o que da para usar
    esperado_vencidas = [1] if bruto == {"vencidas": [1, "dois", 42]} else []
    ok = (
        r.sala == 1
        and r.vencidas == esperado_vencidas
        and r.itens == {}
        and r.vezes_saida == 0
        and r.mundo == "masmorra"
        and r.chefe_fugiu is False
    )
    checa(ok, f"save sujo nao derruba o jogo: {bruto!r}")

so_validos = Progresso.de_extra({"vencidas": [1, 2, 2], "sala": 3})
checa(so_validos.vencidas == [1, 2], "vencidas se limpa e ordena")
checa(so_validos.sala == 3, "sala valida passa")

if FALHOU:
    print(f"\n{FALHOU} verificacao(oes) falharam")
    sys.exit(1)
print("\nprogresso: tudo certo")
