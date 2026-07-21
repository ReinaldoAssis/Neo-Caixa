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
        if getattr(self, "_keep_open", False):
            return
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
        await page.wait_for_timeout(3000)

        pages = context.pages
        if len(pages) < 2:
            await page.wait_for_timeout(4000)
            pages = context.pages

        detalhe_page = pages[-1] if len(pages) >= 2 else page
        await detalhe_page.wait_for_load_state("domcontentloaded")
        await detalhe_page.wait_for_timeout(4000)

        dinheiro = await self._extrair_dinheiro(detalhe_page)
        pagamentos = await self._extrair_pagamentos(detalhe_page, context)

        if detalhe_page != page:
            await detalhe_page.close()

        return CaixaDetalhe(resumo=caixa, dinheiro=dinheiro, pagamentos=pagamentos)

    async def _extrair_dinheiro(self, page) -> str:
        try:
            await page.wait_for_selector(
                'tr[ng-repeat*="RS_FORMASPAGTO"]', timeout=15000
            )
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        # Estrategia 1: JS direto
        try:
            valor = await page.evaluate("""
                const rows = document.querySelectorAll('tr[ng-repeat*="RS_FORMASPAGTO"]');
                for (const row of rows) {
                    const td = row.querySelector('td');
                    if (td && td.textContent.trim().toUpperCase() === 'DINHEIRO') {
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

        # Estrategia 2: Playwright locator (fallback)
        try:
            rows = page.locator('tr[ng-repeat*="RS_FORMASPAGTO"]')
            count = await rows.count()
            for i in range(count):
                row = rows.nth(i)
                first_td = row.locator("td").first
                text = (await first_td.text_content() or "").strip()
                if text.upper() == "DINHEIRO":
                    span = row.locator('span[ng-bind*="CC077_VL_CALC"]')
                    if await span.count() > 0:
                        valor = (await span.first.text_content() or "").strip()
                        if valor:
                            return valor
        except Exception:
            pass

        return ""

    async def _extrair_pagamentos(self, page, context) -> list[PagamentoCartao]:
        btn = page.locator('a:has-text("Conciliar cart")')
        if await btn.count() == 0:
            print("[AVISO] Botao 'Conciliar cartoes' nao encontrado.")
            return []

        await btn.first.click()
        await page.wait_for_timeout(3000)

        pages = context.pages
        if len(pages) < 3:
            await page.wait_for_timeout(4000)
            pages = context.pages

        conciliacao_page = pages[-1]
        await conciliacao_page.wait_for_load_state("domcontentloaded")
        await conciliacao_page.wait_for_timeout(4000)

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

    # ── Lançar (sistema → Cloudfy) ────────────────────────────

    async def _lancar_dinheiro(self, page, valor: str) -> None:
        """Preenche o input de dinheiro na linha DINHEIRO da tabela RS_FORMASPAGTO."""
        rows = page.locator('tr[ng-repeat*="RS_FORMASPAGTO"]')
        count = await rows.count()
        for i in range(count):
            row = rows.nth(i)
            first_td = row.locator("td").first
            text = (await first_td.text_content() or "").strip()
            if text.upper() == "DINHEIRO":
                inp = row.locator('input[ng-model*="CC077_VL_CONCI"]')
                if await inp.count() > 0:
                    await inp.first.fill(valor)
                    await page.wait_for_timeout(300)
                    print(f"[OK] Dinheiro lancado: {valor}")
                    return
        print("[AVISO] Input de dinheiro nao encontrado.")

    async def _abrir_conciliacao(self, page, context):
        """Clica 'Conciliar cartoes' e retorna a pagina de conciliacao."""
        btn = page.locator('a:has-text("Conciliar cart")')
        if await btn.count() == 0:
            print("[AVISO] Botao 'Conciliar cartoes' nao encontrado.")
            return None

        await btn.first.click()
        await page.wait_for_timeout(3000)

        pages = context.pages
        if len(pages) < 3:
            await page.wait_for_timeout(4000)
            pages = context.pages

        conciliacao_page = pages[-1]
        await conciliacao_page.wait_for_load_state("domcontentloaded")
        await conciliacao_page.wait_for_timeout(4000)
        return conciliacao_page

    async def _lancar_pagamentos(
        self, page, mapeamento: dict, categorias: dict
    ) -> None:
        """Preenche inputs da conciliacao com valores reais do sistema."""
        rows = page.locator('tr[ng-repeat*="RS_PAGAMENTOS"]')
        count = await rows.count()

        for i in range(count):
            row = rows.nth(i)
            tds = row.locator("td")

            # Extrai o subtipo (3a coluna)
            subtipo = ""
            if await tds.count() > 2:
                subtipo = (await tds.nth(2).text_content() or "").strip()

            if not subtipo:
                continue

            # Busca categoria do sistema via mapeamento
            cat_key = mapeamento.get(subtipo, "")
            if not cat_key or cat_key not in categorias:
                continue

            real_val = categorias[cat_key].get("real", 0)
            if not real_val:
                continue

            valor_str = str(real_val).replace(".", ",")

            # Preenche VNDPOS (coluna 5, index 4)
            inp = row.locator('input[ng-model*="CC078_VL_VNDPOS"]')
            if await inp.count() > 0:
                await inp.first.fill(valor_str)
                await page.wait_for_timeout(200)

            print(f"[OK] Lancado {subtipo} -> {cat_key}: {valor_str}")

    async def _confirmar_conciliacao(self, page) -> None:
        """Clica no botao Confirmar na pagina de conciliacao."""
        btn = page.locator('a:has-text("Confirmar")')
        if await btn.count() > 0:
            await btn.first.click()
            await page.wait_for_timeout(1000)
            print("[OK] Confirmar clicado.")

    async def executar_lancamento(
        self,
        caixa_idx: int,
        dinheiro_valor: str,
        mapeamento: dict,
        categorias: dict,
    ) -> dict[str, Any]:
        ok = await self.login()
        if not ok:
            return {"erro": "Falha no login."}

        await self.navegar_conciliador()
        caixas = await self.listar_caixas()

        if caixa_idx < 0 or caixa_idx >= len(caixas):
            return {"erro": f"Indice invalido. {len(caixas)} disponiveis."}

        selecionado = caixas[caixa_idx]
        page = self._page
        context = self._context

        # Abre detalhes do caixa
        row = page.locator('tr[ng-repeat*="sknDataProviderFiltered"]').nth(
            selecionado.row_index
        )
        btn = row.locator("td .material-icons").last
        await btn.click()
        await page.wait_for_timeout(3000)

        pages = context.pages
        if len(pages) < 2:
            await page.wait_for_timeout(4000)
            pages = context.pages

        detalhe_page = pages[-1] if len(pages) >= 2 else page
        await detalhe_page.wait_for_load_state("domcontentloaded")
        await detalhe_page.wait_for_timeout(4000)

        # 1. Lancar dinheiro
        await self._lancar_dinheiro(detalhe_page, dinheiro_valor)

        # 2. Abrir conciliacao e lancar pagamentos
        conciliacao_page = await self._abrir_conciliacao(detalhe_page, context)
        if conciliacao_page:
            await self._lancar_pagamentos(conciliacao_page, mapeamento, categorias)
            await self._confirmar_conciliacao(conciliacao_page)
            # NAO fecha a pagina — usuario precisa ver
        else:
            # Se nao tem conciliacao, fecha detalhe
            if detalhe_page != page:
                await detalhe_page.close()

        print("[OK] Lancamento concluido. Navegador permanece aberto para acao do usuario.")
        self._keep_open = True
        return {"ok": True, "mensagem": "Lancamento concluido. Verifique e finalize manualmente no navegador."}

    # ── Fluxo principal ────────────────────────────────────────

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


def lancar_caixa_cloudfy(
    login: str,
    senha: str,
    caixa_idx: int,
    dinheiro_valor: str,
    mapeamento: dict,
    categorias: dict,
) -> dict:
    """Lanca valores do sistema no Cloudfy. Sempre com navegador visivel.
    Navegador permanece aberto apos o lancamento."""

    async def _runner():
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(
                channel="chrome", headless=False
            )
        except Exception:
            browser = await pw.chromium.launch(headless=False)

        context = await browser.new_context()
        page = await context.new_page()

        scraper = CloudfyScraper(login, senha, debug=True)
        scraper._browser = browser
        scraper._context = context
        scraper._page = page
        scraper._keep_open = True

        try:
            return await scraper.executar_lancamento(
                caixa_idx=caixa_idx,
                dinheiro_valor=dinheiro_valor,
                mapeamento=mapeamento,
                categorias=categorias,
            )
        except Exception as exc:
            return {"erro": str(exc)}

    try:
        return asyncio.run(_runner())
    except Exception as exc:
        return {"erro": str(exc)}


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
