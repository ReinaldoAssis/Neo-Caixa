"""Testes da consolidacao de contagens com nomes das notas de R$ 200."""

from __future__ import annotations

from app.modules.conciliador.export import _formatar_seriais_200
from app.modules.conciliador.services import consolidate_contagens


def _contagem(label: str, serials: list[str], nomes: list[str] | None = None) -> dict:
    return {
        "id": label,
        "label": label,
        "editado": False,
        "notas": {"200": len(serials), "100": 0, "50": 0, "20": 0, "10": 0, "5": 0, "2": 0},
        "seriais_200": serials,
        "nomes_200": nomes or [],
        "moedas": 0,
        "depositos": 0,
        "total": len(serials) * 200,
    }


def _geral() -> dict:
    return {
        "id": "geral",
        "label": "Geral",
        "editado": False,
        "notas": {},
        "seriais_200": [],
        "nomes_200": [],
        "moedas": 0,
        "depositos": 0,
        "total": 0,
    }


def test_consolida_seriais_e_nomes_na_mesma_ordem():
    contagens = [
        _geral(),
        _contagem("1", ["11111", "22222"], ["Fulano", ""]),
        _contagem("2", ["33333"], ["Beltrano"]),
    ]
    geral = consolidate_contagens(contagens)
    assert geral["seriais_200"] == ["11111", "22222", "33333"]
    assert geral["nomes_200"] == ["Fulano", "", "Beltrano"]


def test_consolida_sem_nomes_mantem_alinhamento():
    contagens = [
        _geral(),
        _contagem("1", ["11111", "22222"]),
    ]
    geral = consolidate_contagens(contagens)
    assert geral["seriais_200"] == ["11111", "22222"]
    assert geral["nomes_200"] == ["", ""]


def test_geral_editada_preserva_nomes():
    geral = _geral()
    geral.update({"editado": True, "seriais_200": ["99999"], "nomes_200": ["Manual"]})
    out = consolidate_contagens([geral, _contagem("1", ["11111"], ["Fulano"])])
    assert out["seriais_200"] == ["99999"]
    assert out["nomes_200"] == ["Manual"]


def test_formato_pdf_serial_e_nome():
    assert _formatar_seriais_200(["11111", "22222"], ["Fulano", ""]) == (
        "11111 - Fulano, 22222"
    )
    assert _formatar_seriais_200([], []) == ""
    assert _formatar_seriais_200(["33333"], None) == "33333"
