from __future__ import annotations

import re


def parse_money(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("R$", "").replace("\xa0", " ").strip()
    text = re.sub(r"[^\d,.\-]", "", text)
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError as exc:
        raise ValueError(f"Valor monetario invalido: {value!r}") from exc


def normalize_text(text: object) -> str:
    raw = "" if text is None else str(text)
    replacements = {
        "Á": "A", "À": "A", "Â": "A", "Ã": "A", "Ä": "A",
        "É": "E", "Ê": "E", "Í": "I", "Ó": "O", "Ô": "O",
        "Õ": "O", "Ú": "U", "Ü": "U", "Ç": "C",
    }
    out = raw.strip().upper()
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return " ".join(out.split())


CATEGORIES_POSTO = [
    "PREMMIA_CARTAO",
    "PREMMIA_PIX",
    "PREMMIA_VALE",
    "PREMMIA_CUPOM",
    "FITCARD",
    "PAG_PIX",
    "AMEX",
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
    "PREMMIA_VALE": "PREMMIA VALE",
    "PREMMIA_CUPOM": "PREMMIA CUPOM",
    "FITCARD": "FITCARD",
    "PAG_PIX": "PAG PIX",
    "AMEX": "AMERICAN EXP",
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


def empty_categories_posto(keys: list[str] | None = None) -> dict[str, dict[str, float]]:
    keys = keys if keys is not None else CATEGORIES_POSTO
    return {key: {"sistema": 0.0, "site": 0.0} for key in keys}


def normalize_categories_posto(
    categorias: dict[str, dict[str, float]] | None,
    keys: list[str] | None = None,
) -> dict[str, dict[str, float]]:
    keys = keys if keys is not None else CATEGORIES_POSTO
    normalized = empty_categories_posto(keys)
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
