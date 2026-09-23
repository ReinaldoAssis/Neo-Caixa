"""
Persistencia e consulta dos descontos de 'Venda a prazo' puxados do Cloudfy.

A ferramenta Gerenciador de Descontos guarda apenas cupons do tipo
'Venda a prazo' e nunca sobrescreve registros existentes (dedupe por
data + cupom). O campo `conferido` e controlado pelo usuario.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

TABLE = "descontos"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def chave_desconto(data: str, cupom: str) -> str:
    return f"{(data or '').strip()}|{(cupom or '').strip()}"


def _doc_id(doc: dict[str, Any]) -> str:
    raw = getattr(doc, "doc_id", None)
    if raw is None:
        raw = doc.get("doc_id") or doc.get("id")
    return str(raw) if raw is not None else ""


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).replace("R$", "").replace(" ", "").strip()
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def normalize_desconto(raw: dict[str, Any]) -> dict[str, Any]:
    data = str(raw.get("data", "")).strip()
    cupom = str(raw.get("cupom", "")).strip()
    return {
        "tipo": str(raw.get("tipo", "")).strip(),
        "motivo": str(raw.get("motivo", "")).strip(),
        "data": data,
        "caixa": str(raw.get("caixa", "")).strip(),
        "cupom": cupom,
        "qtde_itens": str(raw.get("qtde_itens", "")).strip(),
        "valor": _to_float(raw.get("valor")),
        "cliente": str(raw.get("cliente") or "").strip(),
        "forma_pagamento": str(raw.get("forma_pagamento", "")).strip(),
        "chave": chave_desconto(data, cupom),
        "conferido": False,
        "criado_em": _now(),
    }


def upsert_descontos(database, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Insere somente cupons novos (dedupe por chave). Nunca sobrescreve."""
    existentes = {d.get("chave") for d in database.all(TABLE)}
    inseridos = 0
    ignorados = 0

    for raw in rows or []:
        doc = normalize_desconto(raw)
        if not doc["data"] or not doc["cupom"]:
            ignorados += 1
            continue
        if doc["chave"] in existentes:
            ignorados += 1
            continue
        database.insert(TABLE, doc)
        existentes.add(doc["chave"])
        inseridos += 1

    return {
        "inseridos": inseridos,
        "ignorados": ignorados,
        "total": len(existentes),
    }


def _date_score(data_br: str) -> tuple[int, int, int]:
    try:
        dia, mes, ano = str(data_br).split("/")
        return (int(ano), int(mes), int(dia))
    except (ValueError, TypeError):
        return (0, 0, 0)


def _sort_key(doc: dict[str, Any]) -> tuple[int, int, int, int]:
    score = _date_score(doc.get("data", ""))
    try:
        cupom = int(str(doc.get("cupom", "") or 0))
    except (ValueError, TypeError):
        cupom = 0
    return (score[0], score[1], score[2], cupom)


def list_descontos(
    database,
    data_ini: str | None = None,
    data_fim: str | None = None,
    cupom: str | None = None,
    cliente: str | None = None,
    motivo: str | None = None,
) -> list[dict[str, Any]]:
    docs = database.all(TABLE)
    cupom = (cupom or "").strip()
    cliente = (cliente or "").strip().lower()
    motivo = (motivo or "").strip().lower()
    ini = _date_score(data_ini) if data_ini else None
    fim = _date_score(data_fim) if data_fim else None

    resultado = []
    for doc in docs:
        score = _date_score(doc.get("data", ""))
        if ini and score < ini:
            continue
        if fim and score > fim:
            continue
        if cupom and cupom not in str(doc.get("cupom", "")):
            continue
        if cliente and cliente not in str(doc.get("cliente", "")).lower():
            continue
        if motivo and motivo not in str(doc.get("motivo", "")).lower():
            continue
        resultado.append(doc)

    resultado.sort(key=_sort_key, reverse=True)
    return [dict(doc, _id=_doc_id(doc)) for doc in resultado]


def toggle_conferido(database, doc_id: str) -> dict[str, Any] | None:
    doc = database.get(TABLE, doc_id)
    if not doc:
        return None
    doc["conferido"] = not bool(doc.get("conferido"))
    doc["atualizado_em"] = _now()
    database.update(TABLE, doc_id, doc)
    return dict(doc, _id=_doc_id(doc))
