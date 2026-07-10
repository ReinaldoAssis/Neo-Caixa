from __future__ import annotations

from app.modules.conciliador.constants import (
    CATEGORIES_POSTO,
    CATEGORY_LABELS_POSTO,
    CATEGORIAS_RESTAURANTE,
    CATEGORIAS_RESTAURANTE_LABELS,
    CATEGORIA_CLASSIFICACAO,
    DENOMINATIONS,
    normalize_categories_posto,
    normalize_categories_restaurante,
    parse_money,
)


def format_money(value: object) -> str:
    amount = float(value or 0)
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def serials_valid(serials: list[str], qty_200: int) -> bool:
    import re
    if qty_200 <= 0:
        return True
    if len(serials) != qty_200:
        return False
    return all(re.fullmatch(r"\d{5}", serial or "") for serial in serials)


# ─── Posto ────────────────────────────────────────────────────────

def _apply_avulsos_posto(
    base_sistema: float, base_site: float, avulsos: list[dict], key: str
) -> tuple[float, float]:
    sistema = base_sistema
    site = base_site
    for avulso in (avulsos or []):
        if avulso.get("categoria_vinculada") == key:
            valor = float(avulso.get("valor", 0) or 0)
            delta = round(valor if avulso.get("tipo") == "RECEITA" else -valor, 2)
            coluna = avulso.get("coluna", "sistema")
            if coluna == "site":
                site = round(site + delta, 2)
            else:
                sistema = round(sistema + delta, 2)
    return sistema, site


def build_conciliation_rows_posto(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
    keys: list[str] | None = None,
    labels: dict[str, str] | None = None,
) -> list[dict]:
    keys = keys if keys is not None else CATEGORIES_POSTO
    labels = labels if labels is not None else CATEGORY_LABELS_POSTO
    categorias = normalize_categories_posto(categorias, keys)
    rows = []
    for key in keys:
        values = categorias.get(key, {})
        sistema = round(float(values.get("sistema", 0) or 0), 2)
        site = round(float(values.get("site", 0) or 0), 2)
        sistema, site = _apply_avulsos_posto(sistema, site, avulsos or [], key)
        diff = round(sistema - site, 2)
        rows.append({
            "key": key,
            "label": labels.get(key, key),
            "sistema": sistema,
            "site": site,
            "diferenca": diff,
            "status": "OK" if abs(diff) < 0.005 else "DIVERGENTE",
        })
    for avulso in (avulsos or []):
        if avulso.get("categoria_nova"):
            valor = float(avulso.get("valor", 0) or 0)
            label = avulso["categoria_nova"]
            delta = round(valor if avulso.get("tipo") == "RECEITA" else -valor, 2)
            coluna = avulso.get("coluna", "sistema")
            sistema_new = delta if coluna != "site" else 0.0
            site_new = delta if coluna == "site" else 0.0
            rows.append({
                "key": label,
                "label": label,
                "sistema": sistema_new,
                "site": site_new,
                "diferenca": round(sistema_new - site_new, 2),
                "status": "OK" if abs(sistema_new - site_new) < 0.005 else "DIVERGENTE",
            })
    return rows


def totals_posto(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
    keys: list[str] | None = None,
    labels: dict[str, str] | None = None,
) -> tuple[float, float, float]:
    rows = build_conciliation_rows_posto(categorias, avulsos, keys, labels)
    sistema = round(sum(float(row["sistema"]) for row in rows), 2)
    site = round(sum(float(row["site"]) for row in rows), 2)
    return sistema, site, round(sistema - site, 2)


# ─── Restaurante ──────────────────────────────────────────────────

def _apply_avulsos_restaurante(
    base_sistema: float, base_real: float, avulsos: list[dict], key: str
) -> tuple[float, float]:
    sistema = base_sistema
    real = base_real
    for avulso in (avulsos or []):
        if avulso.get("categoria_vinculada") == key:
            valor = float(avulso.get("valor", 0) or 0)
            delta = round(valor if avulso.get("tipo") == "RECEITA" else -valor, 2)
            coluna = avulso.get("coluna", "sistema")
            if coluna == "real":
                real = round(real + delta, 2)
            else:
                sistema = round(sistema + delta, 2)
    return sistema, real


def build_conciliation_rows_restaurante(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
    dinheiro_real: float = 0.0,
) -> list[dict]:
    categorias = normalize_categories_restaurante(categorias)
    rows = []
    for key in CATEGORIAS_RESTAURANTE:
        values = categorias.get(key, {})
        sistema = round(float(values.get("sistema", 0) or 0), 2)
        real = round(float(values.get("real", 0) or 0), 2)
        if key == "DINHEIRO":
            real = round(dinheiro_real, 2)
        sistema, real = _apply_avulsos_restaurante(sistema, real, avulsos or [], key)
        diff = round(sistema - real, 2)
        rows.append({
            "key": key,
            "label": CATEGORIAS_RESTAURANTE_LABELS[key],
            "classificacao": CATEGORIA_CLASSIFICACAO[key],
            "sistema": sistema,
            "real": real,
            "diferenca": diff,
            "status": "OK" if abs(diff) < 0.005 else "DIVERGENTE",
        })
    for avulso in (avulsos or []):
        if avulso.get("categoria_nova"):
            valor = float(avulso.get("valor", 0) or 0)
            label = avulso["categoria_nova"]
            delta = round(valor if avulso.get("tipo") == "RECEITA" else -valor, 2)
            coluna = avulso.get("coluna", "sistema")
            sistema_new = delta if coluna != "real" else 0.0
            real_new = delta if coluna == "real" else 0.0
            rows.append({
                "key": label,
                "label": label,
                "classificacao": "",
                "sistema": sistema_new,
                "real": real_new,
                "diferenca": round(sistema_new - real_new, 2),
                "status": "OK" if abs(sistema_new - real_new) < 0.005 else "DIVERGENTE",
            })
    return rows


def totals_restaurante(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
    dinheiro_real: float = 0.0,
) -> tuple[float, float, float]:
    rows = build_conciliation_rows_restaurante(categorias, avulsos, dinheiro_real)
    sistema = round(sum(float(row["sistema"]) for row in rows), 2)
    real = round(sum(float(row["real"]) for row in rows), 2)
    return sistema, real, round(sistema - real, 2)


# ─── Contagem de Dinheiro ────────────────────────────────────────

def compute_contagem_total(contagem: dict) -> float:
    notas = contagem.get("notas", {})
    total = sum(int(notas.get(str(d), 0) or 0) * d for d in DENOMINATIONS)
    total += parse_money(contagem.get("moedas", 0))
    total += parse_money(contagem.get("depositos", 0))
    return round(total, 2)


def consolidate_contagens(contagens: list[dict]) -> dict:
    geral = next((c for c in contagens if c.get("label") == "Geral"), None)
    if geral and geral.get("editado"):
        return dict(geral)

    total_notes: dict[str, int] = {str(d): 0 for d in DENOMINATIONS}
    total_moedas = 0.0
    total_depositos = 0.0
    all_serials: list[str] = []

    for c in contagens:
        notas = c.get("notas", {})
        for d in DENOMINATIONS:
            total_notes[str(d)] += int(notas.get(str(d), 0) or 0)
        total_moedas += parse_money(c.get("moedas", 0))
        total_depositos += parse_money(c.get("depositos", 0))
        all_serials.extend(c.get("seriais_200", []))

    grand = sum(total_notes[str(d)] * d for d in DENOMINATIONS) + total_moedas + total_depositos

    if geral:
        return {
            "id": geral.get("id"),
            "label": "Geral",
            "criado_em": geral.get("criado_em"),
            "notas": total_notes,
            "seriais_200": all_serials,
            "moedas": round(total_moedas, 2),
            "depositos": round(total_depositos, 2),
            "total": round(grand, 2),
        }

    return {
        "label": "Geral",
        "notas": total_notes,
        "seriais_200": all_serials,
        "moedas": round(total_moedas, 2),
        "depositos": round(total_depositos, 2),
        "total": round(grand, 2),
    }


def _serial_required(label: str, serial_mode: str) -> bool:
    if serial_mode == "opcional_todas":
        return False
    if serial_mode == "opcional_geral":
        return label != "Geral"
    return True


def validate_contagens(
    contagens: list[dict], serial_mode: str = "obrigatorio_todas"
) -> list[str]:
    errors = []
    for c in contagens:
        label = c.get("label", "Contagem")
        notas = c.get("notas", {})
        qty_200 = int(notas.get("200", 0) or 0)
        if qty_200 <= 0:
            continue
        if not _serial_required(label, serial_mode):
            continue
        if not serials_valid(c.get("seriais_200", []), qty_200):
            errors.append(
                f'{label}: Cada nota de R$ 200 precisa de um serial numerico com 5 digitos '
                f'(esperado {qty_200})'
            )
    return errors
