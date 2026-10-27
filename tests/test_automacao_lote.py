"""Testes puros do lote/chaves/parsers da automação Cloudfy."""

from __future__ import annotations

from app.modules.conciliador import automacao as aut
from app.modules.conciliador import config_posto


def _caixa(data="27/10/2026", pdv="01", turno="1", movto="T1", fechamento="15:00", idx=0):
    return aut.CaixaResumo(
        data=data,
        pdv=pdv,
        turno=turno,
        horario_abertura="08:00",
        horario_fechamento=fechamento,
        movto=movto,
        status="Fechado",
        valor="100,00",
        row_index=idx,
    )


# ─── Datas ────────────────────────────────────────────────────────

def test_normalizar_data_iso_formatos():
    assert aut.normalizar_data_iso("27/10/2026") == "2026-10-27"
    assert aut.normalizar_data_iso("27/10/26") == "2026-10-27"
    assert aut.normalizar_data_iso("2026-10-27") == "2026-10-27"
    assert aut.normalizar_data_iso("2026-10-27T10:00:00") == "2026-10-27"
    assert aut.normalizar_data_iso("") is None
    assert aut.normalizar_data_iso("ontem") is None


def test_validar_data_caixa():
    caixa = _caixa()
    assert aut.validar_data_caixa(caixa, "2026-10-27") is None
    assert aut.validar_data_caixa(caixa, None) is None
    erro = aut.validar_data_caixa(caixa, "2026-10-26")
    assert erro is not None and "fora da data" in erro


# ─── Turno ────────────────────────────────────────────────────────

def test_turno_de_caixa_coluna_tem_prioridade():
    assert aut.turno_de_caixa(_caixa(turno="2", movto="T1")) == 2
    assert aut.turno_de_caixa(_caixa(turno="1", movto="T2")) == 1


def test_turno_de_caixa_fallback_movto():
    assert aut.turno_de_caixa(_caixa(turno="", movto="T2")) == 2
    assert aut.turno_de_caixa({"turno": "", "movto": "mov T1"}) == 1
    assert aut.turno_de_caixa({"turno": "", "movto": "T3"}) is None


# ─── Resolução de chaves ─────────────────────────────────────────

def test_resolver_por_chave_estavel():
    caixas = [_caixa(idx=0), _caixa(turno="2", movto="T2", idx=1)]
    chaves = [aut.chave_de_caixa(caixas[1])]
    resolvidos, erros = aut.resolver_caixas(caixas, chaves, "2026-10-27")
    assert erros == []
    assert len(resolvidos) == 1
    assert resolvidos[0][0].turno == "2"
    assert resolvidos[0][1]["turno"] == "2"


def test_resolver_por_indice_quando_chave_mudou():
    caixas = [_caixa(idx=0), _caixa(turno="2", movto="T2", idx=1)]
    chave = {"data": "27/10/2026", "pdv": "99", "turno": "1", "movto": "T1", "row_index": 1}
    resolvidos, erros = aut.resolver_caixas(caixas, [chave], "2026-10-27")
    assert erros == []
    assert resolvidos[0][0].row_index == 1


def test_resolver_bloqueia_data_divergente():
    caixas = [_caixa(idx=0)]
    chaves = [aut.chave_de_caixa(caixas[0])]
    resolvidos, erros = aut.resolver_caixas(caixas, chaves, "2026-10-26")
    assert resolvidos == []
    assert len(erros) == 1
    assert erros[0]["ok"] is False
    assert "fora da data" in erros[0]["erro"]


def test_resolver_nao_importa_mesmo_caixa_duas_vezes():
    caixas = [_caixa(idx=0)]
    chave = aut.chave_de_caixa(caixas[0])
    resolvidos, erros = aut.resolver_caixas(caixas, [chave, chave], "2026-10-27")
    assert len(resolvidos) == 1
    assert len(erros) == 1
    assert "nao encontrado" in erros[0]["erro"]


def test_resolver_caixa_inexistente():
    caixas = [_caixa(idx=0)]
    chave = {"data": "28/10/2026", "pdv": "01", "turno": "1", "movto": "T1"}
    resolvidos, erros = aut.resolver_caixas(caixas, [chave], "2026-10-28")
    assert resolvidos == []
    assert erros and erros[0]["ok"] is False


# ─── Parsers de linhas ───────────────────────────────────────────

def test_parse_caixas_rows():
    rows = [
        {
            "i": 3,
            "cells": [
                "27/10/2026", "01", "2", "08:00", "15:00",
                "T2", "Fechado", "x", "y", "1.234,56",
            ],
        },
        {"i": 4, "cells": ["curta"]},
    ]
    caixas = aut.parse_caixas_rows(rows)
    assert len(caixas) == 1
    caixa = caixas[0]
    assert caixa.data == "27/10/2026"
    assert caixa.turno == "2"
    assert caixa.movto == "T2"
    assert caixa.status == "Fechado"
    assert caixa.valor == "1.234,56"
    assert caixa.row_index == 3


def test_parse_pagamentos_rows():
    rows = [["POS", "VISA", "VISA CREDITO", "", "10,00", "0,00", "10,00", "1"]]
    pagamentos = aut.parse_pagamentos_rows(rows)
    assert len(pagamentos) == 1
    pg = pagamentos[0]
    assert pg.subtipo == "VISA CREDITO"
    assert pg.valor_vndpos == "10,00"
    assert pg.valor_total == "10,00"
    assert pg.quantidade == "1"


def test_parse_dinheiro_rows():
    rows = [
        {"forma": "CARTAO", "valor": "10,00"},
        {"forma": " dinheiro ", "valor": "35,00"},
    ]
    assert aut.parse_dinheiro_rows(rows) == "35,00"
    assert aut.parse_dinheiro_rows([]) == ""


# ─── Config ───────────────────────────────────────────────────────

class _FakeDB:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self._seq = 0

    def search(self, table, query):
        return [
            dict(doc, id=doc_id)
            for doc_id, doc in self.docs.items()
            if all(doc.get(k) == v for k, v in query.items())
        ]

    def insert(self, table, payload):
        self._seq += 1
        doc_id = str(self._seq)
        self.docs[doc_id] = dict(payload)
        return doc_id

    def update(self, table, doc_id, payload):
        self.docs[str(doc_id)] = dict(payload)
        return True


def test_config_otimizar_default_true():
    assert config_posto.default_settings()["otimizar_automacao"] is True


def test_config_persiste_otimizar():
    db = _FakeDB()
    config_posto.save_settings(db, {"otimizar_automacao": False})
    assert config_posto.load_settings(db)["otimizar_automacao"] is False
    config_posto.save_settings(db, {"otimizar_automacao": True})
    assert config_posto.load_settings(db)["otimizar_automacao"] is True
