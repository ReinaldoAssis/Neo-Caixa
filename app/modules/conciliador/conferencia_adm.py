"""Conferência do extrato CAIXA ADM x dinheiro do caixa restaurante."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.conciliador.services import total_contagens_dinheiro

TABLE = "conferencias_adm"

STATUS_BATE = "bate"
STATUS_NAO_BATE = "nao_bate"
STATUS_SEM_CAIXA = "sem_caixa"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    texto = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return round(float(texto), 2)
    except (TypeError, ValueError):
        return 0.0


def dinheiro_real_caixa(doc: dict[str, Any]) -> float:
    if doc.get("dinheiro_real") is not None:
        return _to_float(doc.get("dinheiro_real"))
    contagens = doc.get("contagens_dinheiro") or []
    ajuste = _to_float(doc.get("dinheiro_ajuste"))
    return round(total_contagens_dinheiro(contagens) + ajuste, 2)


def caixas_do_dia(database, data_iso: str) -> list[dict[str, Any]]:
    out = []
    for doc in database.all("conciliacoes"):
        if doc.get("tipo") != "restaurante":
            continue
        if str(doc.get("data", "")) != str(data_iso):
            continue
        if doc.get("status") == "arquivado":
            continue
        if doc.get("kind") == "contagem":
            continue
        out.append(doc)
    return out


def avaliar(
    database,
    data_iso: str,
    extrato: dict[str, Any],
) -> dict[str, Any]:
    caixas = caixas_do_dia(database, data_iso)
    caixa_total = round(sum(dinheiro_real_caixa(c) for c in caixas), 2)
    extrato_total = _to_float(extrato.get("total"))
    linhas = extrato.get("linhas") or []
    soma_linhas = round(sum(_to_float(item.get("valor")) for item in linhas), 2)
    diferenca = (
        round(extrato_total - caixa_total, 2) if caixas else None
    )
    inconsistencias = abs(soma_linhas - extrato_total) > 0.005

    if not caixas:
        status = STATUS_SEM_CAIXA
    elif abs(diferenca or 0) <= 0.005:
        status = STATUS_BATE
    else:
        status = STATUS_NAO_BATE

    return {
        "data": data_iso,
        "executado_em": _now(),
        "extrato_total": extrato_total,
        "extrato_total_texto": str(extrato.get("total_texto") or ""),
        "linhas": linhas,
        "soma_linhas": soma_linhas,
        "extrato_inconsistente": inconsistencias,
        "caixa_total": caixa_total,
        "caixa_qtd": len(caixas),
        "caixa_ids": [
            str(c.get("doc_id") or c.get("id") or "") for c in caixas
        ],
        "diferenca": diferenca,
        "status": status,
    }


def registrar(database, resultado: dict[str, Any]) -> dict[str, Any]:
    registro = dict(resultado)
    registro["criado_em"] = registro.get("executado_em") or _now()
    doc_id = database.insert(TABLE, registro)
    return {"id": doc_id, **registro}


def listar(database, limite: int = 20) -> list[dict[str, Any]]:
    docs = database.all(TABLE)
    docs.sort(key=lambda d: str(d.get("executado_em", "")), reverse=True)
    return docs[: max(1, int(limite or 20))]
