"""Cliente da API do Sprite Fusion para gerar os sprites do jogo.

A API oficial do Sprite Fusion nao tem plugin para Pygame, entao este
script faz a ponte: chama POST /generate, acompanha o stream SSE e
baixa os PNGs direto para assets/sprites/.

Uso (a chave vai no .env, nunca no codigo):

    python tools/spritefusion.py credits
    python tools/spritefusion.py list
    python tools/spritefusion.py generate --only protagonista
    python tools/spritefusion.py generate --all --size 64

Referencia: https://www.spritefusion.com/docs/pixel-art-generator/api
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import settings  # noqa: E402

API_BASE = "https://www.spritefusion.com/api/v1"

# --- os quatro personagens que o jogo espera -----------------------
# (arquivo .png, rotulo, prompt)
# size 32 ou 64: a API so aceita 16, 32 e 64.
CHARACTERS: dict[str, dict[str, object]] = {
    "protagonista": {
        "label": "Protagonista",
        "prompt": (
            "A young adventurer hero standing, facing the viewer, "
            "wearing a worn leather tunic and a travel cloak, "
            "determined expression, centered full body, simple background"
        ),
    },
    "estranho": {
        "label": "Estranho",
        "prompt": (
            "A tall hooded stranger lurking in shadow, dark cloak, "
            "pale face barely visible, mysterious and menacing, "
            "centered full body, simple background"
        ),
    },
    "mulher_misteriosa": {
        "label": "Mulher misteriosa",
        "prompt": (
            "A mysterious woman in a long elegant dress, long dark hair, "
            "holding a small lantern, enigmatic smile, "
            "centered full body, simple background"
        ),
    },
    "rei_mago": {
        "label": "Rei mago",
        "prompt": (
            "An old king mage with a long white beard, ornate royal robes, "
            "a tall wizard hat and a glowing staff, wise and regal, "
            "centered full body, simple background"
        ),
    },
}


def load_api_key() -> str:
    """Le a chave do ambiente ou do arquivo .env. Nao imprime o valor."""
    key = os.environ.get("SPRITE_FUSION_API_KEY", "").strip()
    if key:
        return key

    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "SPRITE_FUSION_API_KEY":
                return value.strip().strip('"').strip("'")

    raise SystemExit(
        "chave nao encontrada.\n"
        "Crie o arquivo .env na raiz do projeto com:\n"
        "  SPRITE_FUSION_API_KEY=sua_chave\n"
        "A chave sai de: spritefusion.com -> Account -> API keys"
    )


def _request(path: str, key: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method="POST" if data else "GET",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "john-sybau-tools",
        },
    )
    return urllib.request.urlopen(request)


def _read_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode())
        return body.get("error", {}).get("message", str(exc))
    except Exception:
        return f"HTTP {exc.code}"


def show_credits(key: str) -> int:
    """Mostra o saldo de creditos. Nao gasta nada."""
    try:
        with _request("/credits", key) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"erro ao ler creditos: {_read_error(exc)}") from None

    credits = data.get("credits", 0)
    print(f"creditos disponiveis: {credits}")
    return int(credits)


def list_assets(key: str, limit: int = 20) -> None:
    """Lista os assets ja salvos na conta."""
    try:
        with _request(f"/assets?limit={limit}", key) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"erro ao listar assets: {_read_error(exc)}") from None

    assets = data.get("assets", [])
    if not assets:
        print("nenhum asset salvo na conta")
        return

    for asset in assets:
        print(
            f"{asset.get('id', '?'):28} {asset.get('type', '?'):10} "
            f"{asset.get('width', '?')}x{asset.get('height', '?')}  "
            f"{(asset.get('prompt') or '')[:60]}"
        )


def _sse_events(response) -> Iterator[dict]:
    """Le o stream SSE e devolve cada evento JSON."""
    for raw in response:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            continue


def download(url: str, destination: Path) -> None:
    """Baixa um asset para o disco."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:
        destination.write_bytes(response.read())


def generate_one(
    key: str, name: str, spec: dict, size: int, dry_run: bool
) -> list[Path]:
    """Gera um personagem e salva as variacoes em assets/sprites/."""
    prompt = str(spec["prompt"])
    label = str(spec.get("label", name))
    print(f"\n[{label}] size={size}")
    print(f"  prompt: {prompt[:80]}...")

    if dry_run:
        print("  --dry-run: nenhuma chamada feita, nenhum credito gasto")
        return []

    payload = {"operation": "generate", "prompt": prompt, "size": size}
    saved: list[Path] = []

    try:
        response = _request("/generate", key, payload)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"  erro: {_read_error(exc)}") from None

    with response:
        for event in _sse_events(response):
            kind = event.get("type")

            if kind == "started":
                credits = event.get("credits", {})
                print(
                    f"  reservado: {credits.get('reserved', '?')} creditos, "
                    f"restam {credits.get('remaining', '?')}"
                )
            elif kind == "progress":
                print(f"  ... {event.get('message', 'gerando')}")
            elif kind == "output":
                asset = event.get("asset", {})
                index = event.get("index", 0)
                url = asset.get("assetUrl")
                if not url:
                    continue
                target = settings.SPRITES_DIR / f"{name}.png"
                if index > 0:
                    target = settings.SPRITES_DIR / f"{name}_v{index + 1}.png"
                download(url, target)
                saved.append(target)
                print(f"  salvo: {target.name}")
            elif kind == "completed":
                status = event.get("status")
                count = event.get("output_count", 0)
                remaining = event.get("credits", {}).get("remaining", "?")
                print(f"  {status}: {count} arquivo(s), restam {remaining} creditos")

    if not saved:
        print("  nenhum arquivo salvo")
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera os sprites do John Sybau com a API do Sprite Fusion"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("credits", help="mostra o saldo de creditos")
    sub.add_parser("list", help="lista os assets ja salvos na conta")

    gen = sub.add_parser("generate", help="gera os sprites dos personagens")
    gen.add_argument("--only", action="append", choices=sorted(CHARACTERS),
                     help="gera so este personagem (repetivel)")
    gen.add_argument("--all", action="store_true", help="gera os quatro")
    gen.add_argument("--size", type=int, default=32, choices=[16, 32, 64],
                     help="tamanho em pixels: 16, 32 ou 64 (padrao 32)")
    gen.add_argument("--dry-run", action="store_true",
                     help="mostra o que seria enviado sem gastar credito")

    args = parser.parse_args()

    # --dry-run so imprime o plano: nao precisa de chave
    needs_key = not (args.command == "generate" and args.dry_run)
    key = load_api_key() if needs_key else ""

    if args.command == "credits":
        show_credits(key)
        return 0

    if args.command == "list":
        list_assets(key)
        return 0

    if args.all or args.only:
        targets = sorted(CHARACTERS) if args.all else args.only
    else:
        raise SystemExit(
            "informe --all ou --only <personagem>.\n"
            f"personagens: {', '.join(sorted(CHARACTERS))}"
        )

    missing = [t for t in targets if t not in CHARACTERS]
    if missing:
        raise SystemExit(f"personagem desconhecido: {missing}")

    print("gerando:")
    for name in targets:
        print(f"  - {name} ({CHARACTERS[name]['label']})")
    print(f"\ntamanho: {args.size}x{args.size}   destino: assets/sprites/")

    total: list[Path] = []
    for name in targets:
        total += generate_one(key, name, CHARACTERS[name], args.size, args.dry_run)

    print(f"\nconcluido: {len(total)} arquivo(s) em {settings.SPRITES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
