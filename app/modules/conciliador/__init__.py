from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import Response

from app.core import app_context
from app.modules.conciliador.manifest import manifest
from app.modules.conciliador.constants import (
    empty_categories_posto,
    parse_money,
    empty_categories_restaurante,
    normalize_categories_posto,
    normalize_categories_restaurante,
)
from app.modules.conciliador.parsers import (
    parse_caixa_csv,
    parse_pagbank_csv,
    parse_premmia_file,
    parse_restaurante_pagbank_csv,
    parse_restaurante_pagbank_split,
)
from app.modules.conciliador.services import (
    totals_posto,
    totals_restaurante,
    consolidate_contagens,
    validate_contagens,
)
from app.modules.conciliador.config_posto import (
    load_config,
    save_config,
    default_config,
    config_category_keys,
    config_labels,
    load_settings,
    save_settings,
    load_cloudfy_mapeamento,
    save_cloudfy_mapeamento,
    DEFAULT_CLOUDY_MAPEAMENTO,
)
from app.modules.conciliador.export import generate_conciliation_pdf_bytes
from app.modules.conciliador.automacao import (
    listar_caixas_cloudfy,
    importar_caixa_cloudfy,
)

router = APIRouter(prefix="/api/conciliador", tags=["Conciliador"])
TABLE = "conciliacoes"


def _posto_config() -> dict:
    return load_config(app_context.database)


# ─── Helpers ─────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _get_or_404(conciliacao_id: str) -> dict:
    doc = app_context.database.get(TABLE, conciliacao_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Conciliacao nao encontrada")
    return doc


def _normalize_posto(data: dict) -> dict:
    now = _now()
    config = _posto_config()
    keys = config_category_keys(config)
    labels = config_labels(config)
    data.setdefault("id", str(uuid4()))
    data.setdefault("status", "rascunho")
    data.setdefault("tipo", "posto")
    data.setdefault("categorias", empty_categories_posto(keys))
    data["categorias"] = normalize_categories_posto(data["categorias"], keys)
    data.setdefault("fitcard_total", 0.0)
    data.setdefault("sangria", 0.0)
    data.setdefault("notas_a_prazo", 0.0)
    data.setdefault("despesas", 0.0)
    data.setdefault("contagens_dinheiro", [])
    data.setdefault("lancamentos_avulsos", [])
    data.setdefault("premmia_lancamentos", [])
    data.setdefault("status_caixa", "")
    data.setdefault("status_pagbank", "")
    data.setdefault("status_premmia", "")
    data.setdefault("observacoes", "")
    data.setdefault("dinheiro_notas", 0.0)
    data.setdefault("dinheiro_moedas", 0.0)
    data.setdefault("criado_em", now)
    data["atualizado_em"] = now
    avulsos = data.get("lancamentos_avulsos") or []
    contagens = data.get("contagens_dinheiro") or []
    data["dinheiro_notas"], data["dinheiro_moedas"] = _dinheiro_breakdown(contagens)

    cash_total = _dinheiro_real_from_contagens(contagens)
    for key in data["categorias"]:
        if key == "SANGRIA" or labels.get(key, "").upper() == "SANGRIA":
            data["categorias"][key]["site"] = round(cash_total, 2)
            break

    total_sistema, total_site, diferenca = totals_posto(
        data["categorias"], avulsos, keys, labels
    )
    data["total_sistema"] = total_sistema
    data["total_site"] = total_site
    data["diferenca_total"] = diferenca
    return data


def _normalize_restaurante(data: dict) -> dict:
    now = _now()
    data.setdefault("id", str(uuid4()))
    data.setdefault("status", "rascunho")
    data.setdefault("tipo", "restaurante")
    data.setdefault("turno", None)
    data.setdefault("categorias", empty_categories_restaurante())
    data["categorias"] = normalize_categories_restaurante(data["categorias"])
    data.setdefault("contagens_dinheiro", [])
    data.setdefault("lancamentos_avulsos", [])
    data.setdefault("observacoes", "")
    data.setdefault("dinheiro_real", 0.0)
    data.setdefault("criado_em", now)
    data["atualizado_em"] = now
    avulsos = data.get("lancamentos_avulsos") or []
    contagens = data.get("contagens_dinheiro") or []
    dinheiro_real = _dinheiro_real_from_contagens(contagens)
    total_sistema, total_real, diferenca = totals_restaurante(
        data["categorias"], avulsos, dinheiro_real
    )
    data["total_sistema"] = total_sistema
    data["total_real"] = total_real
    data["diferenca_total"] = diferenca
    data["dinheiro_real"] = dinheiro_real
    data["dinheiro_notas"], data["dinheiro_moedas"] = _dinheiro_breakdown(contagens)
    return data


def _sanitize_for_response(doc: dict) -> dict:
    result = dict(doc)
    result.pop("doc_id", None)
    if "doc_id" in result:
        del result["doc_id"]
    return result


def _dinheiro_real_from_contagens(contagens: list[dict]) -> float:
    """Soma o total de todas as contagens 'Geral'.

    Em caixa normal existe uma unica 'Geral'. Em caixa dividido (T1/T2)
    as contagens de ambos os turnos sao mescladas, gerando duas 'Geral';
    ambas devem somar no dinheiro real combinado.
    """
    gerais = [c for c in (contagens or []) if c.get("label") == "Geral"]
    if not gerais:
        return 0.0
    return round(sum(float(c.get("total", 0) or 0) for c in gerais), 2)


def _dinheiro_breakdown(contagens: list[dict]) -> tuple[float, float]:
    gerais = [c for c in (contagens or []) if c.get("label") == "Geral"]
    notas_total = 0.0
    moedas_total = 0.0
    for c in gerais:
        total = float(c.get("total", 0) or 0)
        moedas = parse_money(c.get("moedas", 0))
        notas_total += round(total - moedas, 2)
        moedas_total += moedas
    return round(notas_total, 2), round(moedas_total, 2)


# ─── CRUD ────────────────────────────────────────────────────────

@router.get("/conciliacoes")
async def list_conciliacoes(
    tipo: str | None = Query(None),
    status: str | None = Query(None),
    data: str | None = Query(None),
):
    all_docs = app_context.database.all(TABLE)
    records = []
    for doc in all_docs:
        doc_tipo = doc.get("tipo", "posto")
        doc_status = doc.get("status", "rascunho")
        doc_data = doc.get("data", "")
        if tipo and doc_tipo != tipo:
            continue
        if data and doc_data != data:
            continue
        if status == "ativos":
            if doc_status == "arquivado":
                continue
        elif status and status != "todos":
            if doc_status != status:
                continue
        records.append(doc)
    records.sort(key=lambda item: item.get("data", ""), reverse=True)
    for doc in records:
        doc["_id"] = str(doc.get("doc_id", doc.get("id", "")))
    return [dict(d, _id=str(d.get("doc_id", d.get("id", "")))) for d in records]


@router.get("/conciliacoes/{conciliacao_id}")
async def get_conciliacao(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    doc["_id"] = str(doc.get("doc_id", doc.get("id", "")))
    return doc


def _normalize_contagem_avulsa(data: dict) -> dict:
    """Contagem de dinheiro autonoma (nao vinculada a um caixa)."""
    now = _now()
    data.setdefault("id", str(uuid4()))
    data.setdefault("status", "rascunho")
    data["kind"] = "contagem"
    data.setdefault("tipo", "posto")
    data.setdefault("contagens_dinheiro", [])
    data.setdefault("observacoes", "")
    data.setdefault("criado_em", now)
    data["atualizado_em"] = now
    contagens = data.get("contagens_dinheiro") or []
    total = _dinheiro_real_from_contagens(contagens)
    data["total_sistema"] = 0.0
    data["total_site"] = 0.0
    data["total_real"] = total
    data["diferenca_total"] = 0.0
    data["dinheiro_real"] = total
    data["dinheiro_notas"], data["dinheiro_moedas"] = _dinheiro_breakdown(contagens)
    return data


@router.post("/conciliacoes")
async def save_conciliacao(data: dict):
    tipo = data.get("tipo", "posto")
    kind = data.get("kind")
    conciliacao_id = data.get("id") or data.get("_id")

    existing = None
    if conciliacao_id:
        existing = app_context.database.get(TABLE, str(conciliacao_id))

    if kind == "contagem":
        normalized = _normalize_contagem_avulsa(data)
    elif tipo == "restaurante":
        normalized = _normalize_restaurante(data)
    else:
        normalized = _normalize_posto(data)

    if existing:
        existing_id = str(existing.get("doc_id", existing.get("id", "")))
        app_context.database.update(TABLE, existing_id, normalized)
        return {"id": existing_id, **normalized}
    else:
        new_id = app_context.database.insert(TABLE, normalized)
        return {"id": new_id, **normalized}


@router.post("/conciliacoes/{conciliacao_id}/conciliar")
async def conciliar(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    existing_id = str(doc.get("doc_id", doc.get("id", "")))
    doc["status"] = "conciliado"
    doc["atualizado_em"] = _now()
    app_context.database.update(TABLE, existing_id, doc)
    return {"id": existing_id, "status": "conciliado"}


@router.post("/conciliacoes/{conciliacao_id}/arquivar")
async def arquivar(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    existing_id = str(doc.get("doc_id", doc.get("id", "")))
    doc["status"] = "arquivado"
    doc["atualizado_em"] = _now()
    app_context.database.update(TABLE, existing_id, doc)
    return {"id": existing_id, "status": "arquivado"}


@router.post("/conciliacoes/{conciliacao_id}/restaurar")
async def restaurar(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    if doc.get("status") != "arquivado":
        raise HTTPException(status_code=400, detail="Apenas conciliacoes arquivadas podem ser restauradas")
    existing_id = str(doc.get("doc_id", doc.get("id", "")))
    doc["status"] = "rascunho"
    doc["atualizado_em"] = _now()
    app_context.database.update(TABLE, existing_id, doc)
    return {"id": existing_id, "status": "rascunho"}


@router.post("/conciliacoes/{conciliacao_id}/reabrir")
async def reabrir(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    if doc.get("status") == "arquivado":
        raise HTTPException(status_code=400, detail="Restaure a conciliacao arquivada antes de reabrir")
    existing_id = str(doc.get("doc_id", doc.get("id", "")))
    doc["status"] = "rascunho"
    doc["atualizado_em"] = _now()
    app_context.database.update(TABLE, existing_id, doc)
    return {"id": existing_id, "status": "rascunho"}


@router.delete("/conciliacoes/{conciliacao_id}")
async def delete_conciliacao(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    existing_id = str(doc.get("doc_id", doc.get("id", "")))
    app_context.database.delete(TABLE, existing_id)
    return {"deleted": True}


# ─── Parsers (upload de arquivos) ─────────────────────────────────

@router.post("/parser/caixa")
async def parser_caixa(file: UploadFile = File(...)):
    content = await file.read()
    try:
        result = parse_caixa_csv(content, file.filename or "caixa.csv", _posto_config())
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/parser/pagbank")
async def parser_pagbank(file: UploadFile = File(...)):
    content = await file.read()
    try:
        result = parse_pagbank_csv(content, file.filename or "pagbank.csv", _posto_config())
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/parser/premmia")
async def parser_premmia(file: UploadFile = File(...)):
    content = await file.read()
    try:
        result = parse_premmia_file(content, file.filename or "premmia.xls", _posto_config())
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/parser/pagbank-restaurante")
async def parser_pagbank_restaurante(
    file: UploadFile = File(...),
    hora_ini: str | None = Query(None),
    hora_fim: str | None = Query(None),
):
    content = await file.read()
    try:
        result = parse_restaurante_pagbank_csv(
            content,
            file.filename or "pagbank.csv",
            hora_ini=hora_ini,
            hora_fim=hora_fim,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/parser/pagbank-restaurante-split")
async def parser_pagbank_restaurante_split(
    file: UploadFile = File(...),
    split_time: str = Query(...),
):
    content = await file.read()
    try:
        result = parse_restaurante_pagbank_split(
            content,
            file.filename or "pagbank.csv",
            split_time=split_time,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ─── Resultado (conferencia) ──────────────────────────────────────

@router.post("/conciliacoes/{conciliacao_id}/resultado")
async def build_resultado(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    tipo = doc.get("tipo", "posto")
    avulsos = doc.get("lancamentos_avulsos") or []
    contagens = doc.get("contagens_dinheiro") or []

    if tipo == "restaurante":
        from app.modules.conciliador.services import build_conciliation_rows_restaurante
        dinheiro_real = _dinheiro_real_from_contagens(contagens)
        rows = build_conciliation_rows_restaurante(
            doc.get("categorias", {}), avulsos, dinheiro_real
        )
    else:
        from app.modules.conciliador.services import build_conciliation_rows_posto
        config = _posto_config()
        rows = build_conciliation_rows_posto(
            doc.get("categorias", {}),
            avulsos,
            config_category_keys(config),
            config_labels(config),
        )

    return {
        "rows": rows,
        "total_sistema": doc.get("total_sistema", 0),
        "total_site" if tipo == "posto" else "total_real": doc.get(
            "total_site" if tipo == "posto" else "total_real", 0
        ),
        "diferenca_total": doc.get("diferenca_total", 0),
        "sangria": doc.get("sangria", 0),
        "notas_a_prazo": doc.get("notas_a_prazo", 0),
        "despesas": doc.get("despesas", 0),
    }


# ─── Export PDF ───────────────────────────────────────────────────

@router.get("/conciliacoes/{conciliacao_id}/export/pdf")
async def export_pdf(conciliacao_id: str):
    doc = _get_or_404(conciliacao_id)
    try:
        cfg = _posto_config() if doc.get("tipo", "posto") == "posto" else None
        pdf_bytes = generate_conciliation_pdf_bytes(doc, cfg)
        date_str = doc.get("data", "export")
        tipo = doc.get("tipo", "")
        tipo_str = f"_{tipo}" if tipo else ""
        filename = f"CaixaPos{tipo_str}_{date_str}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Configuração de grupos (Posto) ──────────────────────────────

@router.get("/config/posto")
async def get_config_posto():
    config = _posto_config()
    return {
        "grupos": config["grupos"],
        "categorias": config_category_keys(config),
        "labels": config_labels(config),
    }


@router.put("/config/posto")
async def update_config_posto(data: dict):
    try:
        saved = save_config(app_context.database, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    config = {"grupos": saved["grupos"]}
    return {
        "grupos": config["grupos"],
        "categorias": config_category_keys(config),
        "labels": config_labels(config),
    }


@router.post("/config/posto/reset")
async def reset_config_posto():
    saved = save_config(app_context.database, default_config())
    config = {"grupos": saved["grupos"]}
    return {
        "grupos": config["grupos"],
        "categorias": config_category_keys(config),
        "labels": config_labels(config),
    }


# ─── Settings do módulo ──────────────────────────────────────────

@router.get("/config/settings")
async def get_module_settings():
    return load_settings(app_context.database)


@router.put("/config/settings")
async def update_module_settings(data: dict):
    try:
        saved = save_settings(app_context.database, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return saved


# ─── Mapeamento Cloudfy → Sistema ──────────────────────────────

@router.get("/config/mapeamento")
async def get_mapeamento():
    return {
        "mapeamento": load_cloudfy_mapeamento(app_context.database),
        "padrao": DEFAULT_CLOUDY_MAPEAMENTO,
    }


@router.put("/config/mapeamento")
async def update_mapeamento(data: dict):
    mapping = data.get("mapeamento")
    if not isinstance(mapping, dict):
        raise HTTPException(status_code=400, detail="Mapeamento deve ser um dict.")
    try:
        saved = save_cloudfy_mapeamento(app_context.database, mapping)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"mapeamento": saved}


# ─── Automação Cloudfy ──────────────────────────────────────────

@router.post("/automacao/listar")
async def automacao_listar():
    import asyncio as aio

    settings = load_settings(app_context.database)
    login = settings.get("cloudfy_login", "")
    senha = settings.get("cloudfy_senha", "")
    debug = settings.get("cloudfy_debug", False)

    if not login or not senha:
        raise HTTPException(
            status_code=400,
            detail="Credenciais Cloudfy nao configuradas. Acesse Configuracoes.",
        )

    loop = aio.get_running_loop()
    result = await loop.run_in_executor(
        None, listar_caixas_cloudfy, login, senha, debug
    )
    if "erro" in result:
        raise HTTPException(status_code=500, detail=result["erro"])
    return result


@router.post("/automacao/importar")
async def automacao_importar(data: dict):
    import asyncio as aio

    caixa_idx = data.get("caixa_idx")
    if caixa_idx is None:
        raise HTTPException(status_code=400, detail="Informe caixa_idx.")

    settings = load_settings(app_context.database)
    login = settings.get("cloudfy_login", "")
    senha = settings.get("cloudfy_senha", "")
    debug = settings.get("cloudfy_debug", False)

    if not login or not senha:
        raise HTTPException(
            status_code=400,
            detail="Credenciais Cloudfy nao configuradas.",
        )

    loop = aio.get_running_loop()
    result = await loop.run_in_executor(
        None, importar_caixa_cloudfy, login, senha, int(caixa_idx), debug
    )
    if "erro" in result:
        raise HTTPException(status_code=500, detail=result["erro"])
    return result


# ─── Validação de contagens ──────────────────────────────────────

@router.post("/validar-contagens")
async def validar_contagens(data: dict):
    contagens = data.get("contagens", [])
    settings = load_settings(app_context.database)
    errors = validate_contagens(contagens, settings.get("serial_200_mode", "obrigatorio_todas"))
    return {"valid": len(errors) == 0, "errors": errors}
