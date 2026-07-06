from __future__ import annotations

CATEGORIES_POSTO = [
    "PREMMIA_CARTAO",
    "PREMMIA_PIX",
    "PREMMIA_CUPOM",
    "PREMMIA_VALE",
    "FITCARD",
    "PAG_PIX",
    "ELO_CREDITO",
    "ELO_DEBITO",
    "MASTERCARD_CREDITO",
    "MASTERCARD_DEBITO",
    "VISA_CREDITO",
    "VISA_DEBITO",
]

CATEGORY_LABELS_POSTO = {
    "PREMMIA_CARTAO": "PREMMIA CARTAO",
    "PREMMIA_PIX": "PREMMIA PIX",
    "PREMMIA_CUPOM": "PREMMIA CUPOM",
    "PREMMIA_VALE": "PREMMIA VALE",
    "FITCARD": "FITCARD",
    "PAG_PIX": "PAG PIX",
    "ELO_CREDITO": "ELO CREDITO",
    "ELO_DEBITO": "ELO DEBITO",
    "MASTERCARD_CREDITO": "MASTERCARD CREDITO",
    "MASTERCARD_DEBITO": "MASTERCARD DEBITO",
    "VISA_CREDITO": "VISA CREDITO",
    "VISA_DEBITO": "VISA DEBITO",
}

CATEGORIAS_RESTAURANTE = [
    "PIX",
    "ELO_DEBITO",
    "MAESTRO",
    "VC_ELECTRON",
    "AMEX",
    "ELO_CR",
    "MASTERCARD",
    "VISA",
    "DINHEIRO",
]

CATEGORIAS_RESTAURANTE_LABELS = {
    "PIX": "PIX",
    "ELO_DEBITO": "ELO DEBITO",
    "MAESTRO": "MAESTRO",
    "VC_ELECTRON": "VC ELECTRON",
    "AMEX": "AMEX",
    "ELO_CR": "ELO CR",
    "MASTERCARD": "MASTERCARD",
    "VISA": "VISA",
    "DINHEIRO": "DINHEIRO",
}

CATEGORIA_CLASSIFICACAO = {
    "PIX": "DEBITO",
    "ELO_DEBITO": "DEBITO",
    "MAESTRO": "DEBITO",
    "VC_ELECTRON": "DEBITO",
    "AMEX": "CREDITO",
    "ELO_CR": "CREDITO",
    "MASTERCARD": "CREDITO",
    "VISA": "CREDITO",
    "DINHEIRO": "DINHEIRO",
}

DENOMINATIONS = [200, 100, 50, 20, 10, 5, 2]


def empty_categories_posto() -> dict[str, dict[str, float]]:
    return {key: {"sistema": 0.0, "site": 0.0} for key in CATEGORIES_POSTO}


def normalize_categories_posto(
    categorias: dict[str, dict[str, float]] | None,
) -> dict[str, dict[str, float]]:
    normalized = empty_categories_posto()
    for key, values in (categorias or {}).items():
        if key == "CARTAO_FITCARD":
            target = "FITCARD"
        elif key in normalized:
            target = key
        else:
            continue
        normalized[target]["sistema"] = round(
            normalized[target]["sistema"] + float((values or {}).get("sistema", 0) or 0), 2
        )
        normalized[target]["site"] = round(
            normalized[target]["site"] + float((values or {}).get("site", 0) or 0), 2
        )
    return normalized


def empty_categories_restaurante() -> dict[str, dict[str, float]]:
    return {key: {"sistema": 0.0, "real": 0.0} for key in CATEGORIAS_RESTAURANTE}


def normalize_categories_restaurante(
    categorias: dict[str, dict[str, float]] | None,
) -> dict[str, dict[str, float]]:
    normalized = empty_categories_restaurante()
    for key, values in (categorias or {}).items():
        if key not in normalized:
            continue
        normalized[key]["sistema"] = round(
            normalized[key]["sistema"] + float((values or {}).get("sistema", 0) or 0), 2
        )
        normalized[key]["real"] = round(
            normalized[key]["real"] + float((values or {}).get("real", 0) or 0), 2
        )
    return normalized
