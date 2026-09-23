"""
Saldos de caixa - acompanhamento do saldo devedor das atendentes.

Controle simples por funcionario:
  - DEBITO    = valor devido (ex: quebra de caixa)
  - PAGAMENTO = valor pago/abatido
O saldo devedor e `total_debitos - total_pagamentos`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

FUNCIONARIOS_TABLE = "saldos_funcionarios"
LANCAMENTOS_TABLE = "saldos_lancamentos"

TIPOS = ("DEBITO", "PAGAMENTO")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


# ─── Funcionarios ────────────────────────────────────────────────

def criar_funcionario(database, nome: str) -> dict[str, Any]:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do funcionario.")
    for f in database.all(FUNCIONARIOS_TABLE):
        if str(f.get("nome", "")).strip().lower() == nome.lower():
            raise ValueError("Funcionario ja cadastrado.")
    doc = {"id": str(uuid4()), "nome": nome, "criado_em": _now()}
    database.insert(FUNCIONARIOS_TABLE, doc)
    return doc


def remover_funcionario(database, funcionario_id: str) -> bool:
    docs = database.search(FUNCIONARIOS_TABLE, {"id": funcionario_id})
    if not docs:
        return False
    for lanc in database.search(LANCAMENTOS_TABLE, {"funcionario_id": funcionario_id}):
        database.delete(LANCAMENTOS_TABLE, _doc_id(lanc))
    database.delete(FUNCIONARIOS_TABLE, _doc_id(docs[0]))
    return True


def _saldo(lancamentos: list[dict[str, Any]]) -> tuple[float, float]:
    debitos = sum(
        float(l.get("valor", 0) or 0)
        for l in lancamentos
        if l.get("tipo") == "DEBITO"
    )
    pagamentos = sum(
        float(l.get("valor", 0) or 0)
        for l in lancamentos
        if l.get("tipo") == "PAGAMENTO"
    )
    return round(debitos, 2), round(pagamentos, 2)


def listar_funcionarios(database) -> list[dict[str, Any]]:
    funcionarios = database.all(FUNCIONARIOS_TABLE)
    lancamentos = database.all(LANCAMENTOS_TABLE)
    por_funcionario: dict[str, list[dict[str, Any]]] = {}
    for l in lancamentos:
        por_funcionario.setdefault(str(l.get("funcionario_id", "")), []).append(l)

    out: list[dict[str, Any]] = []
    for f in funcionarios:
        fid = str(f.get("id", ""))
        lancs = por_funcionario.get(fid, [])
        debitos, pagamentos = _saldo(lancs)
        out.append({
            "id": fid,
            "nome": f.get("nome", ""),
            "criado_em": f.get("criado_em", ""),
            "total_debitos": debitos,
            "total_pagamentos": pagamentos,
            "saldo": round(debitos - pagamentos, 2),
            "lancamentos": len(lancs),
        })
    out.sort(key=lambda x: x["nome"].lower())
    return out


# ─── Lancamentos ─────────────────────────────────────────────────

def criar_lancamento(database, data: dict[str, Any]) -> dict[str, Any]:
    funcionario_id = str(data.get("funcionario_id", "")).strip()
    if not funcionario_id:
        raise ValueError("Selecione um funcionario.")
    if not database.search(FUNCIONARIOS_TABLE, {"id": funcionario_id}):
        raise ValueError("Funcionario nao encontrado.")

    tipo = str(data.get("tipo", "DEBITO")).upper()
    if tipo not in TIPOS:
        raise ValueError("Tipo invalido. Use DEBITO ou PAGAMENTO.")

    valor = _to_float(data.get("valor"))
    if valor <= 0:
        raise ValueError("Valor deve ser maior que zero.")

    referente = str(data.get("referente_a", "")).strip()
    if not referente:
        raise ValueError("Informe a que o lancamento se refere (referente a).")

    data_lanc = str(data.get("data") or datetime.now().strftime("%d/%m/%Y"))
    doc = {
        "id": str(uuid4()),
        "funcionario_id": funcionario_id,
        "tipo": tipo,
        "valor": valor,
        "referente_a": referente,
        "data": data_lanc,
        "criado_em": _now(),
    }
    database.insert(LANCAMENTOS_TABLE, doc)
    return doc


def listar_lancamentos(database, funcionario_id: str) -> list[dict[str, Any]]:
    docs = database.search(LANCAMENTOS_TABLE, {"funcionario_id": funcionario_id})
    docs.sort(key=lambda d: str(d.get("criado_em", "")), reverse=True)
    return [dict(d, _id=_doc_id(d)) for d in docs]


def remover_lancamento(database, lancamento_id: str) -> bool:
    docs = database.search(LANCAMENTOS_TABLE, {"id": lancamento_id})
    if not docs:
        return False
    database.delete(LANCAMENTOS_TABLE, _doc_id(docs[0]))
    return True
