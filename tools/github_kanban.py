"""Registra o progresso no GitHub: issues e KANBAN.md.

O board em projects/8 e um Projects cl\u00e1ssico, que n\u00e3o tem API \u2014 s\u00f3 da para
mover card na m\u00e3o. As issues, essas t\u00eam API. Este script fecha o que
foi entregue e cria o que falta.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "HavertZZz-ops/John-Sybau"
API = f"https://api.github.com/repos/{REPO}"
TOKEN = os.environ["GH_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def pedir(metodo, caminho, dados=None):
    corpo = json.dumps(dados).encode() if dados is not None else None
    req = urllib.request.Request(
        API + caminho, data=corpo, headers=HEADERS, method=metodo
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            bruto = r.read().decode()
        return json.loads(bruto) if bruto else None
    except urllib.error.HTTPError as e:
        print(f"  ERRO {metodo} {caminho}: {e.code} {e.read()[:200]}")
        return None
    except Exception as e:
        print(f"  ERRO {metodo} {caminho}: {e}")
        return None


def comentar(numero, texto):
    pedir("POST", f"/issues/{numero}/comments", {"body": texto})


def fechar(numero, texto):
    pedir("PATCH", f"/issues/{numero}", {"state": "closed"})
    comentar(numero, texto)


def criar(titulo, corpo):
    r = pedir("POST", "/issues", {"title": titulo, "body": corpo})
    if r:
        print(f"  criada #{r['number']} {titulo}")
    return r["number"] if r else None


def main():
    print("fechando o que foi entregue:")

    fechar(4, "Sprite do protagonista entregue.\n\n"
              "Vieram dos pacotes baixados (Top_Down_Adventure_Pack_v.1.0):\n"
              "`char_idle_*` e `char_run_*`, 6 quadros por direcao, nas 4\n"
              "direcoes. `tools/import_sprites.py` extrai do zip e escreve\n"
              "em `assets/sprites/hero/hero_<dir>_<idle|walk>_<n>.png`.\n\n"
              "Tambem entrou a distincao idle/walk, que antes nao existia:\n"
              "o heroi andava com a pose de passo mesmo parado.")

    entregues = [
        ("Cenario: Catacumbas com saida pelo caixao de pedra", [
            "- `src/dungeon_map.py`: 7 salas ligadas por corredores, semente fixa, com validacao de que o caixao alcanca a saida",
            "- `src/dungeon_scene.py`: camera que segue o jogador e trava nas bordas, colisao por eixo (desliza na parede)",
            "- `src/coffin.py`: sarcofago desenhado por codigo; a tampa desliza e passa NA FRENTE do heroi enquanto ele sai",
            "- `src/area_title.py`: 'Catacumbas' no alto, com o fade e o filete dourado",
            "- `tools/preview_dungeon.py`: roda a abertura e salva PNGs de cada fase",
        ]),
        ("Sistema de save com PostgreSQL via Django", [
            "- `src/saves.py`: `SaveStore` com dois lugares. Arquivo sempre funciona; Django e usado quando o servidor responde",
            "- `server/`: app Django com o modelo `Slot`, migration versionada e API JSON (GET/PUT/DELETE)",
            "- Menu com Continuar / Novo jogo, mostrando de onde vem o save",
            "- F5 salva; sair da masmorra tambem salva",
            "- `tools/setup_postgres.py` cria o banco e aplica a migration",
        ]),
        ("Menus minimalistas no estilo Dark Souls", [
            "Fundo quase preto, texto com tracking (feito caractere por caractere, porque o pygame nao tem), dourado pulsando no item selecionado, sem paineis nem bordas.",
            "FPS em uma linha no canto superior.",
        ]),
        ("Corrigir transicao de tela cheia que quebrava a resolucao", [
            "Em tela cheia nao ha moldura: a diferenca entre a janela e a superficie e o espaco da ESCALA (256x240 num 1280x720). Medida e guardada como borda, ela encolhia o filtro de resolucao a cada viagem de tela cheia.",
            "O primeiro `set_mode` depois de sair de tela cheia nao aplica o tamanho novo: a janela ficava maior que a tela, com a moldura dobrada (32x78 em vez de 16x39).",
            "`Config.clamp` exigia que a resolucao estivesse na lista estatica, entao a maior que cabia na tela era salva e descartada na abertura.",
            "As opcoes agora guardam cursor e aba quando a janela e recriada.",
        ]),
        ("Importar sprites dos pacotes baixados", [
            "6 pacotes em ~/Downloads inspecionados. Entraram: o tileset de masmorra e o personagem. O caixao de pedra e desenhado por codigo porque precisa de tampa animada.",
            "Os originais ficam fora do repositorio (licenca do autor); `tools/import_sprites.py` refaz a extracao.",
        ]),
    ]

    numeros = []
    for titulo, linhas in entregues:
        corpo = "Entregue no jogo.\n\n" + "\n".join(f"- {ln}" for ln in linhas)
        n = criar(titulo, corpo)
        if n:
            numeros.append((n, titulo))
            fechar(n, "Entregue e testado.")

    print("\nabrir o que falta:")
    faltando = [
        ("Sprites dos NPCs (mulher misteriosa, rei mago, strange)", [
            "Continua de #5, #6 e #7. Faltam os tres personagens, que agora",
            "podem sair dos pacotes ja baixados, no mesmo esquema do heroi.",
        ]),
        ("Audio: trilha e efeitos", [
            "Nenhum pacote de audio foi baixado ainda. Falta trilha por",
            "area e os sons de interface.",
        ]),
    ]
    for titulo, linhas in faltando:
        criar(titulo, "\n".join(linhas) + "\n")

    # imprime o mapa final
    print("\nissues:")
    r = pedir("GET", "/issues?state=all&per_page=100")
    if r:
        for it in sorted(
            (i for i in r if "pull_request" not in i), key=lambda i: i["number"]
        ):
            print(f"  #{it['number']:<4} [{it['state']:<6}] {it['title']}")

    return numeros


if __name__ == "__main__":
    sys.exit(0 if main() else 0)