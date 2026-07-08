from __future__ import annotations

from app.modules.conciliador.constants import (
    CATEGORIES_POSTO,
    CATEGORY_LABELS_POSTO,
    normalize_text,
)

CONFIG_TABLE = "config_posto"
CONFIG_KEY = "posto_grupos"


# ─── Configuração padrão de grupos ────────────────────────────────
# Cada grupo (categoria) define:
#   - label: nome exibido
#   - sistema: lista de descrições brutas do relatório CAIXA que somam neste grupo
#   - pagbank: lista de pares {bandeira, forma} do relatório PagBank (coluna SITE)
#   - premmia: lista de "Forma de Pagamento" do relatório Premmia (coluna SITE)
#
# O usuário pode editar isso na tela de Configurações.

DEFAULT_GRUPOS: list[dict] = [
    {
        "key": "PREMMIA_CARTAO",
        "label": "PREMMIA CARTAO",
        "sistema": ["BR PREMMIA CARTAO", "CARTAO PREMIA"],
        "pagbank": [],
        "premmia": ["CARTAO APP", "CARTAO"],
    },
    {
        "key": "PREMMIA_PIX",
        "label": "PREMMIA PIX",
        "sistema": ["BR PREMMIA PIX"],
        "pagbank": [],
        "premmia": ["PIX"],
    },
    {
        "key": "PREMMIA_VALE",
        "label": "PREMMIA VALE",
        "sistema": ["BR PREMMIA VALE"],
        "pagbank": [],
        "premmia": ["VALE"],
    },
    {
        "key": "PREMMIA_CUPOM",
        "label": "PREMMIA CUPOM",
        "sistema": ["BR PREMMIA GENERICO", "BR PREMMIA GENERICO / CUPOM", "BR PREMMIA CUPOM"],
        "pagbank": [],
        "premmia": ["DESCONTO", "CUPOM"],
    },
    {
        "key": "FITCARD",
        "label": "FITCARD",
        "sistema": ["CARTAO FITCARD"],
        "pagbank": [],
        "premmia": [],
    },
    {
        "key": "PAG_PIX",
        "label": "PAG PIX",
        "sistema": ["PAG PIX"],
        "pagbank": [{"bandeira": "", "forma": "PIX"}],
        "premmia": [],
    },
    {
        "key": "AMEX",
        "label": "AMERICAN EXP",
        "sistema": ["POS PAGSEGURO AMERICAN EXPRESS", "SMART PAGSEGURO AMERICAN EXPRESS"],
        "pagbank": [
            {"bandeira": "AMEX", "forma": "CREDITO"},
            {"bandeira": "AMERICAN EXPRESS", "forma": "CREDITO"},
        ],
        "premmia": [],
    },
    {
        "key": "ELO_CREDITO",
        "label": "ELO CREDITO",
        "sistema": ["POS PAGSEGURO ELO CRED", "SMART PAGSEGURO ELO CRED"],
        "pagbank": [{"bandeira": "ELO", "forma": "CREDITO"}],
        "premmia": [],
    },
    {
        "key": "ELO_DEBITO",
        "label": "ELO DEBITO",
        "sistema": ["POS PAGSEGURO ELO DEBITO", "SMART PAGSEGURO ELO DEBI"],
        "pagbank": [{"bandeira": "ELO", "forma": "DEBITO"}],
        "premmia": [],
    },
    {
        "key": "MASTERCARD_CREDITO",
        "label": "MASTERCARD CREDITO",
        "sistema": ["POS PAGSEGURO MASTER.CRE", "SMART PAGSEGURO MASTER.C"],
        "pagbank": [{"bandeira": "MASTERCARD", "forma": "CREDITO"}],
        "premmia": [],
    },
    {
        "key": "MASTERCARD_DEBITO",
        "label": "MASTERCARD DEBITO",
        "sistema": ["POS PAGSEGURO MASTER.DEB", "SMART PAGSEGURO MASTER.D"],
        "pagbank": [{"bandeira": "MASTERCARD", "forma": "DEBITO"}],
        "premmia": [],
    },
    {
        "key": "VISA_CREDITO",
        "label": "VISA CREDITO",
        "sistema": ["POS PAGSEGURO VISA CREDI", "SMART PAGSEGURO VISA CRE"],
        "pagbank": [{"bandeira": "VISA", "forma": "CREDITO"}],
        "premmia": [],
    },
    {
        "key": "VISA_DEBITO",
        "label": "VISA DEBITO",
        "sistema": ["POS PAGSEGURO VISA DEBIT", "SMART PAGSEGURO VISA DEB"],
        "pagbank": [{"bandeira": "VISA", "forma": "DEBITO"}],
        "premmia": [],
    },
]

# Campos informativos (não são grupos de conciliação)
INFO_FIELDS_DEFAULT = {
    "SANGRIA": "sangria",
    "NOTAS A PRAZO": "notas_a_prazo",
    "DESPESAS DO POSTO": "despesas",
}


def default_config() -> dict:
    return {
        "grupos": [dict(g, sistema=list(g["sistema"]),
                        pagbank=[dict(p) for p in g["pagbank"]],
                        premmia=list(g["premmia"]))
                   for g in DEFAULT_GRUPOS],
    }


# ─── Persistência ────────────────────────────────────────────────

def load_config(database) -> dict:
    doc = None
    try:
        results = database.search(CONFIG_TABLE, {"key": CONFIG_KEY})
        doc = results[0] if results else None
    except Exception:
        doc = None
    if not doc or not doc.get("grupos"):
        return default_config()
    return {"grupos": doc["grupos"]}


def save_config(database, config: dict) -> dict:
    grupos = _validate_grupos(config.get("grupos"))
    payload = {"key": CONFIG_KEY, "grupos": grupos}
    existing = database.search(CONFIG_TABLE, {"key": CONFIG_KEY})
    if existing:
        raw_id = getattr(existing[0], "doc_id", None)
        if raw_id is None:
            raw_id = existing[0].get("id")
        database.update(CONFIG_TABLE, str(raw_id), payload)
    else:
        database.insert(CONFIG_TABLE, payload)
    return {"grupos": grupos}


def _validate_grupos(grupos: object) -> list[dict]:
    if not isinstance(grupos, list) or not grupos:
        raise ValueError("Configuracao invalida: 'grupos' deve ser uma lista nao vazia.")
    out = []
    seen = set()
    for g in grupos:
        if not isinstance(g, dict):
            raise ValueError("Cada grupo deve ser um objeto.")
        key = str(g.get("key", "")).strip().upper().replace(" ", "_")
        if not key:
            raise ValueError("Grupo sem 'key'.")
        if key in seen:
            raise ValueError(f"Grupo duplicado: {key}")
        seen.add(key)
        label = str(g.get("label", key)).strip() or key
        sistema = [normalize_text(s) for s in (g.get("sistema") or []) if str(s).strip()]
        premmia = [normalize_text(s) for s in (g.get("premmia") or []) if str(s).strip()]
        pagbank = []
        for p in (g.get("pagbank") or []):
            if not isinstance(p, dict):
                continue
            pagbank.append({
                "bandeira": normalize_text(p.get("bandeira", "")),
                "forma": normalize_text(p.get("forma", "")),
            })
        out.append({
            "key": key,
            "label": label,
            "sistema": sistema,
            "pagbank": pagbank,
            "premmia": premmia,
        })
    return out


# ─── Derivados usados pelos parsers/serviços ──────────────────────

def config_category_keys(config: dict) -> list[str]:
    return [g["key"] for g in config["grupos"]]


def config_labels(config: dict) -> dict[str, str]:
    return {g["key"]: g.get("label", g["key"]) for g in config["grupos"]}


def build_system_map(config: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for g in config["grupos"]:
        for desc in g.get("sistema", []):
            mapping[normalize_text(desc)] = g["key"]
    return mapping


def build_premmia_map(config: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for g in config["grupos"]:
        for forma in g.get("premmia", []):
            mapping[normalize_text(forma)] = g["key"]
    return mapping


def build_pagbank_map(config: dict) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    for g in config["grupos"]:
        for p in g.get("pagbank", []):
            mapping[(normalize_text(p.get("bandeira", "")), normalize_text(p.get("forma", "")))] = g["key"]
    return mapping
