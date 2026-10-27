"""Smoke do preenchimento do gerenciador financeiro contra um Cloudfy falso.

Uso: .venv/bin/python scripts/smoke_financeiro.py
Não usa credenciais. Valida seletores, selectize, toggle e Salvar.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app.modules.conciliador import automacao as ops  # noqa: E402

FIXTURE = RAIZ / "tests" / "fixtures" / "cloudfy_financeiro.html"

CONFIG = {
    "financeiro_origem": "CAIXA ADM",
    "financeiro_destino": "MOEDAS",
    "financeiro_descricao_moedas": "MOEDAS",
    "financeiro_categorias": [
        {"codigo": "78", "descricao": "02.04.23 Vale Transporte"},
        {"codigo": "54", "descricao": "02.03.01 Fornecedores"},
        {"codigo": "115", "descricao": "02.08.99 Outras Despesas Operacionais"},
    ],
    "financeiro_categoria_padrao": "54",
    "financeiro_conta": "CAIXA ADM",
    "financeiro_centro_custo": "LAGOA CAFE CONVENIENCIA",
    "financeiro_tipo_documento": "DINHEIRO",
    "financeiro_fornecedor": "",
}

ITENS = [
    {
        "chave": "transferencia_moedas|2026-10-27",
        "tipo": ops.TIPO_MOEDAS,
        "descricao": "MOEDAS",
        "valor": 123.45,
        "data": "2026-10-27",
    },
    {
        "chave": "despesa|cx-1|0|n1",
        "tipo": ops.TIPO_DESPESA,
        "descricao": "GAS",
        "valor": 30.0,
        "data": "2026-10-27",
        "turno": None,
        "nota_id": "n1",
        "tipo_codigo": "115",
        "tipo_descricao": "02.08.99 Outras Despesas Operacionais",
    },
]


async def main() -> int:
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        erros: list[str] = []
        page.on("pageerror", lambda exc: erros.append(str(exc)))

        await page.goto(FIXTURE.as_uri())
        await page.wait_for_function(ops.JS_FINANCEIRO_PRONTO)
        await ops._hover_novo(page)
        for ng_click in ("onNovoPagamento()", "onNovaTransferencia()"):
            if not await ops._opcao_novo_visivel(page, ng_click):
                print(f"Opcao {ng_click} nao apareceu no hover.", file=sys.stderr)
                return 1

        resultado = await ops.executar_lancamentos_financeiros(page, ITENS, CONFIG)
        dados = await page.evaluate("() => window.__lancamentos")

        await browser.close()

    print(json.dumps({"resultado": resultado, "lancamentos": dados, "pageerrors": erros}, indent=2, ensure_ascii=False))

    falhas = [r for r in resultado.get("resultados", []) if not r.get("ok")]
    if falhas or erros:
        return 1
    if len(dados) != 2:
        print("Esperava 2 lancamentos no Cloudfy falso.", file=sys.stderr)
        return 1

    transferencia, pagamento = dados
    ok = (
        transferencia["tipo"] == "transferencia"
        and transferencia["descricao"] == "MOEDAS"
        and transferencia["valor"] == "123,45"
        and transferencia["data"] == "27/10/2026"
        and "CAIXA ADM" in transferencia["origem"]
        and "MOEDAS" in transferencia["destino"]
        and pagamento["tipo"] == "pagamento"
        and pagamento["descricao"] == "GAS"
        and pagamento["valor"] == "30,00"
        and pagamento["vencimento"] == "27/10/2026"
        and pagamento["pagou"] is True
        and pagamento["pagamento"] == "27/10/2026"
        and "02.08.99 Outras Despesas Operacionais" in pagamento["categoria"]
        and "CAIXA ADM" in pagamento["conta"]
        and "LAGOA CAFE CONVENIENCIA" in pagamento["centro"]
        and "DINHEIRO" in pagamento["tipo_doc"]
    )
    if not ok:
        print("Valores preenchidos nao conferem.", file=sys.stderr)
        return 1
    print("Smoke financeiro OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
