"""
Lançamentos financeiros do caixa restaurante no Cloudfy.

Regras:

- Notas de despesa: lista `{id, descricao, valor, legado?}` no caixa (topo) e
  por turno quando o caixa é dividido. A soma alimenta o DINHEIRO real.
- Ajuste antigo (`dinheiro_ajuste` numérico, sem notas) migra para uma nota
  `AJUSTE MANUAL` marcada como legado.
- Transferência MOEDAS: uma por data, valor = soma de `dinheiro_moedas` de
  todos os caixas restaurante da data.
- Histórico em `lancamentos_financeiros`, um registro por chave (upsert).
  Pendentes são derivados dos caixas + histórico.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from app.modules.conciliador.config_posto import (
    DEFAULT_FINANCEIRO,
    DEFAULT_FINANCEIRO_CATEGORIA,
    categoria_por_codigo,
    normalizar_categorias_financeiro,
)
from app.modules.conciliador.constants import parse_money

CONCILIACOES_TABLE = "conciliacoes"
TABLE = "lancamentos_financeiros"

TIPO_MOEDAS = "transferencia_moedas"
TIPO_DESPESA = "despesa"

STATUS_PENDENTE = "pendente"
STATUS_ERRO = "erro"
STATUS_LANCADO = "lancado"
STATUS_DIVERGENTE = "divergente"

DESCRICAO_LEGADO = "AJUSTE MANUAL"

MARGEM = 0.005


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _doc_id(doc: dict[str, Any]) -> str:
    raw = getattr(doc, "doc_id", None)
    if raw is None:
        raw = doc.get("doc_id") or doc.get("id")
    return str(raw) if raw is not None else ""


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    try:
        return round(parse_money(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _round(value: float) -> float:
    return round(float(value or 0), 2)


# ─── Configuração ────────────────────────────────────────────────

def config_financeiro(settings: dict | None = None) -> dict[str, Any]:
    settings = settings or {}
    cfg: dict[str, Any] = {}
    for chave, padrao in DEFAULT_FINANCEIRO.items():
        valor = settings.get(chave)
        if valor is None or str(valor).strip() == "":
            cfg[chave] = padrao
        else:
            cfg[chave] = str(valor).strip()

    categorias = normalizar_categorias_financeiro(
        settings.get("financeiro_categorias")
    )
    cfg["financeiro_categorias"] = categorias
    padrao = str(settings.get("financeiro_categoria_padrao") or "").strip()
    if not categoria_por_codigo(categorias, padrao):
        padrao = DEFAULT_FINANCEIRO_CATEGORIA
    if not categoria_por_codigo(categorias, padrao):
        padrao = categorias[0]["codigo"]
    cfg["financeiro_categoria_padrao"] = padrao
    return cfg


def resolver_categoria(
    tipo_codigo: Any,
    tipo_descricao: Any,
    config: dict[str, Any],
) -> tuple[str, str]:
    """Categoria efetiva: config atual pelo código; snapshot como fallback."""
    codigo = str(tipo_codigo or "").strip()
    snapshot = " ".join(str(tipo_descricao or "").split())
    categorias = config.get("financeiro_categorias") or []
    if not codigo:
        # Nota antiga/sem tipo: mantem o comportamento historico (54).
        codigo = DEFAULT_FINANCEIRO_CATEGORIA
        if not categoria_por_codigo(categorias, codigo):
            codigo = str(config.get("financeiro_categoria_padrao") or codigo)
    categoria = categoria_por_codigo(categorias, codigo)
    if categoria:
        return str(categoria["codigo"]), str(categoria["descricao"])
    return codigo, snapshot or codigo


# ─── Notas de despesa ────────────────────────────────────────────

def normalizar_nota(raw: Any, default_id: str | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    descricao = str(raw.get("descricao", "")).strip()
    valor = _to_float(raw.get("valor"))
    if valor <= 0:
        return None
    nota_id = str(raw.get("id") or default_id or uuid4())
    return {
        "id": nota_id,
        "descricao": descricao or "DESPESA",
        "valor": valor,
        "tipo_codigo": str(
            raw.get("tipo_codigo") or raw.get("categoria_codigo") or ""
        ).strip(),
        "tipo_descricao": " ".join(
            str(
                raw.get("tipo_descricao") or raw.get("categoria_descricao") or ""
            ).split()
        ),
        "legado": bool(raw.get("legado")),
    }


def normalizar_notas(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in raw:
        nota = normalizar_nota(item)
        if nota is None:
            continue
        if nota["id"] in vistos:
            nota["id"] = str(uuid4())
        vistos.add(nota["id"])
        out.append(nota)
    return out


def nota_legado(nota_id: str, valor: float) -> dict[str, Any]:
    return {
        "id": nota_id,
        "descricao": DESCRICAO_LEGADO,
        "valor": _round(valor),
        "legado": True,
    }


def somar_notas(notas: list[dict[str, Any]] | None) -> float:
    return _round(sum(_to_float(n.get("valor")) for n in (notas or [])))


def _notas_turno(turno: dict[str, Any] | None, numero: int) -> list[dict[str, Any]]:
    turno = turno or {}
    notas = normalizar_notas(turno.get("despesas_notas"))
    if notas:
        return notas
    ajuste = _to_float(turno.get("dinheiro_ajuste"))
    if ajuste > 0:
        return [nota_legado(f"legado-{numero}", ajuste)]
    return []


def normalizar_despesas(data: dict[str, Any]) -> dict[str, Any]:
    """Normaliza notas no topo e nos turnos; deriva `dinheiro_ajuste`.

    Usado por `_normalize_restaurante` para que o ajuste continue existindo
    como soma das notas (export/resultado/testes antigos).
    """
    turnos = data.get("turnos")
    if isinstance(turnos, dict) and turnos:
        topo = normalizar_notas(data.get("despesas_notas"))
        total = 0.0
        merged: list[dict[str, Any]] = []
        for numero in (1, 2):
            turno = turnos.get(str(numero))
            if not isinstance(turno, dict):
                continue
            notas = _notas_turno(turno, numero)
            turno["despesas_notas"] = notas
            turno["dinheiro_ajuste"] = somar_notas(notas)
            total += turno["dinheiro_ajuste"]
            merged.extend([dict(nota, turno=numero) for nota in notas])
        data["despesas_notas"] = merged
        data["dinheiro_ajuste"] = _round(total)
        if total <= 0 and not merged:
            # Cliente antigo/parcial pode mandar só o topo, sem turnos.
            if topo:
                data["despesas_notas"] = topo
                data["dinheiro_ajuste"] = somar_notas(topo)
        return data

    notas = normalizar_notas(data.get("despesas_notas"))
    if not notas:
        ajuste = _to_float(data.get("dinheiro_ajuste"))
        if ajuste > 0:
            notas = [nota_legado("legado-caixa", ajuste)]
    data["despesas_notas"] = notas
    data["dinheiro_ajuste"] = somar_notas(notas)
    return data


def notas_do_caixa(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Notas do caixa com `turno` (1/2) quando dividido."""
    turnos = doc.get("turnos")
    if doc.get("split_mode") and isinstance(turnos, dict) and turnos:
        out: list[dict[str, Any]] = []
        for numero in (1, 2):
            turno = turnos.get(str(numero))
            if not isinstance(turno, dict):
                continue
            for nota in _notas_turno(turno, numero):
                out.append(dict(nota, turno=numero))
        if out:
            return out

    notas = normalizar_notas(doc.get("despesas_notas"))
    if not notas:
        ajuste = _to_float(doc.get("dinheiro_ajuste"))
        if ajuste > 0:
            notas = [nota_legado("legado-caixa", ajuste)]
    return [dict(nota, turno=None) for nota in notas]


# ─── MOEDAS do dia ───────────────────────────────────────────────

def _moedas_doc(doc: dict[str, Any]) -> float:
    if "dinheiro_moedas" in doc:
        return _round(_to_float(doc.get("dinheiro_moedas")))
    total = 0.0
    for contagem in doc.get("contagens_dinheiro") or []:
        if contagem.get("label") == "Geral":
            total += _to_float(contagem.get("moedas"))
    return _round(total)


def valor_moedas_do_dia(database, data_iso: str) -> float:
    if not data_iso:
        return 0.0
    total = 0.0
    for doc in database.all(CONCILIACOES_TABLE):
        if doc.get("tipo") != "restaurante":
            continue
        if str(doc.get("data", "")) != data_iso:
            continue
        total += _moedas_doc(doc)
    return _round(total)


# ─── Chaves e registros ──────────────────────────────────────────

def chave_moedas(data_iso: str) -> str:
    return f"{TIPO_MOEDAS}|{data_iso}"


def chave_moedas_delta(data_iso: str, total: float) -> str:
    return f"{TIPO_MOEDAS}|{data_iso}|delta|{_round(total):.2f}"


def chave_despesa(caixa_id: str, turno: int | None, nota_id: str) -> str:
    return f"{TIPO_DESPESA}|{caixa_id}|{turno or 0}|{nota_id}"


def _registros(database, data_iso: str, tipo: str | None = None) -> list[dict[str, Any]]:
    out = []
    for doc in database.all(TABLE):
        if str(doc.get("data", "")) != data_iso:
            continue
        if tipo and doc.get("tipo") != tipo:
            continue
        out.append(doc)
    return out


def _por_chave(database) -> dict[str, dict[str, Any]]:
    return {str(doc.get("chave")): doc for doc in database.all(TABLE)}


def registrar_resultado(
    database,
    item: dict[str, Any],
    ok: bool,
    erro: str = "",
) -> dict[str, Any]:
    now = _now()
    existentes = database.search(TABLE, {"chave": item["chave"]})
    existente = existentes[0] if existentes else None
    lancado_em = existente.get("lancado_em", "") if existente else ""
    if ok:
        lancado_em = now

    payload = {
        "chave": item["chave"],
        "tipo": item["tipo"],
        "caixa_id": item.get("caixa_id", ""),
        "turno": item.get("turno"),
        "nota_id": item.get("nota_id"),
        "tipo_codigo": str(item.get("tipo_codigo") or ""),
        "tipo_descricao": str(item.get("tipo_descricao") or ""),
        "data": item.get("data", ""),
        "descricao": item.get("descricao", ""),
        "valor": _to_float(item.get("valor")),
        "status": STATUS_LANCADO if ok else STATUS_ERRO,
        "erro": "" if ok else (erro or "Falha no lancamento."),
        "criado_em": (existente or {}).get("criado_em") or now,
        "atualizado_em": now,
        "lancado_em": lancado_em,
    }

    # Uma tentativa de relançamento que falhou não pode sobrescrever o valor
    # que de fato foi lançado antes.
    if not ok and existente and existente.get("lancado_em"):
        payload["valor"] = _to_float(existente.get("valor"))
        payload["descricao"] = existente.get("descricao", payload["descricao"])

    if existente:
        database.update(TABLE, _doc_id(existente), payload)
    else:
        database.insert(TABLE, payload)
    return payload


# ─── Pendentes ───────────────────────────────────────────────────

def _item_base(
    *,
    chave: str,
    tipo: str,
    descricao: str,
    valor: float,
    data_iso: str,
    caixa_id: str,
    turno: int | None = None,
    nota_id: str | None = None,
    tipo_codigo: str = "",
    tipo_descricao: str = "",
    status: str = STATUS_PENDENTE,
    selecionavel: bool = True,
    legado: bool = False,
    complemento: bool = False,
    erro: str = "",
    lancado_em: str = "",
    valor_atual: float | None = None,
    detalhe: str = "",
) -> dict[str, Any]:
    atual = _to_float(valor_atual) if valor_atual is not None else None
    return {
        "chave": chave,
        "tipo": tipo,
        "descricao": descricao,
        "valor": _to_float(valor),
        "valor_atual": atual,
        "alterado": bool(
            atual is not None and abs(atual - _to_float(valor)) >= MARGEM
        ),
        "data": data_iso,
        "caixa_id": caixa_id,
        "turno": turno,
        "nota_id": nota_id,
        "tipo_codigo": str(tipo_codigo or ""),
        "tipo_descricao": str(tipo_descricao or ""),
        "status": status,
        "selecionavel": bool(selecionavel),
        "legado": bool(legado),
        "complemento": bool(complemento),
        "erro": erro,
        "lancado_em": lancado_em,
        "detalhe": detalhe,
    }


def _moedas_itens(
    database,
    data_iso: str,
    caixa_id: str,
    descricao: str,
) -> tuple[list[dict[str, Any]], float, float]:
    total = valor_moedas_do_dia(database, data_iso)
    registros = _registros(database, data_iso, TIPO_MOEDAS)
    lancados = [r for r in registros if r.get("lancado_em")]
    soma_lancada = _round(sum(_to_float(r.get("valor")) for r in lancados))
    por_chave = {str(r.get("chave")): r for r in registros}

    itens: list[dict[str, Any]] = []

    # Histórico do que já foi lançado (inclusive tentativas com erro posterior).
    for registro in sorted(lancados, key=lambda r: str(r.get("lancado_em", ""))):
        itens.append(
            _item_base(
                chave=str(registro.get("chave")),
                tipo=TIPO_MOEDAS,
                descricao=str(registro.get("descricao") or descricao),
                valor=registro.get("valor", 0),
                data_iso=data_iso,
                caixa_id=caixa_id,
                status=STATUS_LANCADO,
                selecionavel=False,
                erro=str(registro.get("erro") or ""),
                lancado_em=str(registro.get("lancado_em") or ""),
                detalhe="Transferencia ja lancada.",
            )
        )

    if total <= 0 and not lancados:
        return itens, total, soma_lancada

    if not lancados:
        chave = chave_moedas(data_iso)
        registro = por_chave.get(chave)
        itens.append(
            _item_base(
                chave=chave,
                tipo=TIPO_MOEDAS,
                descricao=descricao,
                valor=total,
                data_iso=data_iso,
                caixa_id=caixa_id,
                status=STATUS_ERRO if registro else STATUS_PENDENTE,
                selecionavel=True,
                erro=str((registro or {}).get("erro") or ""),
                detalhe="Soma das moedas de todos os caixas da data.",
            )
        )
        return itens, total, soma_lancada

    diferenca = _round(total - soma_lancada)
    if diferenca > MARGEM:
        chave = chave_moedas_delta(data_iso, total)
        registro = por_chave.get(chave)
        itens.append(
            _item_base(
                chave=chave,
                tipo=TIPO_MOEDAS,
                descricao=descricao,
                valor=diferenca,
                data_iso=data_iso,
                caixa_id=caixa_id,
                status=STATUS_ERRO if registro else STATUS_PENDENTE,
                selecionavel=True,
                complemento=True,
                erro=str((registro or {}).get("erro") or ""),
                detalhe=(
                    f"Complemento: total do dia {total:.2f}, "
                    f"ja lancado {soma_lancada:.2f}."
                ),
            )
        )
    elif diferenca < -MARGEM:
        itens.append(
            _item_base(
                chave=f"{TIPO_MOEDAS}|{data_iso}|divergente|{total:.2f}",
                tipo=TIPO_MOEDAS,
                descricao=descricao,
                valor=total,
                data_iso=data_iso,
                caixa_id=caixa_id,
                status=STATUS_DIVERGENTE,
                selecionavel=False,
                detalhe=(
                    f"Soma atual ({total:.2f}) menor que o ja lancado "
                    f"({soma_lancada:.2f}). Revise no Cloudfy."
                ),
            )
        )

    return itens, total, soma_lancada


def _despesas_itens(
    database,
    doc: dict[str, Any],
    caixa_id: str,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    data_iso = str(doc.get("data", ""))
    chaves = _por_chave(database)
    itens: list[dict[str, Any]] = []
    config = config or config_financeiro({})

    for nota in notas_do_caixa(doc):
        turno = nota.get("turno")
        nota_id = str(nota.get("id"))
        chave = chave_despesa(caixa_id, turno, nota_id)
        registro = chaves.get(chave)
        valor = _to_float(nota.get("valor"))
        descricao = str(nota.get("descricao") or "DESPESA")
        legado = bool(nota.get("legado"))
        tipo_codigo, tipo_descricao = resolver_categoria(
            nota.get("tipo_codigo"),
            nota.get("tipo_descricao"),
            config,
        )

        if registro and registro.get("lancado_em"):
            itens.append(
                _item_base(
                    chave=chave,
                    tipo=TIPO_DESPESA,
                    descricao=descricao,
                    valor=registro.get("valor", 0),
                    valor_atual=valor,
                    data_iso=data_iso,
                    caixa_id=caixa_id,
                    turno=turno,
                    nota_id=nota_id,
                    tipo_codigo=str(
                        registro.get("tipo_codigo") or tipo_codigo
                    ),
                    tipo_descricao=str(
                        registro.get("tipo_descricao") or tipo_descricao
                    ),
                    status=STATUS_LANCADO,
                    selecionavel=False,
                    legado=legado,
                    erro=str(registro.get("erro") or ""),
                    lancado_em=str(registro.get("lancado_em") or ""),
                    detalhe="Pagamento ja lancado.",
                )
            )
            continue

        if registro and registro.get("status") == STATUS_ERRO:
            itens.append(
                _item_base(
                    chave=chave,
                    tipo=TIPO_DESPESA,
                    descricao=descricao,
                    valor=valor,
                    data_iso=data_iso,
                    caixa_id=caixa_id,
                    turno=turno,
                    nota_id=nota_id,
                    tipo_codigo=tipo_codigo,
                    tipo_descricao=tipo_descricao,
                    status=STATUS_ERRO,
                    selecionavel=True,
                    legado=legado,
                    erro=str(registro.get("erro") or ""),
                    detalhe="Tentativa anterior falhou.",
                )
            )
            continue

        itens.append(
            _item_base(
                chave=chave,
                tipo=TIPO_DESPESA,
                descricao=descricao,
                valor=valor,
                data_iso=data_iso,
                caixa_id=caixa_id,
                turno=turno,
                nota_id=nota_id,
                tipo_codigo=tipo_codigo,
                tipo_descricao=tipo_descricao,
                status=STATUS_PENDENTE,
                selecionavel=True,
                legado=legado,
                detalhe="Pagamento pendente.",
            )
        )

    return itens


def pendentes_caixa(database, caixa_id: str, settings: dict | None = None) -> dict[str, Any]:
    doc = database.get(CONCILIACOES_TABLE, str(caixa_id))
    if not doc:
        raise ValueError("Conciliacao nao encontrada.")
    if doc.get("tipo") != "restaurante":
        raise ValueError("Lancamentos financeiros disponiveis apenas para o restaurante.")

    config = config_financeiro(settings)
    data_iso = str(doc.get("data", "") or "").strip()
    status_caixa = str(doc.get("status", "rascunho") or "rascunho")

    motivo = ""
    if not data_iso:
        motivo = "Informe a data do caixa antes de lancar."
    elif status_caixa == "arquivado":
        motivo = "Caixa arquivado nao pode ser lancado. Restaure o caixa primeiro."

    itens: list[dict[str, Any]] = []
    total_moedas = 0.0
    lancado_moedas = 0.0
    if data_iso:
        moedas, total_moedas, lancado_moedas = _moedas_itens(
            database,
            data_iso,
            str(caixa_id),
            config["financeiro_descricao_moedas"],
        )
        itens.extend(moedas)

    despesas = _despesas_itens(database, doc, str(caixa_id), config)
    itens.extend(despesas)

    if motivo:
        for item in itens:
            if item["selecionavel"]:
                item["selecionavel"] = False

    despesas_pendentes = _round(
        sum(i["valor"] for i in itens if i["tipo"] == TIPO_DESPESA and i["selecionavel"])
    )
    despesas_lancadas = _round(
        sum(
            i["valor"]
            for i in itens
            if i["tipo"] == TIPO_DESPESA and i["lancado_em"]
        )
    )
    moedas_pendentes = _round(
        sum(i["valor"] for i in itens if i["tipo"] == TIPO_MOEDAS and i["selecionavel"])
    )

    resumo = {
        "moedas_total": _round(total_moedas),
        "moedas_lancado": _round(lancado_moedas),
        "moedas_pendente": moedas_pendentes,
        "despesas_total": _round(despesas_pendentes + despesas_lancadas),
        "despesas_lancado": despesas_lancadas,
        "despesas_pendente": despesas_pendentes,
        "pendencias": sum(1 for i in itens if i["selecionavel"]),
        "bloqueado": bool(motivo),
        "motivo_bloqueio": motivo,
    }

    return {
        "caixa_id": str(caixa_id),
        "data": data_iso,
        "status_caixa": status_caixa,
        "itens": itens,
        "resumo": resumo,
        "config": config,
    }


# ─── Seleção para lançamento ─────────────────────────────────────

def selecionar_por_chaves(
    database,
    caixa_id: str,
    chaves: list[str],
    forcar: bool = False,
    settings: dict | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(chaves, list) or not chaves:
        raise ValueError("Selecione pelo menos um lancamento.")

    pendentes = pendentes_caixa(database, caixa_id, settings)
    if pendentes["resumo"]["bloqueado"]:
        raise ValueError(pendentes["resumo"]["motivo_bloqueio"])

    por_chave = {item["chave"]: item for item in pendentes["itens"]}
    erros: list[str] = []
    itens: list[dict[str, Any]] = []
    vistos: set[str] = set()

    for chave in chaves:
        chave = str(chave)
        if chave in vistos:
            continue
        vistos.add(chave)
        item = por_chave.get(chave)
        if item is None:
            erros.append(f"Item nao encontrado na revisao: {chave}.")
            continue
        if item["status"] == STATUS_DIVERGENTE:
            erros.append(
                "MOEDAS com soma menor que o lancado. Revise manualmente no Cloudfy."
            )
            continue
        if not item["selecionavel"] and not forcar:
            erros.append(
                f"'{item['descricao']}' ja foi lancado. Use Relancar com confirmacao."
            )
            continue
        valor = item["valor"]
        if item.get("valor_atual") is not None:
            valor = item["valor_atual"]
        if valor <= 0:
            erros.append(f"'{item['descricao']}' sem valor positivo.")
            continue
        itens.append(
            {
                "chave": item["chave"],
                "tipo": item["tipo"],
                "descricao": item["descricao"],
                "valor": _to_float(valor),
                "data": item["data"],
                "caixa_id": str(caixa_id),
                "turno": item.get("turno"),
                "nota_id": item.get("nota_id"),
                "tipo_codigo": str(item.get("tipo_codigo") or ""),
                "tipo_descricao": str(item.get("tipo_descricao") or ""),
            }
        )

    if erros:
        raise ValueError(" | ".join(erros))
    if not itens:
        raise ValueError("Nenhum lancamento valido selecionado.")
    return itens


def listar_registros(
    database,
    caixa_id: str | None = None,
    data_iso: str | None = None,
) -> list[dict[str, Any]]:
    out = []
    for doc in database.all(TABLE):
        if caixa_id and str(doc.get("caixa_id", "")) != str(caixa_id):
            continue
        if data_iso and str(doc.get("data", "")) != data_iso:
            continue
        out.append(doc)
    out.sort(key=lambda d: str(d.get("atualizado_em", "")), reverse=True)
    return out
