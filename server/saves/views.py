"""API de save, em JSON puro.

Sem Django REST Framework: a API inteira e um recurso com GET, PUT e
DELETE. Puxar uma framework inteira para quatro rotas seria levar uma
dependencia a mais para o servidor e mais um-version-para-atualizar no
seu PC.
"""
from __future__ import annotations

import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Slot

SLOT_PADRAO = "1"

# o que o cliente pode mandar, e o tipo esperado
CAMPOS = {
    "area": str,
    "x": float,
    "y": float,
    "direcao": str,
    "tempo_jogado": float,
    "versao": int,
}


def _erro(mensagem: str, codigo: int = 400) -> JsonResponse:
    return JsonResponse({"erro": mensagem}, status=codigo)


def _slot_atual() -> Slot | None:
    return Slot.objects.filter(slot=SLOT_PADRAO).first()


@csrf_exempt
def health(_request):
    """Responde vivo, para o jogo decidir se usa o banco."""
    return JsonResponse({
        "ok": True,
        "banco": "ok",
        "tem_save": Slot.objects.filter(slot=SLOT_PADRAO).exists(),
    })


@csrf_exempt
def save(request):
    """GET le o slot, PUT grava (sobrescrevendo), DELETE apaga."""
    if request.method == "GET":
        slot = _slot_atual()
        if slot is None:
            return JsonResponse({"existe": False})
        return JsonResponse({"existe": True, "save": slot.para_dict()})

    if request.method == "PUT":
        try:
            dados = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _erro(f"json invalido: {exc}")
        if not isinstance(dados, dict):
            return _erro("o corpo precisa ser um objeto json")

        # so o que o modelo conhece e numerico. Campo solto ou texto no
        # lugar de numero entra pelo coerce_field, que rejeita.
        limpo: dict = {}
        for campo, tipo in CAMPOS.items():
            if campo not in dados:
                continue
            bruto = dados[campo]
            try:
                limpo[campo] = tipo(bruto)
            except (TypeError, ValueError):
                return _erro(f"{campo} invalido: {bruto!r}")

        extra = dados.get("extra", {})
        if not isinstance(extra, dict):
            return _erro("extra precisa ser um objeto")

        slot, _criado = Slot.objects.update_or_create(
            slot=SLOT_PADRAO,
            defaults={
                "area": limpo.get("area", "catacumbas"),
                "x": limpo.get("x", 0.0),
                "y": limpo.get("y", 0.0),
                "direcao": limpo.get("direcao", "sul"),
                "tempo_jogado": limpo.get("tempo_jogado", 0.0),
                "versao": limpo.get("versao", 1),
                "extra": extra,
            },
        )
        return JsonResponse({"existe": True, "save": slot.para_dict()})

    if request.method == "DELETE":
        deletados, _ = Slot.objects.filter(slot=SLOT_PADRAO).delete()
        return JsonResponse({"existe": False, "removidos": deletados})

    return HttpResponse(
        "use GET, PUT ou DELETE",
        status=405,
        content_type="text/plain",
    )