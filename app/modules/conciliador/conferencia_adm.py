"""Conferência do extrato CAIXA ADM x dinheiro em espécie do caixa restaurante."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.conciliador.constants import parse_money
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


def moedas_caixa(doc: dict[str, Any]) -> float:
    """Total de moedas da contagem (dinheiro que nao e cedula)."""
    if doc.get("dinheiro_moedas") is not None:
        return _to_float(doc.get("dinheiro_moedas"))
    contagens = doc.get("contagens_dinheiro") or []
    return round(
        sum(
            parse_money(c.get("moedas", 0))
            for c in contagens
            if c.get("label") == "Geral"
        ),
        2,
    )


def dinheiro_especie_caixa(doc: dict[str, Any]) -> float:
    """Dinheiro em especie do caixa: cedulas contadas, sem moedas.

    A conferencia ADM compara o extrato com o dinheiro em especie. O valor
    vem das contagens (cedulas); moedas e notas de despesa (`dinheiro_ajuste`)
    ficam de fora.
    """
    contagens = doc.get("contagens_dinheiro") or []
    if contagens:
        moedas = round(
            sum(
                parse_money(c.get("moedas", 0))
                for c in contagens
                if c.get("label") == "Geral"
            ),
            2,
        )
        return round(total_contagens_dinheiro(contagens) - moedas, 2)
    if doc.get("dinheiro_notas") is not None:
        return _to_float(doc.get("dinheiro_notas"))
    return round(dinheiro_real_caixa(doc) - moedas_caixa(doc), 2)


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


def resumo_caixa(database, data_iso: str) -> dict[str, Any]:
    caixas = caixas_do_dia(database, data_iso)
    return {
        "caixa_total": round(
            sum(dinheiro_especie_caixa(c) for c in caixas), 2
        ),
        "caixa_moedas": round(sum(moedas_caixa(c) for c in caixas), 2),
        "caixa_qtd": len(caixas),
        "caixa_ids": [
            str(c.get("doc_id") or c.get("id") or "") for c in caixas
        ],
    }


def _indices_selecionados(linhas: list, selecionadas: list | None) -> list[int]:
    indices: list[int] = []
    for raw in selecionadas or []:
        try:
            indice = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= indice < len(linhas) and indice not in indices:
            indices.append(indice)
    return indices


def avaliar(
    database,
    data_iso: str,
    extrato: dict[str, Any],
    modo: str = "completo",
    selecionadas: list | None = None,
) -> dict[str, Any]:
    resumo = resumo_caixa(database, data_iso)
    caixa_total = resumo["caixa_total"]
    caixa_moedas = resumo["caixa_moedas"]
    extrato_total = _to_float(extrato.get("total"))
    linhas = extrato.get("linhas") or []
    soma_linhas = round(sum(_to_float(item.get("valor")) for item in linhas), 2)

    modo = str(modo or "completo")
    if modo not in ("completo", "selecionar"):
        modo = "completo"
    if modo == "selecionar":
        indices = _indices_selecionados(linhas, selecionadas)
        total_comparado = round(
            sum(_to_float(linhas[i].get("valor")) for i in indices), 2
        )
    else:
        indices = list(range(len(linhas)))
        total_comparado = extrato_total

    diferenca = (
        round(total_comparado - caixa_total, 2) if resumo["caixa_qtd"] else None
    )
    inconsistencias = abs(soma_linhas - extrato_total) > 0.005

    if not resumo["caixa_qtd"]:
        status = STATUS_SEM_CAIXA
    elif abs(diferenca or 0) <= 0.005:
        status = STATUS_BATE
    else:
        status = STATUS_NAO_BATE

    return {
        "data": data_iso,
        "executado_em": _now(),
        "modo": modo,
        "selecionadas": indices,
        "extrato_total": extrato_total,
        "extrato_total_texto": str(extrato.get("total_texto") or ""),
        "linhas": linhas,
        "soma_linhas": soma_linhas,
        "extrato_inconsistente": inconsistencias,
        "total_comparado": total_comparado,
        "caixa_total": caixa_total,
        "caixa_moedas": caixa_moedas,
        "caixa_qtd": resumo["caixa_qtd"],
        "caixa_ids": resumo["caixa_ids"],
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
