"""
Bridge entre a API do conciliador e o scraper Playwright do Cloudfy.

Expõe funções síncronas que internamente rodam o loop async do Playwright.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field, asdict
from typing import Any

CLOUDY_BASE = "https://app.cloudfy.net.br/site"
LOGIN_URL = f"{CLOUDY_BASE}/#/login"
CONCILIADOR_URL = f"{CLOUDY_BASE}/#/H02SF0108B"


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


# ─── Helpers ───────────────────────────────────────────────────────

def _parse_brl(value: str) -> float:
    cleaned = value.replace("R$", "").replace(" ", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return 0.0


# ─── Scraper Async ─────────────────────────────────────────────────

class CloudfyScraper:
    def __init__(self, login: str, senha: str, debug: bool = False):
        self._login = login
        self._senha = senha
        self._debug = debug

    async def __aenter__(self) -> "CloudfyScraper":
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()

        launch_options = {"headless": not self._debug}

        try:
            self._browser = await pw.chromium.launch(
                channel="chrome", **launch_options
            )
        except Exception:
            try:
                self._browser = await pw.chromium.launch(**launch_options)
            except Exception as e:
                raise RuntimeError(
                    "Navegador nao encontrado. Instale o Google Chrome ou "
                    "execute 'playwright install chromium' no terminal."
                ) from e
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if getattr(self, "_browser", None):
            await self._browser.close()

    async def login(self) -> bool:
        page = self._page
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        await page.fill('#loginControllerLoginId', self._login)
        await page.fill('#inputPassword', self._senha)
        await page.press('#inputPassword', 'Enter')
        await page.wait_for_timeout(5000)

        if "login" in page.url.lower():
            print("[ERRO] Login falhou.", file=sys.stderr)
            return False
        print("[OK] Login realizado.")
        return True

    async def navegar_conciliador(self) -> None:
        page = self._page
        await page.goto(CONCILIADOR_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        try:
            await page.wait_for_selector(
                'tr[ng-repeat*="sknDataProviderFiltered"]', timeout=20000
            )
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        await page.evaluate("""
            const el = Array.from(document.querySelectorAll('a'))
                .find(a => a.textContent.trim() === 'Mostrar todos');
            if (el) el.click();
        """)
        await page.wait_for_timeout(3000)
        try:
            await page.wait_for_selector(
                'tr[ng-repeat*="sknDataProviderFiltered"]', timeout=20000
            )
        except Exception:
            pass
        await page.wait_for_timeout(1000)
        print("[OK] Conciliador carregado.")

    async def listar_caixas(self, apenas_fechado: bool = True) -> list[CaixaResumo]:
        page = self._page
        rows = page.locator('tr[ng-repeat*="sknDataProviderFiltered"]')
        count = await rows.count()
        caixas: list[CaixaResumo] = []

        for i in range(count):
            row = rows.nth(i)
            cells = row.locator('td[ng-repeat*="Column in ::Columns"]')
            cell_count = await cells.count()
            texts: list[str] = []
            for j in range(cell_count):
                cell = cells.nth(j)
                class_attr = (await cell.get_attribute("class")) or ""
                if "ng-hide" in class_attr:
                    continue
                text = (await cell.text_content() or "").strip()
                texts.append(text)

            if not texts or len(texts) < 4:
                continue

            caixa = CaixaResumo(
                data=texts[0] if len(texts) > 0 else "",
                pdv=texts[1] if len(texts) > 1 else "",
                turno=texts[2] if len(texts) > 2 else "",
                horario_abertura=texts[3] if len(texts) > 3 else "",
                horario_fechamento=texts[4] if len(texts) > 4 else "",
                movto=texts[5] if len(texts) > 5 else "",
                status=texts[6] if len(texts) > 6 else "",
                valor=texts[9] if len(texts) > 9 else "",
                row_index=i,
            )
            caixas.append(caixa)

        if apenas_fechado:
            caixas = [c for c in caixas if c.status.lower() == "fechado"]

        print(f"[OK] {len(caixas)} caixas encontradas.")
        return caixas

    async def abrir_detalhes(self, caixa: CaixaResumo) -> CaixaDetalhe:
        page = self._page
        context = self._context

        row = page.locator('tr[ng-repeat*="sknDataProviderFiltered"]').nth(
            caixa.row_index
        )
        btn = row.locator("td .material-icons").last
        await btn.click()
        await page.wait_for_timeout(2000)

        pages = context.pages
        if len(pages) < 2:
            await page.wait_for_timeout(3000)
            pages = context.pages

        detalhe_page = pages[-1] if len(pages) >= 2 else page
        await detalhe_page.wait_for_load_state("domcontentloaded")
        await detalhe_page.wait_for_timeout(3000)

        dinheiro = await self._extrair_dinheiro(detalhe_page)
        pagamentos = await self._extrair_pagamentos(detalhe_page, context)

        if detalhe_page != page:
            await detalhe_page.close()

        return CaixaDetalhe(resumo=caixa, dinheiro=dinheiro, pagamentos=pagamentos)

    async def _extrair_dinheiro(self, page) -> str:
        # Aguarda tabela de formas de pagamento carregar
        try:
            await page.wait_for_selector(
                'tr[ng-repeat*="RS_FORMASPAGTO"]', timeout=15000
            )
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        # Extrai via JS do escopo Angular — mais confiavel que seletor CSS
        try:
            valor = await page.evaluate("""
                const rows = document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]');
                for (const row of rows) {
                    const tds = row.querySelectorAll('td');
                    if (tds.length > 0 && tds[0].textContent.trim().toUpperCase() === 'DINHEIRO') {
                        const span = row.querySelector('span[ng-bind*="CC077_VL_CALC"]');
                        if (span) return span.textContent.trim();
                    }
                }
                return '';
            """)
            if valor:
                return valor.strip()
        except Exception:
            pass

        return ""

    async def _extrair_pagamentos(self, page, context) -> list[PagamentoCartao]:
        btn = page.locator('a:has-text("Conciliar cart")')
        if await btn.count() == 0:
            print("[AVISO] Botao 'Conciliar cartoes' nao encontrado.")
            return []

        await btn.first.click()
        await page.wait_for_timeout(2000)

        pages = context.pages
        conciliacao_page = pages[-1]
        await conciliacao_page.wait_for_load_state("domcontentloaded")
        await conciliacao_page.wait_for_timeout(3000)

        pagamentos = await self._parse_tabela_pagamentos(conciliacao_page)

        if conciliacao_page != page:
            await conciliacao_page.close()

        return pagamentos

    async def _parse_tabela_pagamentos(self, page) -> list[PagamentoCartao]:
        rows = page.locator('tr[ng-repeat*="RS_PAGAMENTOS"]')
        count = await rows.count()
        pagamentos: list[PagamentoCartao] = []

        for i in range(count):
            row = rows.nth(i)
            tds = row.locator("td")
            td_count = await tds.count()

            texts: list[str] = []
            for j in range(td_count):
                td = tds.nth(j)
                inp = td.locator(
                    'input[ng-model*="CC078_VL_VNDPOS"], '
                    'input[ng-model*="CC078_VL_VNDTEF"], '
                    'input[ng-model*="CC078_IT_QTPAGAME"]'
                )
                if await inp.count() > 0:
                    val = await inp.first.input_value()
                    texts.append(val.strip())
                else:
                    txt = (await td.text_content() or "").strip()
                    texts.append(txt)

            if len(texts) >= 4:
                pg = PagamentoCartao(
                    tipo=texts[0] if len(texts) > 0 else "",
                    bandeira=texts[1] if len(texts) > 1 else "",
                    subtipo=texts[2] if len(texts) > 2 else "",
                    valor_vndpos=texts[4] if len(texts) > 4 else "",
                    valor_vndtef=texts[5] if len(texts) > 5 else "",
                    valor_total=texts[6] if len(texts) > 6 else "",
                    quantidade=texts[7] if len(texts) > 7 else "",
                )
                pagamentos.append(pg)

        print(f"[OK] {len(pagamentos)} pagamentos extraidos.")
        return pagamentos

    async def executar(
        self, caixa_idx: int | None = None, apenas_listar: bool = False
    ) -> dict[str, Any]:
        ok = await self.login()
        if not ok:
            return {"erro": "Falha no login."}

        await self.navegar_conciliador()
        caixas = await self.listar_caixas()

        if apenas_listar or caixa_idx is None:
            return {
                "total": len(caixas),
                "caixas": [asdict(c) for c in caixas],
            }

        if caixa_idx < 0 or caixa_idx >= len(caixas):
            return {
                "erro": f"Indice invalido. {len(caixas)} disponiveis (0-{len(caixas)-1})."
            }

        selecionado = caixas[caixa_idx]
        detalhe = await self.abrir_detalhes(selecionado)
        return asdict(detalhe)


# ─── API pública síncrona ──────────────────────────────────────────


def listar_caixas_cloudfy(login: str, senha: str, debug: bool = False) -> dict:
    """Lista caixas com status 'Fechado' no Cloudfy. Bloqueante."""
    return _run_async(login, senha, debug, apenas_listar=True)


def importar_caixa_cloudfy(
    login: str, senha: str, caixa_idx: int, debug: bool = False
) -> dict:
    """Extrai detalhes de um caixa especifico do Cloudfy. Bloqueante."""
    return _run_async(login, senha, debug, caixa_idx=caixa_idx)


def _run_async(
    login: str,
    senha: str,
    debug: bool = False,
    caixa_idx: int | None = None,
    apenas_listar: bool = False,
) -> dict:
    async def _runner():
        async with CloudfyScraper(login, senha, debug=debug) as scraper:
            return await scraper.executar(caixa_idx=caixa_idx, apenas_listar=apenas_listar)

    try:
        return asyncio.run(_runner())
    except Exception as exc:
        return {"erro": str(exc)}
