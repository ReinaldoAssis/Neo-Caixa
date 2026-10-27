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


# ─── Settings do módulo (aplica a posto e restaurante) ───────────

SETTINGS_KEY = "modulo_settings"

CONTAGEM_TAB_BEHAVIORS = ("icone", "icone_fixo")

# Comportamento da obrigatoriedade do serial das notas de R$ 200
#   obrigatorio_todas -> serial obrigatorio em todas as contagens
#   opcional_geral    -> serial opcional apenas na contagem Geral (obrigatorio nas demais)
#   opcional_todas    -> serial opcional em todas as contagens
SERIAL_200_MODES = ("obrigatorio_todas", "opcional_geral", "opcional_todas")

# Categorias de despesa (Tipo) usadas no pagamento do gerenciador financeiro.
# `codigo` é o identificador do Cloudfy; `descricao` é o texto procurado no
# selectize. A lista é editável em Configurações > Financeiro.
DEFAULT_FINANCEIRO_CATEGORIAS: list[dict[str, str]] = [
    {"codigo": "78", "descricao": "02.04.23 Vale Transporte"},
    {"codigo": "54", "descricao": "02.03.01 Fornecedores"},
    {"codigo": "56", "descricao": "02.04.01 Adiantamento Salarial"},
    {"codigo": "74", "descricao": "02.04.19 Salarios / Remuneracoes"},
    {"codigo": "79", "descricao": "02.04.99 Outras Despesas c/ Pessoal"},
    {"codigo": "115", "descricao": "02.08.99 Outras Despesas Operacionais"},
    {"codigo": "151", "descricao": "02.12.99 Outras Despesas c/ Reposicoes"},
    {"codigo": "145", "descricao": "02.11.99 Outras Despesas c/ Manutencoes"},
    {"codigo": "163", "descricao": "02.99 SNOP - OUTRAS SAIDAS NAO OPERACIONAIS"},
]

DEFAULT_FINANCEIRO_CATEGORIA = "54"

# Valores usados pelo atalho de lançamentos financeiros do caixa restaurante.
# São textos procurados nas opções do selectize do Cloudfy.
DEFAULT_FINANCEIRO = {
    "financeiro_origem": "CAIXA ADM",
    "financeiro_destino": "MOEDAS",
    "financeiro_descricao_moedas": "MOEDAS",
    "financeiro_conta": "CAIXA ADM",
    "financeiro_centro_custo": "LAGOA CAFE CONVENIENCIA",
    "financeiro_tipo_documento": "DINHEIRO",
    "financeiro_fornecedor": "",
}

DEFAULT_SETTINGS = {
    "contagem_tab_behavior": "icone",
    "serial_200_mode": "obrigatorio_todas",
    "cloudfy_login": "",
    "cloudfy_senha": "",
    "cloudfy_debug": False,
    "otimizar_automacao": True,
    "relatorio_csv_dir": "",
    "financeiro_categorias": DEFAULT_FINANCEIRO_CATEGORIAS,
    "financeiro_categoria_padrao": DEFAULT_FINANCEIRO_CATEGORIA,
    **DEFAULT_FINANCEIRO,
}


def default_financeiro_categorias() -> list[dict[str, str]]:
    return [dict(categoria) for categoria in DEFAULT_FINANCEIRO_CATEGORIAS]


def _categoria(raw) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    codigo = str(raw.get("codigo", "")).strip()
    descricao = " ".join(str(raw.get("descricao", "")).split())
    if not codigo.isdigit() or not descricao:
        return None
    return {"codigo": codigo, "descricao": descricao}


def normalizar_categorias_financeiro(raw) -> list[dict[str, str]]:
    """Normaliza a lista salva; lista inválida/vazia cai no default."""
    if not isinstance(raw, list):
        return default_financeiro_categorias()
    out: list[dict[str, str]] = []
    vistos: set[str] = set()
    for item in raw:
        categoria = _categoria(item)
        if categoria is None or categoria["codigo"] in vistos:
            continue
        vistos.add(categoria["codigo"])
        out.append(categoria)
    return out or default_financeiro_categorias()


def validar_categorias_financeiro(raw) -> list[dict[str, str]]:
    """Valida a lista enviada pela UI; erro explícito para dado inválido."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("Informe pelo menos uma categoria de despesa.")
    out: list[dict[str, str]] = []
    vistos: set[str] = set()
    for posicao, item in enumerate(raw, start=1):
        categoria = _categoria(item)
        if categoria is None:
            raise ValueError(
                f"Categoria {posicao}: codigo deve ser inteiro e descricao obrigatoria."
            )
        if categoria["codigo"] in vistos:
            raise ValueError(f"Codigo de categoria duplicado: {categoria['codigo']}.")
        vistos.add(categoria["codigo"])
        out.append(categoria)
    return out


def categoria_por_codigo(
    categorias: list[dict[str, str]] | None, codigo: str
) -> dict[str, str] | None:
    codigo = str(codigo or "").strip()
    for categoria in categorias or []:
        if str(categoria.get("codigo")) == codigo:
            return categoria
    return None


def _padrao_valido(categorias: list[dict[str, str]], codigo: str) -> str:
    if categoria_por_codigo(categorias, codigo):
        return str(codigo)
    if categoria_por_codigo(categorias, DEFAULT_FINANCEIRO_CATEGORIA):
        return DEFAULT_FINANCEIRO_CATEGORIA
    return categorias[0]["codigo"]


def default_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    settings["financeiro_categorias"] = default_financeiro_categorias()
    return settings


def load_settings(database) -> dict:
    doc = None
    try:
        results = database.search(CONFIG_TABLE, {"key": SETTINGS_KEY})
        doc = results[0] if results else None
    except Exception:
        doc = None
    settings = default_settings()
    if doc:
        behavior = doc.get("contagem_tab_behavior")
        if behavior in CONTAGEM_TAB_BEHAVIORS:
            settings["contagem_tab_behavior"] = behavior
        serial_mode = doc.get("serial_200_mode")
        if serial_mode in SERIAL_200_MODES:
            settings["serial_200_mode"] = serial_mode
        settings["cloudfy_login"] = doc.get("cloudfy_login", "")
        settings["cloudfy_senha"] = doc.get("cloudfy_senha", "")
        settings["cloudfy_debug"] = doc.get("cloudfy_debug", False)
        settings["otimizar_automacao"] = doc.get("otimizar_automacao", True)
        settings["relatorio_csv_dir"] = doc.get("relatorio_csv_dir", "")
        for chave, padrao in DEFAULT_FINANCEIRO.items():
            settings[chave] = doc.get(chave, padrao)
        categorias = normalizar_categorias_financeiro(
            doc.get("financeiro_categorias")
        )
        settings["financeiro_categorias"] = categorias
        settings["financeiro_categoria_padrao"] = _padrao_valido(
            categorias,
            str(doc.get("financeiro_categoria_padrao") or "").strip(),
        )
    return settings


def save_settings(database, data: dict) -> dict:
    data = data or {}
    settings = load_settings(database)

    if "contagem_tab_behavior" in data:
        behavior = data.get("contagem_tab_behavior")
        if behavior not in CONTAGEM_TAB_BEHAVIORS:
            raise ValueError(
                f"contagem_tab_behavior invalido. Use um de: {', '.join(CONTAGEM_TAB_BEHAVIORS)}"
            )
        settings["contagem_tab_behavior"] = behavior

    if "serial_200_mode" in data:
        serial_mode = data.get("serial_200_mode")
        if serial_mode not in SERIAL_200_MODES:
            raise ValueError(
                f"serial_200_mode invalido. Use um de: {', '.join(SERIAL_200_MODES)}"
            )
        settings["serial_200_mode"] = serial_mode

    if "cloudfy_login" in data:
        settings["cloudfy_login"] = str(data.get("cloudfy_login", ""))
    if "cloudfy_senha" in data:
        settings["cloudfy_senha"] = str(data.get("cloudfy_senha", ""))
    if "cloudfy_debug" in data:
        settings["cloudfy_debug"] = bool(data.get("cloudfy_debug", False))
    if "otimizar_automacao" in data:
        settings["otimizar_automacao"] = bool(data.get("otimizar_automacao", True))
    if "relatorio_csv_dir" in data:
        settings["relatorio_csv_dir"] = str(data.get("relatorio_csv_dir", "")).strip()
    for chave in DEFAULT_FINANCEIRO:
        if chave in data:
            settings[chave] = str(data.get(chave, "")).strip()

    if "financeiro_categorias" in data:
        settings["financeiro_categorias"] = validar_categorias_financeiro(
            data.get("financeiro_categorias")
        )
    if "financeiro_categoria_padrao" in data:
        codigo = str(data.get("financeiro_categoria_padrao") or "").strip()
        if not categoria_por_codigo(settings["financeiro_categorias"], codigo):
            raise ValueError(
                f"financeiro_categoria_padrao '{codigo}' nao existe na lista de categorias."
            )
        settings["financeiro_categoria_padrao"] = codigo

    padrao = str(settings.get("financeiro_categoria_padrao") or "")
    if not categoria_por_codigo(settings["financeiro_categorias"], padrao):
        raise ValueError(
            f"A categoria padrao '{padrao}' nao pode ser removida sem trocar o padrao."
        )

    payload = {"key": SETTINGS_KEY, **settings}
    existing = database.search(CONFIG_TABLE, {"key": SETTINGS_KEY})
    if existing:
        raw_id = getattr(existing[0], "doc_id", None)
        if raw_id is None:
            raw_id = existing[0].get("id")
        database.update(CONFIG_TABLE, str(raw_id), payload)
    else:
        database.insert(CONFIG_TABLE, payload)
    return settings


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


# ─── Mapeamento Cloudfy → Sistema (restaurante) ─────────────────

CLOUDY_MAPEAMENTO_KEY = "cloudfy_mapeamento"

DEFAULT_CLOUDY_MAPEAMENTO: dict[str, str] = {
    "PIX ADQUIRENTE": "PIX",
    "ELO DEBITO": "ELO_DEBITO",
    "MAESTRO": "MAESTRO",
    "VC ELECTRON": "VC_ELECTRON",
    "AMEX": "AMEX",
    "ELO CR": "ELO_CR",
    "MASTERCARD": "MASTERCARD",
    "VISA": "VISA",
}


def load_cloudfy_mapeamento(database) -> dict[str, str]:
    doc = None
    try:
        results = database.search(CONFIG_TABLE, {"key": CLOUDY_MAPEAMENTO_KEY})
        doc = results[0] if results else None
    except Exception:
        doc = None
    if doc and isinstance(doc.get("map"), dict):
        return doc["map"]
    return dict(DEFAULT_CLOUDY_MAPEAMENTO)


def save_cloudfy_mapeamento(database, mapping: dict[str, str]) -> dict[str, str]:
    if not isinstance(mapping, dict):
        raise ValueError("Mapeamento deve ser um dict {subtipo_cloudfy: categoria_sistema}.")
    payload = {"key": CLOUDY_MAPEAMENTO_KEY, "map": mapping}
    existing = database.search(CONFIG_TABLE, {"key": CLOUDY_MAPEAMENTO_KEY})
    if existing:
        raw_id = getattr(existing[0], "doc_id", None)
        if raw_id is None:
            raw_id = existing[0].get("id")
        database.update(CONFIG_TABLE, str(raw_id), payload)
    else:
        database.insert(CONFIG_TABLE, payload)
    return mapping
