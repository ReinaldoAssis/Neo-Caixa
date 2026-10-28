"""Categoria PIX CNPJ (forma CHEQUE do Cloudfy) no caixa restaurante."""

from __future__ import annotations

import asyncio

import pytest

from app.modules.conciliador import automacao as aut
from app.modules.conciliador.constants import (
    CATEGORIA_CLASSIFICACAO,
    CATEGORIAS_RESTAURANTE,
    CATEGORIAS_RESTAURANTE_LABELS,
)
from app.modules.conciliador.services import build_conciliation_rows_restaurante


class _FakeInput:
    def __init__(self):
        self.value = None

    async def count(self):
        return 1

    @property
    def first(self):
        return self

    async def fill(self, value):
        self.value = value


class _FakeFormaRows:
    def __init__(self, page):
        self.page = page

    def nth(self, idx):
        self.page.idx = int(idx)
        return self

    def locator(self, selector):
        return self.page.inputs[self.page.formas[self.page.idx]]


class _FakePage:
    def __init__(self, formas):
        self.formas = list(formas)
        self.inputs = {forma: _FakeInput() for forma in self.formas}
        self.rows: list[dict] = []
        self.idx = None

    async def wait_for_function(self, expressao, timeout=None):
        return True

    async def evaluate(self, expressao, arg=None):
        if arg is not None:
            alvo = str(arg).upper()
            for indice, forma in enumerate(self.formas):
                if forma.upper() == alvo:
                    return indice
            return -1
        if "CC077_VL_CALC" in expressao:
            return self.rows
        return True

    def locator(self, selector):
        return _FakeFormaRows(self)


def test_categoria_pix_cnpj_no_restaurante():
    assert "PIX_CNPJ" in CATEGORIAS_RESTAURANTE
    assert CATEGORIAS_RESTAURANTE_LABELS["PIX_CNPJ"] == "PIX CNPJ"
    assert CATEGORIA_CLASSIFICACAO["PIX_CNPJ"] == "DEBITO"


def test_linha_pix_cnpj_usa_real_informado():
    rows = build_conciliation_rows_restaurante(
        {"PIX_CNPJ": {"sistema": 100.0, "real": 90.0}}, [], 0.0
    )
    linha = next(row for row in rows if row["key"] == "PIX_CNPJ")
    assert linha["label"] == "PIX CNPJ"
    assert linha["sistema"] == 100.0
    assert linha["real"] == 90.0
    assert linha["diferenca"] == -10.0


def test_parse_cheque_rows_le_forma_cheque():
    rows = [
        {"forma": "DINHEIRO", "valor": "35,00"},
        {"forma": " Cheque ", "valor": "1.234,56"},
    ]
    assert aut.parse_cheque_rows(rows) == "1.234,56"
    assert aut.parse_dinheiro_rows(rows) == "35,00"
    assert aut.parse_cheque_rows([]) == ""


def test_extrair_formas_pagamento_le_dinheiro_e_cheque():
    page = _FakePage(["DINHEIRO", "CHEQUE"])
    page.rows = [
        {"forma": "DINHEIRO", "valor": "632,75"},
        {"forma": "CHEQUE", "valor": "150,00"},
    ]
    formas = asyncio.run(aut.extrair_formas_pagamento(page))
    assert formas == {"DINHEIRO": "632,75", "CHEQUE": "150,00"}


def test_lancar_formas_preenche_dinheiro_e_cheque():
    page = _FakePage(["PIX", "DINHEIRO", "CHEQUE"])
    asyncio.run(aut._lancar_formas_pagamento(page, "100,00", "50,00"))
    assert page.inputs["DINHEIRO"].value == "100,00"
    assert page.inputs["CHEQUE"].value == "50,00"
    assert page.inputs["PIX"].value is None


def test_lancar_formas_nao_preenche_cheque_zerado():
    page = _FakePage(["DINHEIRO", "CHEQUE"])
    asyncio.run(aut._lancar_formas_pagamento(page, "100,00", "0,00"))
    assert page.inputs["DINHEIRO"].value == "100,00"
    assert page.inputs["CHEQUE"].value is None


def test_lancar_formas_ignora_cheque_sem_linha():
    page = _FakePage(["DINHEIRO"])
    asyncio.run(aut._lancar_formas_pagamento(page, "100,00", "50,00"))
    assert page.inputs["DINHEIRO"].value == "100,00"


def test_lancar_formas_exige_linha_dinheiro():
    page = _FakePage(["CHEQUE"])
    with pytest.raises(RuntimeError, match="DINHEIRO"):
        asyncio.run(aut._lancar_formas_pagamento(page, "100,00", ""))
