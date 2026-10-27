"""
Bridge entre a API do conciliador e o scraper Playwright do Cloudfy.

Aqui ficam apenas operações de página (recebem ``page``/``context`` já prontos)
e parsers puros/testáveis. O ciclo de vida do navegador (sessão persistente,
aquecimento, troca headless↔headed) mora em ``automacao_sessao.py``.

As funções públicas continuam síncronas e delegam para a sessão singleton.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from app.core.logger import logger

CLOUDY_BASE = "https://app.cloudfy.net.br/site"
LOGIN_URL = f"{CLOUDY_BASE}/#/login"
CONCILIADOR_URL = f"{CLOUDY_BASE}/#/H02SF0108B"
HOME_URL = f"{CLOUDY_BASE}/#/"

RELATORIO_DESCONTO_MENU = "Relatório de desconto"
RELATORIO_POR_CUPOM = "Relatório por cupom"
FORMA_VENDA_A_PRAZO = "venda a prazo"

TIMEOUT_PADRAO_MS = 15000
TIMEOUT_CURTO_MS = 8000
TIMEOUT_POPUP_MS = 10000


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
    .map((row, i) => ({
        i,
        cells: Array.from(row.querySelectorAll('td[ng-repeat*="Column in ::Columns"]'))
            .filter(td => !(td.className || '').includes('ng-hide'))
            .map(td => (td.textContent || '').trim()),
    }))
"""

JS_PAGAMENTOS = """
() => Array.from(document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]'))
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
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="sknDataProviderFiltered"]'));
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
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'));
    if (!rows.length) return false;
    return rows.every(row => (row.textContent || '').trim().length > 0);
}
"""

JS_DINHEIRO_PRONTO = """
() => {
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'));
    return rows.length > 0 && rows.every(row => (row.textContent || '').trim().length > 0);
}
"""

JS_CONTAR_FORMAS = """() => document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]').length"""

JS_CONTAR_PAGAMENTOS = """() => document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]').length"""

JS_CONCILIACAO_PRONTA = """
() => {
    const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]'));
    if (!rows.length) return false;
    return rows.every(row => row.querySelectorAll('td').length >= 8);
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

    _marcar("conciliador", inicio)


async def ler_caixas(page) -> list[CaixaResumo]:
    inicio = time.perf_counter()
    rows = await page.evaluate(JS_LISTAR)
    caixas = [c for c in parse_caixas_rows(rows) if c.status.lower() == "fechado"]
    _marcar("extrair.lista", inicio)
    return caixas


async def _abrir_popup(page, context, acao):
    """Executa a ação e espera o popup; se não abrir, segue na mesma página."""
    from playwright.async_api import TimeoutError as PWTimeoutError

    try:
        async with context.expect_page(timeout=TIMEOUT_POPUP_MS) as info:
            await acao()
        nova = await info.value
    except PWTimeoutError:
        logger.info("[automacao] popup nao abriu; seguindo na pagina atual")
        return page

    await nova.wait_for_load_state("domcontentloaded")
    return nova


async def extrair_dinheiro(page) -> str:
    try:
        await esperar(page, JS_DINHEIRO_PRONTO, TIMEOUT_CURTO_MS, "detalhe.dinheiro")
    except TimeoutError:
        pass
    rows = await page.evaluate(JS_DINHEIRO)
    return parse_dinheiro_rows(rows)


async def extrair_pagamentos(page, context) -> list[PagamentoCartao]:
    btn = page.locator('a:has-text("Conciliar cart")')
    if await btn.count() == 0:
        logger.warning("[automacao] botao 'Conciliar cartoes' nao encontrado")
        return []

    conciliacao = await _abrir_popup(page, context, btn.first.click)
    try:
        try:
            await esperar(conciliacao, JS_CONCILIACAO_PRONTA, TIMEOUT_CURTO_MS, "conciliacao.pronta")
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
    row = page.locator('tr[ng-repeat*="sknDataProviderFiltered"]').nth(caixa.row_index)
    botao = row.locator("td .material-icons").last
    detalhe = await _abrir_popup(page, context, botao.click)
    try:
        try:
            await esperar(detalhe, JS_DETALHE_PRONTO, TIMEOUT_CURTO_MS, "detalhe.pronto")
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
        if detalhe is not page:
            await detalhe.close()


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
            const rows = Array.from(document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]'));
            return rows.findIndex(row => {
                const td = row.querySelector('td');
                return td && td.textContent.trim().toUpperCase() === 'DINHEIRO';
            });
        }
    """)
    if not isinstance(idx, int) or idx < 0:
        raise RuntimeError("Linha DINHEIRO nao encontrada; nada foi lancado.")

    inp = page.locator('tr[ng-repeat*="RS_FORMASPAGTO"]').nth(idx).locator(
        'input[ng-model*="CC077_VL_CONCI"]'
    )
    if await inp.count() == 0:
        raise RuntimeError("Campo de conciliacao do DINHEIRO nao encontrado; nada foi lancado.")

    await inp.first.fill(valor)
    logger.info("[automacao] dinheiro lancado: %s", valor)
    return True


async def _abrir_conciliacao(page, context):
    btn = page.locator('a:has-text("Conciliar cart")')
    if await btn.count() == 0:
        logger.warning("[automacao] botao 'Conciliar cartoes' nao encontrado")
        return None
    conciliacao = await _abrir_popup(page, context, btn.first.click)
    try:
        await esperar(conciliacao, JS_CONCILIACAO_PRONTA, TIMEOUT_PADRAO_MS, "conciliacao.pronta")
    except TimeoutError:
        logger.warning("[automacao] conciliacao sem linhas de pagamento")
    return conciliacao


async def _lancar_pagamentos(page, mapeamento: dict, categorias: dict) -> int:
    subtipos = await page.evaluate("""
        () => Array.from(document.querySelectorAll('tr[ng-repeat*="RS_PAGAMENTOS"]')).map((row, i) => {
            const tds = row.querySelectorAll('td');
            return { i, subtipo: tds.length > 2 ? (tds[2].textContent || '').trim() : '' };
        })
    """)
    rows = page.locator('tr[ng-repeat*="RS_PAGAMENTOS"]')
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
    btn = page.locator('a:has-text("Confirmar")')
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
    row = page.locator('tr[ng-repeat*="sknDataProviderFiltered"]').nth(caixa.row_index)
    botao = row.locator("td .material-icons").last
    detalhe = await _abrir_popup(page, context, botao.click)
    if detalhe is not page:
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
