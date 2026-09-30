"""Importa TODAS as sprites do protagonista e da masmorra dos pacotes.

Os pacotes ficam em ~/Downloads e nao entram no repositorio: sao
originais do autor, com licenca propria. Este script extrai so o que o
jogo usa e escreve em assets/, entao da para refazer a importacao a
qualquer momento.

    python tools/import_sprites.py

Duas geometrias diferentes convivem no mesmo personagem:

  - o CORPO tem quadro de 16x16 (idle, walk, hit, death, ...)
  - o EFEITO DA ESPADA tem quadro maior: 32x32 nos cortes para cima e
    para baixo, 32x48 nos laterais. Nao e o corpo girando, e a espada
    sozinha, que e desenhada por cima do personagem durante o golpe.

O nome do arquivo diz `anim_strip_6`, mas a imagem tem 288x32 e 192x48.
Descobrir isso olhando (e conferindo com o canal alpha) evitou cortar
o efeito ao meio.
"""
from __future__ import annotations

import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOWNLOADS = Path.home() / "Downloads"
ADVENTURE_ZIP = DOWNLOADS / "Top_Down_Adventure_Pack_v.1.0.zip"
SKELETON_RAR = DOWNLOADS / "Skeletons Pack #2.rar"
OUTRA_ZIP = DOWNLOADS / "gfx.zip"
PACK = "Top_Down_Adventure_Pack_v.1.0"

TILES_DIR = ROOT / "assets" / "tiles"
HERO_DIR = ROOT / "assets" / "sprites" / "hero"
FOE_DIR = ROOT / "assets" / "sprites" / "inimigo"
RAW = ROOT / "assets" / "raw"

UPSCALE = 2

# palavra do pacote -> direcao do jogo
PALAVRA = {
    "down": "sul",
    "up": "norte",
    "left": "oeste",
    "right": "leste",
}
TODAS = ("sul", "norte", "leste", "oeste")
INVERTE = {"sul": "oeste", "oeste": "sul", "norte": "leste", "leste": "norte"}


@dataclass(frozen=True)
class Tira:
    """Uma folha do pacote e como virar quadros."""

    arquivo: str          # nome dentro do zip
    estado: str           # nome do estado no jogo
    direcao: str          # "sul", ..., ou "qualquer"
    quadros: int
    fw: int               # largura do quadro
    fh: int               # altura do quadro
    colunas: int = 0      # 0 = deduzir da propria folha

    def colunas_na_folha(self, largura: int) -> int:
        """Quantos quadros cabem numa linha desta folha.

        Todas as folhas deste pacote sao tiras horizontais (96x16 para
        6 quadros de 16px, 288x32 para 9 de 32px). Assumir uma coluna
        so faz `y = i * fh` grow cada quadro, e o importador truncava
        no quadro 1 achando que a folha nao tinha altura.
        """
        if self.colunas:
            return self.colunas
        cabe = max(1, largura // self.fw)
        return min(cabe, self.quadros)


def tiras_do_heroi() -> list[Tira]:
    lista: list[Tira] = []
    # --- corpo, 16x16, uma tira por direcao ---
    for palavra, direcao in PALAVRA.items():
        for estado, prefixo, n in (
            ("idle", "char_idle", 6),
            ("walk", "char_run", 6),
            ("pushing", "char_pushing", 6),
            ("hit", "char_hit", 3),
        ):
            lista.append(Tira(
                f"Char_Sprites/{prefixo}_{palavra}_anim_strip_{n}.png",
                estado, direcao, n, 16, 16,
            ))
        lista.append(Tira(
            f"Char_Sprites/char_shielded_static_{palavra}.png",
            "shielded", direcao, 1, 16, 16,
        ))
        lista.append(Tira(
            f"Char_Sprites/char_shielded_hit_{palavra}_anim_strip_5.png",
            "shielded_hit", direcao, 5, 16, 16,
        ))

    # --- efeito da espada: corte vertical 32x32, horizontal 32x48 ---
    for palavra, direcao in PALAVRA.items():
        vertical = direcao in ("sul", "norte")
        lista.append(Tira(
            f"Char_Sprites/char_attack_{palavra}_anim_strip_6.png",
            "attack", direcao,
            9 if vertical else 6,
            32, 32 if vertical else 48,
        ))

    # --- escalada: so para cima e para baixo ---
    for palavra, direcao in (("down", "sul"), ("up", "norte")):
        lista.append(Tira(
            f"Char_Sprites/char_climbing_{palavra}_anim_strip_6.png",
            "climbing", direcao, 6, 16, 16,
        ))

    # --- morte e queda: uma tira so, serve para qualquer direcao ---
    lista.append(Tira(
        "Char_Sprites/char_death_all_dir_anim_strip_10.png",
        "death", "qualquer", 10, 16, 16,
    ))
    lista.append(Tira(
        "Char_Sprites/char_falling_all_dir_anim_strip_6.png",
        "falling", "qualquer", 6, 16, 16,
    ))
    return lista



def extrair_gfx(caminho_zip: Path) -> None:
    """Pega um arquivo solto de um zip, se ainda nao estiver no disco."""
    destino = RAW / caminho_zip.stem / caminho_zip.name
    if destino.is_file():
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(caminho_zip) as zf:
        for nome in zf.namelist():
            if nome.endswith(caminho_zip.name):
                destino.write_bytes(zf.read(nome))
                print(f"  extraido: {destino.name}")
                return

def extrair(caminhos: dict[str, Path]) -> None:
    if not ADVENTURE_ZIP.is_file():
        raise SystemExit(
            f"pacote nao encontrado: {ADVENTURE_ZIP}\n"
            "baixe o Top_Down_Adventure_Pack_v.1.0.zip para ~/Downloads"
        )
    faltando = [n for n, p in caminhos.items() if not p.is_file()]
    if not faltando:
        return
    with zipfile.ZipFile(ADVENTURE_ZIP) as zf:
        nomes = set(zf.namelist())
        for nome in faltando:
            chave = f"{PACK}/{nome}"
            if chave not in nomes:
                print(f"  AUSENTE no pacote: {nome}")
                continue
            saida = caminhos[nome]
            saida.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(chave) as src, saida.open("wb") as dst:
                dst.write(src.read())
            print(f"  extraido: {saida.name}")


def escrever_com_nome(tira: Tira, origem: Path, destino: Path) -> int:
    """Quebra a folha em PNGs individuais, dobrados."""
    import pygame

    pygame.init()
    pygame.display.set_mode((8, 8))
    # O pygame e inicializado e DESLIGADO dentro desta funcao. O quit
    # precisa acontecer DEPOIS do laco, nunca logo apos carregar: ao
    # sair, as surfaces do pygame perdem a memoria de video e passam a
    # devolver dimensao invalida. Com o quit antes do laco, a folha
    # media 0 de largura e o importador truncava tudo no quadro 1.
    try:
        folha = pygame.image.load(origem).convert_alpha()

        destino.mkdir(parents=True, exist_ok=True)
        # limpa so os quadros deste estado NESTA direcao. Um glob largo
        # (`*hit_*.png`) tambem pegava `hero_sul_shielded_hit_0.png` e
        # apagava o estado de todas as direcoes, porque a importacao
        # passa direcao por direcao
        padrao = (
            f"hero_{tira.estado}_*.png"
            if tira.direcao == "qualquer"
            else f"hero_{tira.direcao}_{tira.estado}_*.png"
        )
        for velho in destino.glob(padrao):
            velho.unlink(missing_ok=True)

        written = 0
        largura, altura = folha.get_size()
        colunas = tira.colunas_na_folha(largura)
        for i in range(tira.quadros):
            x = (i % colunas) * tira.fw
            y = (i // colunas) * tira.fh
            if x + tira.fw > largura or y + tira.fh > altura:
                print(
                    f"  TRUNCADO {tira.estado}/{tira.direcao} no quadro {i}: "
                    f"cabe {largura // tira.fw}x{altura // tira.fh} "
                    f"na folha {largura}x{altura}"
                )
                break
            pedaco = folha.subsurface(pygame.Rect(x, y, tira.fw, tira.fh))
            grande = pygame.transform.scale(
                pedaco, (tira.fw * UPSCALE, tira.fh * UPSCALE)
            )
            pygame.image.save(grande, destino / f"{nome_de(tira, i)}.png")
            written += 1
        return written
    finally:
        pygame.quit()


def nome_de(tira: Tira, i: int) -> str:
    """Nome do arquivo do quadro `i` desta tira."""
    if tira.direcao == "qualquer":
        return f"hero_{tira.estado}_{i}"
    return f"hero_{tira.direcao}_{tira.estado}_{i}"


def nome_arma(caminho: Path) -> str:
    """'Two-Handed Sword-Sheet-NoOutline.png' -> 'duas_maos_espada'."""
    base = caminho.stem.replace("-Sheet-NoOutline", "")
    partes = base.replace("Two-Handed", "duas_maos").replace("-", "_")
    partes = partes.replace(" ", "_").lower()
    return partes


def importar_armas(alvo: Path) -> int:
    """Copia as folhas de arma inteiras para assets/sprites/arma.

    Nao da para quebrar em quadros sem olhar cada uma: espada, arco e
    escudo tem dimensoes e quantidade de angulos diferentes, e um
    espaco de16x16 fixo cortaria metade fora. A folha vai crua, e quem
    usar depois escolhe o recorte.
    """
    import pygame

    pygame.init()
    pygame.display.set_mode((8, 8))
    destino = ROOT / "assets" / "sprites" / "arma"
    destino.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        for folha in sorted(alvo.rglob("*Sheet-NoOutline.png")):
            if folha.stem.startswith("Skeleton_"):
                continue
            img = pygame.image.load(folha).convert_alpha()
            pygame.image.save(img, destino / f"{nome_arma(folha)}.png")
            total += 1
    finally:
        pygame.quit()
    return total


def _recortar_e_centralizar(quadros: list) -> list:
    """Centraliza cada quadro numa tela do tamanho da arte maior.

    Tres coisas estavam erradas na folha do esqueleto, e as tres so
    aparecem olhando o resultado, nao o codigo:

    1. o desenho fica encostado num canto da celula, nao centrado
    2. a arte anda na horizontal de um quadro para o outro
    3. o quadro tem altura de sobra acima da cabeca

    Cada quadro e recortado pela propria arte e colado no centro de uma
    tela do tamanho da maior arte, apoiado pela BASE. Alinhar pela base
    e o que mantem o pe no chao; centralizar em X tira o vaivem. O
    tamanho da tela vem da uniao, senao a animacao encolhe a cada
    quadro e o esqueleto treme.
    """
    import pygame

    if not quadros:
        return quadros

    areas = []
    for img in quadros:
        r = img.get_bounding_rect()
        areas.append(r if r and r.width and r.height else pygame.Rect(0, 0, 1, 1))

    largura = max(r.width for r in areas)
    altura = max(r.height for r in areas)

    saida = []
    for img, r in zip(quadros, areas):
        recorte = img.subsurface(r).copy()
        tela = pygame.Surface((largura, altura), pygame.SRCALPHA)
        # base apoiada, eixo X centrado
        tela.blit(recorte, ((largura - r.width) // 2, altura - r.height))
        saida.append(tela)
    return saida


def _normalizar_esqueleto(quadros: list, alvo_altura: int) -> list:
    """Redimensiona o esqueleto para a altura do corpo do heroi.

    A arte deste pacote e um esqueleto muito MAGRO: 6 pixels de largura
    por 21 de altura dentro de uma celula de 16x32. Medido no alpha, nao
    e falha de recorte. O problema e de proporcao: o heroi tem 32x32 na
    referencia 1x, entao o esqueleto saia com 6 de largura contra 32 do
    jogador e virava um palito na tela.

    O alvo e DIVIDIDO pelo UPSCALE de proposito. A importacao ja
    multiplica tudo por 2 antes de gravar, e o jogo multiplica de novo
    pela escala das opcoes. Normalizar para 32 aqui produzia 64 no disco
    e 192 na tela, o dobro do heroi: o esqueleto ficava maior que o
    jogador. O certo e que o arquivo no disco tenha a MESMA altura do
    heroi, 32.
    """
    import pygame

    if not quadros:
        return quadros
    altura = max(q.get_height() for q in quadros)
    if altura <= 0 or altura == alvo_altura:
        return quadros

    fator = alvo_altura / altura
    saida = []
    for q in quadros:
        largura = max(1, int(round(q.get_width() * fator)))
        alt = max(1, int(round(q.get_height() * fator)))
        saida.append(pygame.transform.scale(q, (largura, alt)))
    return saida


def importar_npcs() -> int:
    """Importa o NPC de corpo cheio, que le melhor que o esqueleto.

    O esqueleto do Skeletons Pack e fino demais: medido no alpha, a arte
    tem 6px de largura por 21 de altura dentro de uma celula de 16x32.
    Mesmo normalizado para a altura do heroi, ele sai com 30px de
    largura contra 96 do jogador e continua lendo como um palito.

    O `NPC_test` do pacote gfx e uma criatura de osso com corpo de
    verdade: bracos, pernas e sombra, em celulas de 16x32 numa grade de
    4 colunas por 4 linhas (4 quadros por direcao). Normalizado, sai
    com 56px de largura na escala 3x, quase o dobro do esqueleto, e
    continua sendo um osso.
    """
    import pygame

    pygame.init()
    pygame.display.set_mode((8, 8))
    destino = FOE_DIR / "ghoul"
    destino.mkdir(parents=True, exist_ok=True)
    # limpa a versao anterior
    for velho in destino.glob("*.png"):
        velho.unlink(missing_ok=True)

    try:
        bruto = RAW / "gfx" / "NPC_test.png"
        if not bruto.is_file():
            print("  NPC_test.png ausente; extraindo do pacote gfx")
            extrair_gfx(OUTRA_ZIP)
            bruto = RAW / "gfx" / "NPC_test.png"
        if not bruto.is_file():
            print("  NPC_test.png nao encontrado")
            return 0

        folha = pygame.image.load(bruto).convert_alpha()
    except (pygame.error, OSError) as exc:
        print(f"  falha ao abrir NPC_test.png: {exc}")
        return 0
    finally:
        pygame.quit()

    FW, FH = 16, 32
    ORDEM = ("sul", "oeste", "norte", "leste")
    total = 0
    for linha, direcao in enumerate(ORDEM):
        for i in range(4):
            x, y = i * FW, linha * FH
            if x + FW > folha.get_width() or y + FH > folha.get_height():
                break
            quadro = folha.subsurface(pygame.Rect(x, y, FW, FH)).copy()
            quadros = _recortar_e_centralizar([quadro])
            quadros = _normalizar_esqueleto(quadros, 32 // UPSCALE)
            for est, img in zip(("walk",), quadros):
                grande = pygame.transform.scale(
                    img, (img.get_width() * UPSCALE, img.get_height() * UPSCALE)
                )
                pygame.image.save(grande, destino / f"ghoul_{direcao}_{est}_{i}.png")
                total += 1
    return total


def importar_squeletos() -> int:
    """Extrai as folhas de esqueleto do .rar e quebra por direcao.

    A folha do esqueleto e 192x256 com esqueleto de 16x32, e nao uma
    grade uniforme: sao 4 blocos de 4 linhas, um por direcao, e dentro
    de cada bloco a primeira dupla de linhas e o ciclo de andar (8
    quadros) e a segunda e o ataque (12). Descoberto medindo o canal
    alpha, nao pelo nome do arquivo.
    """
    unrar = Path(r"C:\Program Files\WinRAR\UnRAR.exe")
    sete = Path(r"C:\Program Files\7-Zip\7z.exe")
    if not SKELETON_RAR.is_file():
        print("  Skeletons Pack #2.rar nao encontrado em ~/Downloads")
        return 0

    alvo = RAW / "skeletons"
    brutos = sorted(alvo.rglob("Skeleton_*-Sheet-NoOutline.png"))
    if not brutos:
        alvo.mkdir(parents=True, exist_ok=True)
        if unrar.is_file():
            import subprocess
            # sem o -o: nessa maquina o UnRAR aceita o comando, diz
            # "Tudo OK" e nao escreve nada. Extrair com o diretorio de
            # trabalho apontando para a pasta resolve
            subprocess.run(
                [str(unrar), "x", "-y", str(SKELETON_RAR)],
                cwd=alvo, capture_output=True, text=True, timeout=180,
            )
        elif sete.is_file():
            import subprocess
            subprocess.run(
                [str(sete), "x", "-y", str(SKELETON_RAR)],
                cwd=alvo, capture_output=True, text=True, timeout=180,
            )
        else:
            print("  sem UnRAR/7z para abrir o .rar")
            return 0
        brutos = sorted(alvo.rglob("Skeleton_*-Sheet-NoOutline.png"))

    if not brutos:
        print("  nenhuma folha de esqueleto encontrada")
        return 0

    importar_armas(alvo)

    import pygame
    pygame.init()
    pygame.display.set_mode((8, 8))
    FOE_DIR.mkdir(parents=True, exist_ok=True)
    # ordem das linhas na folha, de cima para baixo
    ORDEM = ("sul", "norte", "oeste", "leste")
    FW, FH = 16, 32
    total = 0
    try:
        for bruto in brutos:
            folha = pygame.image.load(bruto).convert_alpha()
            nome = bruto.stem.split("-")[0].lower()  # Skeleton_5 -> skeleton_5
            for bloco, direcao in enumerate(ORDEM):
                # cada direcao ocupa 2 linhas de quadro: uma de andar
                # (8 quadros) e uma de ataque (12). Sao 8 linhas no
                # total, e nao 16: a folha tem 256px de altura e cada
                # linha de quadro e 32px. Tratar como 4 linhas por
                # direcao importava so as duas primeiras direcoes.
                topo = bloco * 2 * FH
                if topo + 2 * FH > folha.get_height():
                    break
                for estado, faixa, n in (
                    ("walk", topo, 8),
                    ("attack", topo + FH, 12),
                ):
                    if faixa + FH > folha.get_height():
                        break
                    quadros = []
                    for i in range(n):
                        x = i * FW
                        if x + FW > folha.get_width():
                            break
                        quadros.append(
                            folha.subsurface(
                                pygame.Rect(x, faixa, FW, FH)
                            ).copy()
                        )
                    if not quadros:
                        continue
                    quadros = _recortar_e_centralizar(quadros)
                    # a arte deste pacote e um esqueleto esguio de 6x21;
                    # sem isso ele sai menor que a propria cabeca do
                    # jogador e vira um palito na tela
                    quadros = _normalizar_esqueleto(quadros, 32 // UPSCALE)
                    for i, quadro in enumerate(quadros):
                        grande = pygame.transform.scale(
                            quadro,
                            (quadro.get_width() * UPSCALE,
                             quadro.get_height() * UPSCALE),
                        )
                        pygame.image.save(
                            grande,
                            FOE_DIR / f"{nome}_{direcao}_{estado}_{i}.png",
                        )
                        total += 1
    finally:
        pygame.quit()
    return total


def main() -> int:
    print("extraindo do zip do personagem:")
    tiras = tiras_do_heroi()
    extrair({t.arquivo: RAW / Path(t.arquivo).name for t in tiras})

    print("\nmeu conteudo do tileset:")
    extrair({"Dungeon_Tileset.png": RAW / "Dungeon_Tileset.png"})
    destino = TILES_DIR / "dungeon_tileset.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes((RAW / "Dungeon_Tileset.png").read_bytes())
    print(f"  {destino.relative_to(ROOT)}")

    print("\nescrevendo as animacoes do heroi:")
    por_estado: dict[str, int] = {}
    for tira in tiras:
        origem = RAW / Path(tira.arquivo).name
        if not origem.is_file():
            print(f"  PULADO (ausente): {tira.arquivo}")
            continue
        n = escrever_com_nome(tira, origem, HERO_DIR)
        por_estado[tira.estado] = por_estado.get(tira.estado, 0) + n
    for estado, n in sorted(por_estado.items()):
        print(f"  {estado:14} {n:3} quadros")

    print("\nesquelecos (inimigos):")
    print(chr(10) + "npcs (inimigo principal):")
    total = importar_npcs()
    if total:
        print(f"  {total} quadros do ghoul")
    print()

    total = importar_squeletos()
    if total:
        print(f"  {total} quadros de esqueleto em "
              f"{FOE_DIR.relative_to(ROOT)}")

    print("\npronto. rode tools/anotar_tileset.py para ver os tiles com indice")
    return 0



if __name__ == "__main__":
    sys.exit(main())
