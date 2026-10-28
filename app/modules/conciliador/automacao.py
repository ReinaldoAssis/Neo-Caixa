"""
Bridge entre a API do conciliador e o scraper Playwright do Cloudfy.

Aqui ficam apenas operações de página (recebem ``page``/``context`` já prontos)
e parsers puros/testáveis. O ciclo de vida do navegador (sessão persistente,
aquecimento, troca headless↔headed) mora em ``automacao_sessao.py``.

As funções públicas continuam síncronas e delegam para a sessão singleton.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from app.core.logger import logger
from app.modules.conciliador.constants import parse_money
from app.modules.conciliador.financeiro import (
    TIPO_DESPESA,
    TIPO_MOEDAS,
    resolver_categoria,
)

CLOUDY_BASE = "https://app.cloudfy.net.br/site"
LOGIN_URL = f"{CLOUDY_BASE}/#/login"
CONCILIADOR_URL = f"{CLOUDY_BASE}/#/H02SF0108B"
FINANCEIRO_URL = f"{CLOUDY_BASE}/#/H02SF0201E"
HOME_URL = f"{CLOUDY_BASE}/#/"

RELATORIO_DESCONTO_MENU = "Relatório de desconto"
RELATORIO_POR_CUPOM = "Relatório por cupom"
FORMA_VENDA_A_PRAZO = "venda a prazo"

TIMEOUT_PADRAO_MS = 15000
TIMEOUT_CURTO_MS = 8000
TIMEOUT_SELECT_MS = 2500


# ─── Models ────────────────────────────────────────────────────────

@dataclass
class CaixaResumo:
    data: str = ""
    pdv: str = ""
    turno: str = ""
    horario_abertura: str = ""
    horario_fechamento: str = ""
    movto: str = ""
    status: str = ""
    valor: str = ""
    row_index: int = -1


@dataclass
class PagamentoCartao:
    tipo: str = ""
    bandeira: str = ""
    subtipo: str = ""
    valor_vndpos: str = ""
    valor_vndtef: str = ""
    valor_total: str = ""
    quantidade: str = ""


@dataclass
class CaixaDetalhe:
    resumo: CaixaResumo = field(default_factory=CaixaResumo)
    dinheiro: str = ""
    pagamentos: list[PagamentoCartao] = field(default_factory=list)


@dataclass
class Desconto:
    tipo: str = ""
    motivo: str = ""
    data: str = ""
    caixa: str = ""
    cupom: str = ""
    qtde_itens: str = ""
    valor: float = 0.0
    cliente: str = ""
    forma_pagamento: str = ""


# ─── Helpers ───────────────────────────────────────────────────────

def _parse_brl(value: str) -> float:
    cleaned = value.replace("R$", "").replace(" ", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return 0.0


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _cell_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return _parse_brl(str(value))


def _norm(value: Any) -> str:
    """Normaliza texto vindo do Cloudfy/cache para comparação de chaves."""
    return " ".join(str(value or "").split()).strip()


_HEADER_ALIASES = {
    "tipo": "tipo",
    "motivo": "motivo",
    "data": "data",
    "caixa": "caixa",
    "cupom": "cupom",
    "qtde. itens": "qtde_itens",
    "qtde itens": "qtde_itens",
    "valor": "valor",
    "cliente": "cliente",
    "forma de pagamento": "forma_pagamento",
}


def _map_header(name: str) -> str | None:
    normalized = " ".join(str(name or "").strip().lower().split())
    if normalized in _HEADER_ALIASES:
        return _HEADER_ALIASES[normalized]
    if normalized.startswith("qtde"):
        return "qtde_itens"
    if normalized.startswith("forma"):
        return "forma_pagamento"
    return None


def parse_descontos_xlsx(path: str) -> list[dict[str, Any]]:
    """Le o XLSX exportado pelo Cloudfy e retorna apenas cupons 'Venda a prazo'."""
    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    worksheet = workbook.worksheets[0]
    rows = worksheet.iter_rows(values_only=True)

    header: dict[str, int] = {}
    parsed: list[dict[str, Any]] = []

    for raw_row in rows:
        cells = [_cell_str(c) for c in raw_row]
        if not header:
            candidate = {
                field_name: idx
                for idx, cell in enumerate(cells)
                if (field_name := _map_header(cell)) is not None
            }
            if "cupom" in candidate and "data" in candidate:
                header = candidate
            continue

        if not any(cells):
            continue

        def get(field_name: str) -> Any:
            idx = header.get(field_name)
            if idx is None or idx >= len(raw_row):
                return ""
            return raw_row[idx]

        forma = _cell_str(get("forma_pagamento"))
        if forma.strip().lower() != FORMA_VENDA_A_PRAZO:
            continue

        parsed.append(asdict(Desconto(
            tipo=_cell_str(get("tipo")),
            motivo=_cell_str(get("motivo")),
            data=_cell_str(get("data")),
            caixa=_cell_str(get("caixa")),
            cupom=_cell_str(get("cupom")),
            qtde_itens=_cell_str(get("qtde_itens")),
            valor=_cell_float(get("valor")),
            cliente=_cell_str(get("cliente")),
            forma_pagamento=forma,
        )))

    workbook.close()
    return parsed


# ─── Chaves / datas / turnos (puro, testável) ─────────────────────

_DATA_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})")
_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_TURNO_RE = re.compile(r"\bT\s*([12])\b", re.IGNORECASE)


def normalizar_data_iso(raw: str) -> str | None:
    """Converte 'dd/mm/yyyy', 'dd/mm/yy' ou 'yyyy-mm-dd...' para ISO."""
    text = _norm(raw)
    if not text:
        return None
    iso = _ISO_RE.match(text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    br = _DATA_RE.match(text)
    if br:
        dia, mes, ano = int(br.group(1)), int(br.group(2)), int(br.group(3))
        if ano < 100:
            ano += 2000
        return f"{ano:04d}-{mes:02d}-{dia:02d}"
    return None


def turno_de_caixa(caixa: CaixaResumo | dict) -> int | None:
    """Turno pela coluna ``turno``; fallback para o texto de ``movto`` (T1/T2)."""
    turno = caixa.get("turno") if isinstance(caixa, dict) else caixa.turno
    digits = re.sub(r"\D", "", str(turno or ""))
    if digits in ("1", "2"):
        return int(digits)
    movto = caixa.get("movto") if isinstance(caixa, dict) else caixa.movto
    match = _TURNO_RE.search(str(movto or ""))
    if match:
        return int(match.group(1))
    return None


def chave_de_caixa(caixa: CaixaResumo | dict) -> dict[str, Any]:
    def get(name: str) -> str:
        return _norm(caixa.get(name) if isinstance(caixa, dict) else getattr(caixa, name, ""))

    return {
        "data": get("data"),
        "pdv": get("pdv"),
        "turno": get("turno"),
        "movto": get("movto"),
    }


def _chave_confere(caixa: CaixaResumo, chave: dict) -> bool:
    return all(
        _norm(getattr(caixa, campo, "")) == _norm(chave.get(campo, ""))
        for campo in ("data", "pdv", "turno", "movto")
    )


def validar_data_caixa(caixa: CaixaResumo, data_iso: str | None) -> str | None:
    if not data_iso:
        return None
    iso = normalizar_data_iso(caixa.data)
    if not iso:
        return f"Data do caixa invalida: {caixa.data!r}."
    if iso != data_iso:
        return (
            f"Caixa de {caixa.data} (turno {caixa.turno or '-'} / PDV "
            f"{caixa.pdv or '-'}) fora da data da conciliacao ({data_iso})."
        )
    return None


def resolver_caixas(
    caixas: list[CaixaResumo],
    chaves: list[dict],
    data_iso: str | None = None,
) -> tuple[list[tuple[CaixaResumo, dict]], list[dict]]:
    """Resolve chaves estáveis (data/pdv/turno/movto) na lista recém-lida.

    Devolve ``(resolvidos, erros)``. ``row_index`` serve só como desempate
    quando a chave exata não existe (cache antigo do front).
    """
    resolvidos: list[tuple[CaixaResumo, dict]] = []
    erros: list[dict] = []
    usados: set[int] = set()
    por_row_index = {caixa.row_index: caixa for caixa in caixas}

    for chave in chaves or []:
        if not isinstance(chave, dict):
            erros.append({"chave": chave, "ok": False, "erro": "Chave invalida."})
            continue

        casada: CaixaResumo | None = None
        for caixa in caixas:
            if casada is None and id(caixa) not in usados and _chave_confere(caixa, chave):
                casada = caixa

        if casada is None:
            row_index = chave.get("row_index")
            if isinstance(row_index, int):
                candidato = por_row_index.get(row_index)
                if (
                    candidato is not None
                    and id(candidato) not in usados
                    and _norm(candidato.data) == _norm(chave.get("data"))
                ):
                    casada = candidato

        if casada is None:
            erros.append({
                "chave": chave,
                "ok": False,
                "erro": "Caixa nao encontrado na lista atual do Cloudfy. Atualize a lista.",
            })
            continue

        usados.add(id(casada))
        erro_data = validar_data_caixa(casada, data_iso)
        if erro_data:
            erros.append({"chave": chave, "ok": False, "erro": erro_data})
            continue

        resolvidos.append((casada, chave))

    return resolvidos, erros


# ─── Parsers de linhas extraídas por JS ────────────────────────────

def parse_caixas_rows(rows: list[dict] | None) -> list[CaixaResumo]:
    caixas: list[CaixaResumo] = []
    for item in rows or []:
        cells = [_cell_str(c) for c in (item.get("cells") or [])]
        if len(cells) < 4:
            continue
        caixas.append(CaixaResumo(
            data=cells[0] if len(cells) > 0 else "",
            pdv=cells[1] if len(cells) > 1 else "",
            turno=cells[2] if len(cells) > 2 else "",
            horario_abertura=cells[3] if len(cells) > 3 else "",
            horario_fechamento=cells[4] if len(cells) > 4 else "",
            movto=cells[5] if len(cells) > 5 else "",
            status=cells[6] if len(cells) > 6 else "",
            valor=cells[9] if len(cells) > 9 else "",
            row_index=int(item.get("i", len(caixas))),
        ))
    return caixas


def parse_pagamentos_rows(rows: list[list[str]] | None) -> list[PagamentoCartao]:
    pagamentos: list[PagamentoCartao] = []
    for raw in rows or []:
        texts = [_cell_str(c) for c in raw]
        if len(texts) >= 4:
            pagamentos.append(PagamentoCartao(
                tipo=texts[0] if len(texts) > 0 else "",
                bandeira=texts[1] if len(texts) > 1 else "",
                subtipo=texts[2] if len(texts) > 2 else "",
                valor_vndpos=texts[4] if len(texts) > 4 else "",
                valor_vndtef=texts[5] if len(texts) > 5 else "",
                valor_total=texts[6] if len(texts) > 6 else "",
                quantidade=texts[7] if len(texts) > 7 else "",
            ))
    return pagamentos


def parse_dinheiro_rows(rows: list[dict] | None) -> str:
    for item in rows or []:
        forma = _norm(item.get("forma")).upper()
        if forma == "DINHEIRO":
            return _norm(item.get("valor"))
    return ""


# ─── Timings ──────────────────────────────────────────────────────

_TEMPOS: dict[str, float] = {}


def _marcar(etapa: str, inicio: float) -> None:
    _TEMPOS[etapa] = round(time.perf_counter() - inicio, 3)
    logger.info("[automacao] %s: %.2fs", etapa, _TEMPOS[etapa])


def tempos_recentes() -> dict[str, float]:
    return dict(_TEMPOS)


def zerar_tempos() -> None:
    _TEMPOS.clear()


# ─── JS de extração / prontidão ───────────────────────────────────

JS_LISTAR = """
() => Array.from(document.querySelectorAll('tr[ng-repeat*="sknDataProviderFiltered"]'))
    .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length))
    .map((row, i) => ({
        i,
        cells: Array.from(row.querySelectorAll('td[ng-repeat*="Column in ::Columns"]'))
            .filter(td => !(td.className || '').includes('ng-hide'))
            .map(td => (td.textContent || '').trim()),
    }))
"""

JS_PAGAMENTOS = """
() => Array.from(document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]'))
    .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length))
    .map(row => Array.from(row.querySelectorAll('td')).map(td => {
        const inp = td.querySelector(
            'input[ng-model*="CC078_VL_VNDPOS"], '
            + 'input[ng-model*="CC078_VL_VNDTEF"], '
            + 'input[ng-model*="CC078_IT_QTPAGAME"]'
        );
        return inp ? (inp.value || '').trim() : (td.textContent || '').trim();
    }))
"""

JS_DINHEIRO = """
() => Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'))
    .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length))
    .map(row => {
        const td = row.querySelector('td');
        const span = row.querySelector('span[ng-bind*="CC077_VL_CALC"]');
        return {
            forma: td ? (td.textContent || '').trim() : '',
            valor: span ? (span.textContent || '').trim() : '',
        };
    })
"""

JS_SHELL_CONCILIADOR = """
() => !!document.querySelector('#inputPassword')
    || !!document.querySelector('tr[ng-repeat*="sknDataProviderFiltered"]')
    || Array.from(document.querySelectorAll('a'))
        .some(a => a.textContent.trim() === 'Mostrar todos')
"""

JS_MENU_DESCONTO = """
() => !!document.querySelector('.selectize-control')
    || Array.from(document.querySelectorAll('a'))
        .some(a => a.textContent.includes('desconto'))
"""

JS_MOSTRAR_TODOS = """
() => {
    const el = Array.from(document.querySelectorAll('a'))
        .find(a => a.textContent.trim() === 'Mostrar todos');
    if (!el) return false;
    el.click();
    return true;
}
"""

JS_LOGIN_OK = "() => !document.querySelector('#inputPassword')"

JS_CONCILIADOR_LINHAS = """
() => {
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="sknDataProviderFiltered"]'))
        .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length));
    if (!rows.length) return false;
    return rows.every(row => {
        const cells = row.querySelectorAll('td[ng-repeat*="Column in ::Columns"]');
        if (cells.length < 7) return false;
        return Array.from(cells).some(td => (td.textContent || '').trim().length > 0);
    });
}
"""

JS_DETALHE_PRONTO = """
() => {
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'))
        .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length));
    if (!rows.length) return false;
    return rows.every(row => (row.textContent || '').trim().length > 0);
}
"""

JS_DINHEIRO_PRONTO = """
() => {
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'))
        .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length));
    return rows.length > 0 && rows.every(row => (row.textContent || '').trim().length > 0);
}
"""

JS_CONTAR_FORMAS = """
() => Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'))
    .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length)).length
"""

JS_CONTAR_PAGAMENTOS = """
() => Array.from(document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]'))
    .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length)).length
"""

JS_CONCILIACAO_PRONTA = """
() => {
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]'))
        .filter(row => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length));
    if (!rows.length) return false;
    return rows.every(row => row.querySelectorAll('td').length >= 8);
}
"""

JS_LISTA_PRONTA = """
() => {
    const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="sknDataProviderFiltered"]')).some(vis);
    if (rows) return true;
    const detalhe = Array.from(document.querySelectorAll('a')).filter(vis)
        .some(a => (a.textContent || '').toUpperCase().includes('CONCILIAR CART'));
    const conc = Array.from(document.querySelectorAll('a')).filter(vis)
        .some(a => (a.textContent || '').trim().toUpperCase() === 'CONFIRMAR');
    if (detalhe || conc) return false;
    return Array.from(document.querySelectorAll('a, button')).filter(vis)
        .some(el => ['BUSCAR', 'MOSTRAR TODOS'].includes((el.textContent || '').trim().toUpperCase()));
}
"""

JS_DETALHE_ABERTO = """
() => Array.from(document.querySelectorAll('a'))
    .filter(a => !!(a.offsetWidth || a.offsetHeight || a.getClientRects().length))
    .some(a => (a.textContent || '').toUpperCase().includes('CONCILIAR CART'))
"""

JS_CONCILIACAO_ABERTA = """
() => Array.from(document.querySelectorAll('a'))
    .filter(a => !!(a.offsetWidth || a.offsetHeight || a.getClientRects().length))
    .some(a => (a.textContent || '').trim().toUpperCase() === 'CONFIRMAR')
"""

JS_DETALHE_OU_LISTA = """
() => {
    const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    const lista = Array.from(document.querySelectorAll('tr[ng-repeat*="sknDataProviderFiltered"]')).some(vis);
    const detalhe = Array.from(document.querySelectorAll('a'))
        .filter(vis)
        .some(a => (a.textContent || '').toUpperCase().includes('CONCILIAR CART'));
    return lista || detalhe;
}
"""

JS_CLICAR_MENU = """
(nome) => {
    const links = Array.from(document.querySelectorAll('a'));
    let el = links.find(a => a.textContent.trim() === nome);
    if (!el) el = links.find(a => a.textContent.includes(nome));
    if (el) { el.click(); return true; }
    return false;
}
"""

JS_FINANCEIRO_PRONTO = """
() => Array.from(document.querySelectorAll('button.md-btn')).some((b) => {
    const t = (b.textContent || '').replace(/\\s+/g, ' ').trim().toUpperCase();
    const visivel = !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length);
    return visivel && t.startsWith('NOVO');
})
"""

JS_SELECT_OPTION = """
({skn, textos}) => {
    const w = document.querySelector(`[skn-id="${skn}"]`);
    if (!w) return false;
    const alvos = (Array.isArray(textos) ? textos : [textos])
        .map((t) => String(t || '').replace(/\\s+/g, ' ').trim().toUpperCase())
        .filter(Boolean);
    if (!alvos.length) return false;
    return Array.from(w.querySelectorAll('.selectize-dropdown .option')).some(o => {
        const t = (o.textContent || '').replace(/\\s+/g, ' ').trim().toUpperCase();
        return alvos.some((alvo) => (
            t === alvo
            || t.endsWith(' : ' + alvo)
            || t.endsWith(' - ' + alvo)
            || t.startsWith(alvo + ' : ')
            || t.startsWith(alvo + ' - ')
            || t.includes(alvo)
        ));
    });
}
"""

JS_SELECT_SELECIONADO = """
({skn, textos}) => {
    const w = document.querySelector(`[skn-id="${skn}"]`);
    if (!w) return false;
    const alvos = (Array.isArray(textos) ? textos : [textos])
        .map((t) => String(t || '').replace(/\\s+/g, ' ').trim().toUpperCase())
        .filter(Boolean);
    if (!alvos.length) return false;
    return Array.from(w.querySelectorAll('.selectize-input .item')).some(i => {
        const t = (i.textContent || '').replace(/\\s+/g, ' ').trim().toUpperCase();
        return alvos.some((alvo) => (
            t === alvo
            || t.endsWith(' : ' + alvo)
            || t.endsWith(' - ' + alvo)
            || t.includes(alvo)
        ));
    });
}
"""


def _url_login(url: str) -> bool:
    return "login" in str(url or "").lower()


async def tem_form_login(page) -> bool:
    """True quando a tela de login está visível (SPA pode não mudar a URL)."""
    try:
        return await page.locator("#inputPassword").count() > 0
    except Exception:
        return False


# ─── Operações de página ──────────────────────────────────────────

async def esperar(page, expressao: str, timeout_ms: int = TIMEOUT_PADRAO_MS, etapa: str = "etapa") -> None:
    """Espera um sinal de dado (JS) em vez de tempo fixo."""
    from playwright.async_api import TimeoutError as PWTimeoutError

    inicio = time.perf_counter()
    try:
        await page.wait_for_function(expressao, timeout=timeout_ms)
    except PWTimeoutError as exc:
        logger.warning("[automacao] timeout (%sms) esperando %s", timeout_ms, etapa)
        raise TimeoutError(f"Timeout esperando {etapa}.") from exc
    _marcar(etapa, inicio)


async def login(page, usuario: str, senha: str) -> bool:
    """Login no Cloudfy. Reaproveita a sessão se já estiver autenticada."""
    inicio = time.perf_counter()
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector("#loginControllerLoginId", timeout=TIMEOUT_CURTO_MS)
    except Exception:
        if not _url_login(page.url):
            _marcar("login.reaproveitado", inicio)
            return True
        raise

    await page.fill("#loginControllerLoginId", usuario)
    await page.fill("#inputPassword", senha)
    await page.press("#inputPassword", "Enter")
    try:
        await esperar(page, JS_LOGIN_OK, 20000, "login")
    except TimeoutError as exc:
        raise RuntimeError(
            "Login no Cloudfy nao concluiu. Verifique usuario/senha nas configuracoes."
        ) from exc
    return True


async def navegar_conciliador(page, usuario: str, senha: str) -> None:
    inicio = time.perf_counter()

    async def _abrir() -> None:
        await page.goto(CONCILIADOR_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_function(JS_SHELL_CONCILIADOR, timeout=TIMEOUT_PADRAO_MS)
        except Exception:
            logger.warning("[automacao] shell do conciliador nao apareceu a tempo")

    await _abrir()

    if _url_login(page.url) or await tem_form_login(page):
        await login(page, usuario, senha)
        await _abrir()

    try:
        await page.evaluate(JS_MOSTRAR_TODOS)
    except Exception:
        pass

    # Se o goto caiu numa tela inline já aberta (mesma URL), volta antes de
    # esperar a lista para não gastar o timeout inteiro.
    if await _conciliacao_aberta(page) or await _detalhe_aberto(page):
        try:
            await garantir_lista(page)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[automacao] nao consegui voltar para a lista: %s", exc)

    try:
        await esperar(page, JS_CONCILIADOR_LINHAS, TIMEOUT_CURTO_MS, "conciliador.linhas")
    except TimeoutError:
        if await tem_form_login(page):
            logger.info("[automacao] sessao expirou; refazendo login")
            await login(page, usuario, senha)
            await _abrir()
            try:
                await page.evaluate(JS_MOSTRAR_TODOS)
            except Exception:
                pass
            try:
                await esperar(page, JS_CONCILIADOR_LINHAS, TIMEOUT_CURTO_MS, "conciliador.linhas")
            except TimeoutError:
                logger.info("[automacao] conciliador sem linhas visiveis (lista vazia?)")
        else:
            logger.info("[automacao] conciliador sem linhas visiveis (lista vazia?)")

    try:
        await garantir_lista(page)
    except Exception as exc:  # noqa: BLE001 - estado sera validado no uso
        logger.warning("[automacao] nao consegui garantir a lista: %s", exc)

    _marcar("conciliador", inicio)


async def ler_caixas(page) -> list[CaixaResumo]:
    inicio = time.perf_counter()
    rows = await page.evaluate(JS_LISTAR)
    caixas = [c for c in parse_caixas_rows(rows) if c.status.lower() == "fechado"]
    _marcar("extrair.lista", inicio)
    return caixas


async def _lista_visivel(page) -> bool:
    try:
        return bool(await page.evaluate(JS_LISTA_PRONTA))
    except Exception:
        return False


async def _detalhe_aberto(page) -> bool:
    try:
        return bool(await page.evaluate(JS_DETALHE_ABERTO))
    except Exception:
        return False


async def _conciliacao_aberta(page) -> bool:
    try:
        return bool(await page.evaluate(JS_CONCILIACAO_ABERTA))
    except Exception:
        return False


async def _clicar_voltar_visivel(page) -> bool:
    botoes = page.locator('a:has-text("Voltar")')
    total = await botoes.count()
    for i in range(total):
        botao = botoes.nth(i)
        try:
            if await botao.is_visible():
                await botao.click()
                return True
        except Exception:
            continue
    return False


async def _voltar_para_lista(page) -> None:
    """Volta da conciliação/detalhe para a lista do conciliador.

    O Cloudfy atual abre detalhe e conciliação inline na mesma aba. O caminho
    de volta é ``Voltar`` (conciliação -> detalhe) e ``Voltar`` (detalhe ->
    lista). Se a tela não responder, recarrega a lista.
    """
    for _ in range(3):
        if await _lista_visivel(page):
            return
        if not (await _conciliacao_aberta(page) or await _detalhe_aberto(page)):
            break
        if not await _clicar_voltar_visivel(page):
            break
        try:
            await page.wait_for_function(JS_DETALHE_OU_LISTA, timeout=TIMEOUT_CURTO_MS)
        except Exception:
            pass

    if await _lista_visivel(page):
        return

    logger.info("[automacao] voltando para a lista via reload")
    await page.reload(wait_until="domcontentloaded")
    try:
        await page.evaluate(JS_MOSTRAR_TODOS)
    except Exception:
        pass
    await page.wait_for_function(JS_LISTA_PRONTA, timeout=TIMEOUT_PADRAO_MS)


async def garantir_lista(page) -> None:
    """Garante a lista do conciliador visível (recupera de detalhe/conciliação)."""
    if await _lista_visivel(page):
        return
    if await _conciliacao_aberta(page) or await _detalhe_aberto(page):
        await _voltar_para_lista(page)
        return
    # Pode ser só o primeiro render da lista: dá uma janela curta antes de
    # assumir que é preciso voltar/recarregar.
    try:
        await page.wait_for_function(JS_LISTA_PRONTA, timeout=1500)
        return
    except Exception:
        pass
    await _voltar_para_lista(page)


async def _abrir_pagina_ou_inline(
    page,
    context,
    acao,
    ready_js: str,
    timeout_ms: int,
    etapa: str,
):
    """Executa a ação e espera uma nova aba OU o conteúdo inline na aba atual.

    Devolve ``(pagina, inline)``. O Cloudfy atual usa navegação inline; algumas
    telas/versões ainda abrem popup, então os dois casos são aceitos. O poll
    tolera navegação/reload no meio da espera (contexto de execução destruído).
    """
    timeout_s = max(0.5, timeout_ms / 1000)
    popup_task = asyncio.create_task(context.wait_for_event("page"))
    try:
        await acao()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if popup_task.done():
                try:
                    nova = popup_task.result()
                    if nova is not None and not nova.is_closed():
                        await nova.wait_for_load_state("domcontentloaded")
                        logger.info("[automacao] %s abriu em nova aba", etapa)
                        return nova, False
                except Exception:
                    pass
            try:
                if await page.evaluate(ready_js):
                    logger.info("[automacao] %s abriu inline", etapa)
                    return page, True
            except Exception:
                # navegação/reload no meio da espera: tenta de novo
                pass
            await asyncio.sleep(0.1)
        raise TimeoutError(f"Timeout esperando {etapa}.")
    finally:
        if not popup_task.done():
            popup_task.cancel()
        await asyncio.gather(popup_task, return_exceptions=True)


async def extrair_dinheiro(page) -> str:
    try:
        await esperar(page, JS_DINHEIRO_PRONTO, TIMEOUT_CURTO_MS, "detalhe.dinheiro")
    except TimeoutError:
        pass
    rows = await page.evaluate(JS_DINHEIRO)
    return parse_dinheiro_rows(rows)


async def extrair_pagamentos(page, context) -> list[PagamentoCartao]:
    btn = page.locator('a:has-text("Conciliar cart"):visible')
    if await btn.count() == 0:
        logger.warning("[automacao] botao 'Conciliar cartoes' nao encontrado")
        return []

    conciliacao, _inline = await _abrir_pagina_ou_inline(
        page,
        context,
        btn.first.click,
        JS_CONCILIACAO_ABERTA,
        TIMEOUT_CURTO_MS,
        "conciliacao",
    )
    try:
        try:
            await esperar(
                conciliacao,
                JS_CONCILIACAO_PRONTA,
                TIMEOUT_CURTO_MS,
                "conciliacao.pronta",
            )
        except TimeoutError:
            if not await conciliacao.evaluate(JS_CONTAR_PAGAMENTOS):
                logger.info("[automacao] conciliacao sem pagamentos de cartao")
            else:
                logger.warning("[automacao] conciliacao nao terminou de renderizar")
        rows = await conciliacao.evaluate(JS_PAGAMENTOS)
        return parse_pagamentos_rows(rows)
    finally:
        if conciliacao is not page:
            await conciliacao.close()


async def abrir_detalhes(page, context, caixa: CaixaResumo) -> CaixaDetalhe:
    inicio = time.perf_counter()
    await garantir_lista(page)
    row = page.locator('tr[ng-repeat*="sknDataProviderFiltered"]:visible').nth(
        caixa.row_index
    )
    botao = row.locator("td .material-icons").last
    detalhe, _inline = await _abrir_pagina_ou_inline(
        page,
        context,
        botao.click,
        JS_DETALHE_ABERTO,
        TIMEOUT_CURTO_MS,
        "detalhe",
    )
    try:
        try:
            await esperar(
                detalhe, JS_DETALHE_PRONTO, TIMEOUT_CURTO_MS, "detalhe.pronto"
            )
        except TimeoutError:
            if not await detalhe.evaluate(JS_CONTAR_FORMAS):
                raise RuntimeError(
                    "Tabela de formas de pagamento do caixa nao carregou. "
                    "Tente importar novamente."
                )
            logger.warning("[automacao] detalhe do caixa sem linhas")
        dinheiro = await extrair_dinheiro(detalhe)
        pagamentos = await extrair_pagamentos(detalhe, context)
        _marcar("extrair.detalhe", inicio)
        return CaixaDetalhe(resumo=caixa, dinheiro=dinheiro, pagamentos=pagamentos)
    finally:
        if detalhe is page:
            try:
                await _voltar_para_lista(page)
            except Exception as exc:  # noqa: BLE001 - próximo caixa tenta de novo
                logger.warning("[automacao] falha ao voltar para a lista: %s", exc)
        else:
            try:
                await detalhe.close()
            except Exception:
                pass


async def _lancar_dinheiro(page, valor: str) -> bool:
    try:
        await esperar(page, JS_DINHEIRO_PRONTO, TIMEOUT_CURTO_MS, "lancar.dinheiro.pronto")
    except TimeoutError:
        if not await page.evaluate(JS_CONTAR_FORMAS):
            raise RuntimeError(
                "Tabela de formas de pagamento nao carregou; nada foi lancado."
            )
        logger.warning("[automacao] tabela de formas de pagamento sem conteudo")

    idx = await page.evaluate("""
        () => {
            const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'))
                .filter(vis);
            return rows.findIndex(row => {
                const td = row.querySelector('td');
                return td && td.textContent.trim().toUpperCase() === 'DINHEIRO';
            });
        }
    """)
    if not isinstance(idx, int) or idx < 0:
        raise RuntimeError("Linha DINHEIRO nao encontrada; nada foi lancado.")

    inp = page.locator('tr[ng-repeat*="RS_FORMASPAGTO"]:visible').nth(idx).locator(
        'input[ng-model*="CC077_VL_CONCI"]'
    )
    if await inp.count() == 0:
        raise RuntimeError("Campo de conciliacao do DINHEIRO nao encontrado; nada foi lancado.")

    await inp.first.fill(valor)
    logger.info("[automacao] dinheiro lancado: %s", valor)
    return True


async def _abrir_conciliacao(page, context):
    btn = page.locator('a:has-text("Conciliar cart"):visible')
    if await btn.count() == 0:
        logger.warning("[automacao] botao 'Conciliar cartoes' nao encontrado")
        return None
    conciliacao, _inline = await _abrir_pagina_ou_inline(
        page,
        context,
        btn.first.click,
        JS_CONCILIACAO_ABERTA,
        TIMEOUT_PADRAO_MS,
        "conciliacao",
    )
    try:
        await esperar(
            conciliacao, JS_CONCILIACAO_PRONTA, TIMEOUT_PADRAO_MS, "conciliacao.pronta"
        )
    except TimeoutError:
        logger.warning("[automacao] conciliacao sem linhas de pagamento")
    return conciliacao


async def _lancar_pagamentos(page, mapeamento: dict, categorias: dict) -> int:
    subtipos = await page.evaluate("""
        () => {
            const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            return Array.from(document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]'))
                .filter(vis)
                .map((row, i) => {
                    const tds = row.querySelectorAll('td');
                    return { i, subtipo: tds.length > 2 ? (tds[2].textContent || '').trim() : '' };
                });
        }
    """)
    rows = page.locator('tr[ng-repeat*="RS_PAGAMENTOS"]:visible')
    lancados = 0
    for item in subtipos or []:
        subtipo = _norm(item.get("subtipo"))
        if not subtipo:
            continue
        cat_key = mapeamento.get(subtipo, "")
        if not cat_key or cat_key not in categorias:
            continue
        real_val = categorias[cat_key].get("real", 0)
        if not real_val:
            continue
        valor_str = str(real_val).replace(".", ",")
        inp = rows.nth(int(item.get("i", 0))).locator('input[ng-model*="CC078_VL_VNDPOS"]')
        if await inp.count() == 0:
            continue
        await inp.first.fill(valor_str)
        lancados += 1
        logger.info("[automacao] lancado %s -> %s: %s", subtipo, cat_key, valor_str)
    return lancados


async def _confirmar_conciliacao(page) -> bool:
    btn = page.locator('a:has-text("Confirmar"):visible')
    if await btn.count() == 0:
        logger.warning("[automacao] botao Confirmar nao encontrado")
        return False
    await btn.first.click()
    logger.info("[automacao] Confirmar clicado")
    return True


async def executar_lancamento(
    page,
    context,
    caixa: CaixaResumo,
    dinheiro_valor: str,
    mapeamento: dict,
    categorias: dict,
) -> dict[str, Any]:
    """Preenche dinheiro + pagamentos. Deixa as páginas abertas."""
    row = page.locator('tr[ng-repeat*="sknDataProviderFiltered"]:visible').nth(
        caixa.row_index
    )
    botao = row.locator("td .material-icons").last
    detalhe, _inline = await _abrir_pagina_ou_inline(
        page,
        context,
        botao.click,
        JS_DETALHE_ABERTO,
        TIMEOUT_CURTO_MS,
        "lancar.detalhe",
    )
    try:
        await esperar(detalhe, JS_DETALHE_PRONTO, TIMEOUT_CURTO_MS, "lancar.detalhe")
    except TimeoutError:
        if not await detalhe.evaluate(JS_CONTAR_FORMAS):
            raise RuntimeError(
                "Tabela de formas de pagamento nao carregou; nada foi lancado."
            )
        logger.warning("[automacao] detalhe do lancamento sem linhas")

    await _lancar_dinheiro(detalhe, dinheiro_valor)
    conciliacao = await _abrir_conciliacao(detalhe, context)
    if conciliacao:
        await _lancar_pagamentos(conciliacao, mapeamento, categorias)
        await _confirmar_conciliacao(conciliacao)
    else:
        logger.warning("[automacao] sem conciliacao de cartoes para lancar")

    return {
        "ok": True,
        "mensagem": "Lancamento concluido. Verifique e finalize manualmente no navegador.",
    }


# ─── Gerenciador financeiro (H02SF0201E) ─────────────────────────

SKN_DESCRICAO = "Components.FI030_VC_LANC"
SKN_VALOR = "Components.FI030_VL_LANC"
SKN_DT_TRANSF = "Components.FI030_DT_TRANSF"
SKN_CONTA_ORIGEM = "Components.FI030_NR_CONTAOR"
SKN_CONTA_DESTINO = "Components.FI030_NR_CONTADE"
SKN_DT_VENC = "Components.FI030_DT_VENC"
SKN_PAGAR_CONTA = "Components.FI030_IT_PAGO"
SKN_DT_PAGAMENTO = "Components.FI030_DT_PAGREC"
SKN_CATEGORIA = "Components.FI030_NR_CAT"
SKN_CONTA = "Components.FI030_NR_CONTA"
SKN_CENTRO_CUSTO = "Components.AD030_NR_CC"
SKN_TIPO_DOCUMENTO = "Components.FI060_IT_TPDOC"
SKN_FORNECEDOR = "Components.FI030_NR_PESSOA"


def _valor_br(valor: Any) -> str:
    texto = f"{float(valor or 0):,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _data_br(data_iso: Any) -> str:
    texto = str(data_iso or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        ano, mes, dia = texto.split("-")
        return f"{dia}/{mes}/{ano}"
    return texto


def _opcao_score(opcao: str, alvo: str) -> int:
    o = " ".join(str(opcao or "").split()).strip().upper()
    a = " ".join(str(alvo or "").split()).strip().upper()
    if not a or not o:
        return -1
    if o == a:
        return 0
    if o.endswith(" : " + a) or o.endswith(": " + a):
        return 1
    if a.isdigit():
        if (
            o.startswith(a + " : ")
            or o.startswith(a + " - ")
            or o.startswith(a + " ")
        ):
            return 1
        return -1
    if a in o:
        return 2
    return -1


def _textos_unicos(texto: str, alternativas: tuple[str, ...] | list[str] = ()) -> list[str]:
    out: list[str] = []
    vistos: set[str] = set()
    for candidato in (texto, *alternativas):
        valor = " ".join(str(candidato or "").split()).strip()
        if not valor or valor.upper() in vistos:
            continue
        vistos.add(valor.upper())
        out.append(valor)
    return out


def _melhor_score(opcao: str, textos: list[str]) -> int:
    scores = [_opcao_score(opcao, texto) for texto in textos]
    validos = [score for score in scores if score >= 0]
    return min(validos) if validos else -1


async def _clicar_melhor_opcao(
    wrapper, textos: list[str], timeout_ms: int = TIMEOUT_SELECT_MS
) -> bool:
    opcoes = wrapper.locator(".selectize-dropdown .option")
    try:
        await opcoes.first.wait_for(state="attached", timeout=timeout_ms)
    except Exception:
        return False

    melhor = None
    melhor_score = 99
    total = await opcoes.count()
    for i in range(total):
        opcao = opcoes.nth(i)
        try:
            if not await opcao.is_visible():
                continue
            score = _melhor_score(await opcao.inner_text(), textos)
        except Exception:
            continue
        if score < 0:
            continue
        if score < melhor_score:
            melhor = opcao
            melhor_score = score
            if score == 0:
                break

    if melhor is None:
        return False
    await melhor.click()
    return True


async def _confirmar_selecao(page, skn_id: str, textos: list[str]) -> None:
    try:
        await page.wait_for_function(
            JS_SELECT_SELECIONADO,
            arg={"skn": skn_id, "textos": textos},
            timeout=TIMEOUT_SELECT_MS,
        )
    except Exception:
        pass


async def _selecionar_opcao(
    modal,
    skn_id: str,
    texto: str,
    alternativas: tuple[str, ...] | list[str] = (),
) -> None:
    """Seleciona uma opção de selectize por texto (código ou descrição)."""
    textos = _textos_unicos(texto, alternativas)
    if not textos:
        return
    wrapper = modal.locator(f'[skn-id="{skn_id}"]').first
    await wrapper.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    page = modal.page

    try:
        atual = await wrapper.locator(".selectize-input").first.inner_text()
        if _melhor_score(atual, textos) >= 0:
            return
    except Exception:
        pass

    controle = wrapper.locator(".selectize-input").first
    await controle.click()

    try:
        await page.wait_for_function(
            JS_SELECT_OPTION,
            arg={"skn": skn_id, "textos": textos},
            timeout=TIMEOUT_SELECT_MS,
        )
    except Exception:
        pass

    if await _clicar_melhor_opcao(wrapper, textos):
        await _confirmar_selecao(page, skn_id, textos)
        return

    # Filtra digitando o texto principal no selectize e tenta novamente.
    try:
        await page.keyboard.type(textos[0], delay=15)
    except Exception:
        pass
    try:
        await page.wait_for_function(
            JS_SELECT_OPTION,
            arg={"skn": skn_id, "textos": textos},
            timeout=TIMEOUT_CURTO_MS,
        )
    except Exception:
        pass
    if await _clicar_melhor_opcao(wrapper, textos, TIMEOUT_CURTO_MS):
        await _confirmar_selecao(page, skn_id, textos)
        return

    raise RuntimeError(
        f"Opcao '{textos[0]}' nao encontrada no campo {skn_id} do financeiro."
    )


async def _preencher_campo(modal, skn_id: str, valor: str) -> None:
    from playwright.async_api import expect

    campo = modal.locator(
        f'[skn-id="{skn_id}"] input[ng-model="sknField"]'
    ).first
    await campo.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    await expect(campo).to_be_enabled(timeout=TIMEOUT_CURTO_MS)
    await campo.fill(str(valor))
    await campo.press("Tab")


async def _toggle_pagar_conta(modal) -> None:
    from playwright.async_api import expect

    wrapper = modal.locator(f'[skn-id="{SKN_PAGAR_CONTA}"]').first
    await wrapper.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    check = wrapper.locator('input[type="checkbox"]').first
    marcado = False
    if await check.count():
        try:
            marcado = await check.is_checked()
        except Exception:
            marcado = False
    if not marcado:
        await _clicar_js(wrapper.locator("span.switchery").first)

    campo = modal.locator(
        f'[skn-id="{SKN_DT_PAGAMENTO}"] input[ng-model="sknField"]'
    ).first
    await expect(campo).to_be_enabled(timeout=TIMEOUT_CURTO_MS)


async def _clicar_js(locator) -> None:
    """Clica via DOM. O Cloudfy cobre botoes com header/iframe de chat."""
    await locator.wait_for(state="attached", timeout=TIMEOUT_CURTO_MS)
    await locator.evaluate("(el) => el.click()")


async def _hover_novo(page):
    """Abre o menu 'Novo' do financeiro (ele só aparece no hover)."""
    botoes = page.locator('button.md-btn:has-text("Novo")')
    total = await botoes.count()
    for posicao in range(total):
        botao = botoes.nth(posicao)
        try:
            if await botao.is_visible():
                await botao.hover()
                return botao
        except Exception:
            continue
    raise RuntimeError(
        "Botao 'Novo' do gerenciador financeiro nao encontrado."
    )


async def _opcao_novo_visivel(
    page, ng_click: str, timeout_ms: int = TIMEOUT_SELECT_MS
) -> bool:
    try:
        await page.locator(
            f'a[ng-click="{ng_click}"]:visible'
        ).first.wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False


async def _abrir_menu_novo(page, ng_click: str):
    botao = await _hover_novo(page)
    if await _opcao_novo_visivel(page, ng_click):
        return botao

    # Fallback: em algumas versões o clique no 'Novo' também abre o menu.
    try:
        await _clicar_js(botao)
        await botao.hover()
    except Exception:
        pass
    if await _opcao_novo_visivel(page, ng_click):
        return botao

    raise RuntimeError(
        "Menu 'Novo' do financeiro nao exibiu a opcao "
        f"'{ng_click}'. Confira se o hover no botao Novo esta funcionando."
    )


async def _clicar_opcao_novo(page, ng_click: str) -> None:
    """Clica via DOM: o menu perde hover/é coberto pelo header durante o clique."""
    alvo = page.locator(f'a[ng-click="{ng_click}"]').first
    await _clicar_js(alvo)


async def _abrir_modal_financeiro(page, ng_click: str, controller: str):
    alvo = page.locator(f'a[ng-click="{ng_click}"]:visible').first
    if await alvo.count() == 0:
        await _abrir_menu_novo(page, ng_click)
    await _clicar_opcao_novo(page, ng_click)

    modal = page.locator(f'main[ng-controller="{controller}"]:visible').last
    await modal.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    await modal.locator(
        f'[skn-id="{SKN_DESCRICAO}"] input[ng-model="sknField"]'
    ).first.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    return modal


async def _erro_campos(modal) -> str:
    try:
        labels = await modal.evaluate(
            """
            (root) => Array.from(root.querySelectorAll('.md-input-danger')).map((el) => {
                const wrapper = el.closest('.md-input-wrapper');
                const label = wrapper ? wrapper.querySelector('label') : null;
                return (label ? label.textContent : '').replace(/\\s+/g, ' ').trim();
            }).filter(Boolean)
            """
        )
    except Exception:
        labels = []
    unicos = list(dict.fromkeys(x for x in labels if x))
    return ", ".join(unicos)


async def _salvar_modal_financeiro(page, modal, dialogos: list[str]) -> None:
    from playwright.async_api import expect

    botao = modal.locator('a:has-text("Salvar")').last
    await _clicar_js(botao)

    try:
        await expect(modal).to_be_hidden(timeout=TIMEOUT_PADRAO_MS)
        return
    except Exception:
        pass

    campos = await _erro_campos(modal)
    mensagem = "Cloudfy nao confirmou o salvamento do lancamento."
    if campos:
        mensagem += f" Campos com erro: {campos}."
    if dialogos:
        mensagem += f" Mensagem do Cloudfy: {dialogos[-1]}"

    # Fecha o modal com erro para o próximo item não reutilizar o formulário.
    try:
        await _clicar_js(modal.locator('a:has-text("Cancelar")').last)
        await expect(modal).to_be_hidden(timeout=TIMEOUT_CURTO_MS)
    except Exception:
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    raise RuntimeError(mensagem)


async def abrir_financeiro(page, usuario: str, senha: str) -> None:
    inicio = time.perf_counter()
    # Sempre parte do login: goto direto no financeiro sem sessão cai no
    # /login/ e o POST de autenticação pode ser abortado pelo goto seguinte.
    await login(page, usuario, senha)
    await page.goto(FINANCEIRO_URL, wait_until="domcontentloaded")
    try:
        await page.wait_for_function(JS_FINANCEIRO_PRONTO, timeout=TIMEOUT_PADRAO_MS)
    except Exception:
        await login(page, usuario, senha)
        await page.goto(FINANCEIRO_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_function(
                JS_FINANCEIRO_PRONTO, timeout=TIMEOUT_PADRAO_MS
            )
        except Exception as exc:
            raise RuntimeError(
                "Gerenciador financeiro do Cloudfy nao carregou "
                "(botao 'Novo' ausente)."
            ) from exc

    await _hover_novo(page)
    faltando: list[str] = []
    for ng_click in ("onNovoPagamento()", "onNovaTransferencia()"):
        if await _opcao_novo_visivel(page, ng_click):
            continue
        try:
            await _abrir_menu_novo(page, ng_click)
        except RuntimeError:
            faltando.append(ng_click)
    if faltando:
        raise RuntimeError(
            "Menu 'Novo' do financeiro abriu sem as opcoes: "
            + ", ".join(faltando)
            + "."
        )
    _marcar("financeiro.tela", inicio)


async def lancar_transferencia_financeira(
    page, item: dict[str, Any], config: dict, dialogos: list[str]
) -> None:
    modal = await _abrir_modal_financeiro(
        page, "onNovaTransferencia()", "H02SF0201J"
    )
    await _preencher_campo(
        modal, SKN_DESCRICAO, str(item.get("descricao") or "MOEDAS").upper()
    )
    await _preencher_campo(modal, SKN_VALOR, _valor_br(item.get("valor")))
    await _preencher_campo(modal, SKN_DT_TRANSF, _data_br(item.get("data")))
    await _selecionar_opcao(
        modal, SKN_CONTA_ORIGEM, config.get("financeiro_origem") or "CAIXA ADM"
    )
    await _selecionar_opcao(
        modal, SKN_CONTA_DESTINO, config.get("financeiro_destino") or "MOEDAS"
    )
    await _salvar_modal_financeiro(page, modal, dialogos)


async def _selecionar_categoria_financeira(
    modal, item: dict[str, Any], config: dict
) -> None:
    codigo, descricao = resolver_categoria(
        item.get("tipo_codigo"),
        item.get("tipo_descricao"),
        config,
    )
    alternativas = [
        f"{codigo} : {descricao}",
        f"{codigo} - {descricao}",
        codigo,
    ]
    await _selecionar_opcao(
        modal,
        SKN_CATEGORIA,
        descricao,
        alternativas,
    )


async def lancar_pagamento_financeiro(
    page, item: dict[str, Any], config: dict, dialogos: list[str]
) -> None:
    modal = await _abrir_modal_financeiro(page, "onNovoPagamento()", "H02SF0201B")
    await _preencher_campo(
        modal, SKN_DESCRICAO, str(item.get("descricao") or "DESPESA").upper()
    )
    await _preencher_campo(modal, SKN_VALOR, _valor_br(item.get("valor")))
    await _preencher_campo(modal, SKN_DT_VENC, _data_br(item.get("data")))
    await _toggle_pagar_conta(modal)
    await _preencher_campo(modal, SKN_DT_PAGAMENTO, _data_br(item.get("data")))
    await _selecionar_categoria_financeira(modal, item, config)
    await _selecionar_opcao(
        modal, SKN_CONTA, config.get("financeiro_conta") or "CAIXA ADM"
    )
    await _selecionar_opcao(
        modal,
        SKN_CENTRO_CUSTO,
        config.get("financeiro_centro_custo") or "LAGOA CAFE CONVENIENCIA",
    )
    await _selecionar_opcao(
        modal,
        SKN_TIPO_DOCUMENTO,
        config.get("financeiro_tipo_documento") or "DINHEIRO",
    )
    fornecedor = str(config.get("financeiro_fornecedor") or "").strip()
    if fornecedor:
        await _selecionar_opcao(modal, SKN_FORNECEDOR, fornecedor)
    await _salvar_modal_financeiro(page, modal, dialogos)


async def executar_lancamentos_financeiros(
    page, itens: list[dict[str, Any]], config: dict
) -> dict[str, Any]:
    """Executa os lançamentos em sequência. Falha de um item não aborta os demais."""
    dialogos: list[str] = []

    async def _handler(dialog):
        try:
            dialogos.append(dialog.message)
        except Exception:
            pass
        try:
            await dialog.accept()
        except Exception:
            pass

    try:
        page.on("dialog", _handler)
    except Exception:
        pass

    resultados: list[dict[str, Any]] = []
    try:
        for posicao, item in enumerate(itens):
            if page.is_closed():
                for resto in itens[posicao:]:
                    resultados.append({
                        "chave": resto.get("chave"),
                        "ok": False,
                        "erro": "Sessao do Cloudfy caiu durante o lote.",
                    })
                break
            try:
                if item.get("tipo") == TIPO_MOEDAS:
                    await lancar_transferencia_financeira(
                        page, item, config, dialogos
                    )
                elif item.get("tipo") == TIPO_DESPESA:
                    await lancar_pagamento_financeiro(page, item, config, dialogos)
                else:
                    raise RuntimeError(
                        f"Tipo de lancamento desconhecido: {item.get('tipo')}"
                    )
                resultados.append({
                    "chave": item.get("chave"),
                    "ok": True,
                    "erro": "",
                })
            except Exception as exc:  # noqa: BLE001 - reporta por item
                logger.warning(
                    "[automacao] falha no lancamento financeiro %s: %s",
                    item.get("chave"),
                    exc,
                )
                resultados.append({
                    "chave": item.get("chave"),
                    "ok": False,
                    "erro": str(exc),
                })
    finally:
        try:
            page.remove_listener("dialog", _handler)
        except Exception:
            pass

    return {"resultados": resultados, "total": len(resultados)}


# ─── Conferência ADM (extrato x dinheiro do caixa) ───────────────

PERIODO_RE = re.compile(
    r"\d{2}/\d{2}/\d{4}\s*[Aa]\s*\d{2}/\d{2}/\d{4}"
)


async def _marcar_checkbox(page, item, marcado: bool) -> None:
    caixa = item.locator(".icheckbox_md").first
    classes = (await caixa.get_attribute("class") or "").split()
    atual = "checked" in classes
    if atual == marcado:
        return
    await _clicar_js(item.locator("label").first)
    await page.wait_for_timeout(150)


async def _filtrar_conta_adm(page) -> None:
    botao = page.locator('button.md-btn:has-text("Contas bancárias")').first
    await botao.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    await botao.hover()

    dropdown = page.locator("div.uk-dropdown:visible").filter(
        has_text="Todas as contas"
    ).first
    await dropdown.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)

    todas = dropdown.locator(
        '[skn-label-field="H02SF0201E_TODAS_AS_CONTAS"]'
    ).first
    caixa_adm = dropdown.locator('[skn-label-field="CAIXA ADM"]').first
    await todas.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    await caixa_adm.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)

    await _marcar_checkbox(page, todas, False)
    await _marcar_checkbox(page, caixa_adm, True)

    aplicar = dropdown.locator('[skn-id="Components.BtnAplicarContas"] a').first
    await _clicar_js(aplicar)
    await page.wait_for_timeout(1200)


async def _filtrar_periodo_adm(page, data_iso: str) -> None:
    data_br = _data_br(data_iso)
    botao = page.locator("button.md-btn").filter(has_text=PERIODO_RE).first
    await botao.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    await botao.hover()

    escolha = page.locator(
        'a[ng-click="onClickSelecionarPeriodo()"]:visible'
    ).first
    await escolha.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    await _clicar_js(escolha)

    inputs = page.locator("input[dir-date-picker]:visible")
    await inputs.first.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
    total = await inputs.count()
    if total < 2:
        raise RuntimeError("Periodo do extrato nao abriu os dois campos de data.")
    for posicao in range(2):
        campo = inputs.nth(posicao)
        await campo.fill(data_br)
        await campo.press("Tab")

    ok = page.locator('a.md-btn:has-text("OK"):visible').last
    await _clicar_js(ok)
    await page.wait_for_timeout(1500)


async def _abrir_extrato_adm(page) -> None:
    botao = page.locator('button.md-btn:has-text("Contas a pagar")').first
    if await botao.count():
        try:
            await botao.hover()
        except Exception:
            pass
    alvo = page.locator('a[ng-click="onFiltraExtrato()"]').first
    await _clicar_js(alvo)
    await page.locator("span[ng-bind='VL_TOTAL']").first.wait_for(
        state="visible", timeout=TIMEOUT_PADRAO_MS
    )


async def _extrair_extrato_adm(page) -> dict[str, Any]:
    total_texto = (
        await page.locator("span[ng-bind='VL_TOTAL']").first.inner_text()
    ).strip()

    dados = await page.evaluate(
        """
        () => Array.from(
            document.querySelectorAll('tr[ng-repeat*="sknDataProviderFiltered"]')
        ).map((row) => {
            try {
                const scope = window.angular && window.angular.element(row).scope();
                const data = scope && scope.Data;
                if (data) {
                    return {
                        descricao: data.FI030_VC_LANC || '',
                        valor: data.FI030_VL_LANC || '',
                        data: data.FI030_DT_DATA || '',
                    };
                }
            } catch (erro) {
                // cai no fallback por celulas
            }
            const tds = row.querySelectorAll('td');
            return {
                descricao: tds[2] ? tds[2].innerText : '',
                valor: tds[11] ? tds[11].innerText : '',
                data: tds[1] ? tds[1].innerText : '',
            };
        })
        """
    )

    linhas: list[dict[str, Any]] = []
    for item in dados:
        descricao = " ".join(str(item.get("descricao") or "").split())
        if not descricao or descricao.upper() == "SALDO ANTERIOR":
            continue
        linhas.append(
            {
                "descricao": descricao,
                "valor": parse_money(item.get("valor")),
                "data": str(item.get("data") or "").strip(),
            }
        )

    total = parse_money(total_texto)
    soma = round(sum(item["valor"] for item in linhas), 2)
    return {
        "total": total,
        "total_texto": total_texto,
        "linhas": linhas,
        "soma_linhas": soma,
        "extrato_inconsistente": abs(soma - total) > 0.005,
    }


async def conferir_extrato_adm(page, data_iso: str) -> dict[str, Any]:
    """Lê o extrato CAIXA ADM da data. Não altera nada no Cloudfy."""
    inicio = time.perf_counter()
    await _abrir_extrato_adm(page)
    _marcar("financeiro.extrato", inicio)

    inicio = time.perf_counter()
    await _filtrar_conta_adm(page)
    _marcar("financeiro.extrato.contas", inicio)

    inicio = time.perf_counter()
    await _filtrar_periodo_adm(page, data_iso)
    _marcar("financeiro.extrato.periodo", inicio)

    inicio = time.perf_counter()
    try:
        await page.wait_for_function(
            """
            (dataBr) => {
                const rows = Array.from(document.querySelectorAll(
                    'tr[ng-repeat*="sknDataProviderFiltered"]'
                ));
                if (!rows.length) return false;
                return rows.every((row) => (
                    (row.textContent || '').includes(dataBr)
                ));
            }
            """,
            arg=_data_br(data_iso),
            timeout=TIMEOUT_PADRAO_MS,
        )
    except Exception:
        logger.warning("[automacao] extrato sem sinal de filtro; lendo assim mesmo")
    dados = await _extrair_extrato_adm(page)
    _marcar("financeiro.extrato.ler", inicio)
    return dados


async def abrir_relatorio_descontos(page, context, usuario: str, senha: str):
    inicio = time.perf_counter()
    await page.goto(HOME_URL, wait_until="domcontentloaded")
    if _url_login(page.url) or await tem_form_login(page):
        await login(page, usuario, senha)

    clicou = await page.evaluate(JS_CLICAR_MENU, RELATORIO_DESCONTO_MENU)
    if not clicou:
        try:
            await page.wait_for_function(JS_MENU_DESCONTO, timeout=TIMEOUT_CURTO_MS)
        except Exception:
            pass
        clicou = await page.evaluate(JS_CLICAR_MENU, RELATORIO_DESCONTO_MENU)
    if not clicou:
        logger.warning("[automacao] menu 'Relatorio de desconto' nao encontrado")
        raise RuntimeError("Menu 'Relatorio de desconto' nao encontrado no Cloudfy.")

    alvo = page
    if len(context.pages) > 1:
        alvo = context.pages[-1]

    try:
        await alvo.wait_for_selector(".selectize-control .selectize-input", timeout=TIMEOUT_PADRAO_MS)
    except Exception:
        logger.warning("[automacao] select de tipo de relatorio nao apareceu")
        raise RuntimeError("Tela do relatorio de descontos nao carregou.")

    await _selecionar_relatorio_por_cupom(alvo)
    _marcar("descontos.tela", inicio)
    return alvo


async def _selecionar_relatorio_por_cupom(page) -> None:
    select = page.locator(".selectize-control .selectize-input")
    await select.first.click()
    opcao = page.locator(".selectize-dropdown .option", has_text=RELATORIO_POR_CUPOM)
    try:
        await opcao.first.wait_for(timeout=TIMEOUT_CURTO_MS)
        await opcao.first.click()
    except Exception:
        logger.warning("[automacao] opcao 'Relatorio por cupom' nao encontrada")


async def baixar_relatorio_descontos(page, usuario: str, senha: str) -> list[dict[str, Any]]:
    context = page.context
    inicio = time.perf_counter()
    alvo = await abrir_relatorio_descontos(page, context, usuario, senha)

    botao = alvo.locator('a:has-text("Excel")')
    try:
        await botao.first.wait_for(timeout=TIMEOUT_PADRAO_MS)
    except Exception as exc:
        raise RuntimeError("Botao de exportacao Excel nao encontrado.") from exc

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        async with alvo.expect_download(timeout=90000) as download_info:
            await botao.first.click()
        download = await download_info.value
        await download.save_as(tmp_path)
        descontos = parse_descontos_xlsx(tmp_path)
        _marcar("descontos.download", inicio)
        return descontos
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# ─── API pública síncrona (delega para a sessão) ──────────────────

def _sessao():
    from app.modules.conciliador.automacao_sessao import SESSAO
    return SESSAO


def listar_caixas_cloudfy(login: str, senha: str, debug: bool = False, otimizar: bool = True) -> dict:
    """Lista caixas com status 'Fechado' no Cloudfy. Bloqueante."""
    return _sessao().listar(login, senha, debug=debug, otimizar=otimizar)


def importar_caixa_cloudfy(
    login: str,
    senha: str,
    caixa_idx: int,
    debug: bool = False,
    otimizar: bool = True,
) -> dict:
    """Extrai detalhes de um caixa especifico do Cloudfy. Bloqueante."""
    return _sessao().importar_por_indice(login, senha, caixa_idx, debug=debug, otimizar=otimizar)


def importar_caixas_cloudfy(
    login: str,
    senha: str,
    chaves: list[dict],
    data_iso: str | None = None,
    debug: bool = False,
    otimizar: bool = True,
) -> dict:
    """Extrai detalhes de varios caixas numa unica rodada. Bloqueante."""
    return _sessao().importar(login, senha, chaves, data_iso, debug=debug, otimizar=otimizar)


def lancar_caixa_cloudfy(
    login: str,
    senha: str,
    caixa_idx: int | None,
    dinheiro_valor: str,
    mapeamento: dict,
    categorias: dict,
    caixa: dict | None = None,
    data_iso: str | None = None,
    debug: bool = False,
    otimizar: bool = True,
) -> dict:
    """Lanca valores do sistema no Cloudfy. Sempre com navegador visivel.
    Navegador permanece aberto apos o lancamento."""
    return _sessao().lancar(
        login,
        senha,
        caixa_idx=caixa_idx,
        dinheiro_valor=dinheiro_valor,
        mapeamento=mapeamento,
        categorias=categorias,
        caixa=caixa,
        data_iso=data_iso,
        debug=debug,
        otimizar=otimizar,
    )


def baixar_descontos_cloudfy(login: str, senha: str, debug: bool = False, otimizar: bool = True) -> dict:
    """Baixa o relatorio de descontos (por cupom) e filtra 'Venda a prazo'."""
    return _sessao().descontos(login, senha, debug=debug, otimizar=otimizar)


def lancar_financeiro_cloudfy(
    login: str,
    senha: str,
    itens: list[dict],
    config: dict,
    debug: bool = False,
    otimizar: bool = True,
) -> dict:
    """Lança transferências/pagamentos no gerenciador financeiro. Headless."""
    return _sessao().lancar_financeiro(
        login,
        senha,
        itens,
        config,
        debug=debug,
        otimizar=otimizar,
    )


def conferir_extrato_adm_cloudfy(
    login: str,
    senha: str,
    data_iso: str,
    debug: bool = False,
    otimizar: bool = True,
) -> dict:
    """Lê o extrato CAIXA ADM no gerenciador financeiro. Headless."""
    return _sessao().conferir_extrato_adm(
        login,
        senha,
        data_iso,
        debug=debug,
        otimizar=otimizar,
    )
