"""Testes da conferência do extrato ADM x caixa restaurante."""

from __future__ import annotations

from app.drivers.tinydb_driver import TinyDBDriver
from app.modules.conciliador import conferencia_adm


def _db(tmp_path):
    return TinyDBDriver(str(tmp_path / "test.json"))


def _caixa(db, data="2026-10-26", dinheiro=100.0, status="rascunho", tipo="restaurante"):
    db.insert(
        "conciliacoes",
        {
            "tipo": tipo,
            "data": data,
            "status": status,
            "dinheiro_real": dinheiro,
        },
    )


def _extrato(total=150.0, linhas=None):
    linhas = linhas or [
        {"descricao": "FECHAMENTO", "valor": 150.0},
    ]
    return {
        "total": total,
        "total_texto": f"R$ {total:.2f}",
        "linhas": linhas,
        "soma_linhas": round(sum(item["valor"] for item in linhas), 2),
        "extrato_inconsistente": False,
    }


def test_conferencia_bate_somando_caixas_nao_arquivados(tmp_path):
    db = _db(tmp_path)
    _caixa(db, dinheiro=100.0)
    _caixa(db, dinheiro=50.0)
    _caixa(db, dinheiro=999.0, status="arquivado")
    _caixa(db, dinheiro=999.0, data="2026-10-25")
    _caixa(db, dinheiro=999.0, tipo="posto")

    out = conferencia_adm.avaliar(db, "2026-10-26", _extrato(150.0))
    assert out["caixa_total"] == 150.0
    assert out["caixa_qtd"] == 2
    assert out["diferenca"] == 0.0
    assert out["status"] == conferencia_adm.STATUS_BATE


def test_conferencia_nao_bate(tmp_path):
    db = _db(tmp_path)
    _caixa(db, dinheiro=140.0)
    out = conferencia_adm.avaliar(db, "2026-10-26", _extrato(150.0))
    assert out["diferenca"] == 10.0
    assert out["status"] == conferencia_adm.STATUS_NAO_BATE


def test_conferencia_sem_caixa(tmp_path):
    db = _db(tmp_path)
    out = conferencia_adm.avaliar(db, "2026-10-26", _extrato(150.0))
    assert out["caixa_qtd"] == 0
    assert out["diferenca"] is None
    assert out["status"] == conferencia_adm.STATUS_SEM_CAIXA


def test_conferencia_sinaliza_extrato_inconsistente(tmp_path):
    db = _db(tmp_path)
    _caixa(db, dinheiro=100.0)
    extrato = _extrato(150.0, [{"descricao": "A", "valor": 120.0}])
    out = conferencia_adm.avaliar(db, "2026-10-26", extrato)
    assert out["extrato_inconsistente"] is True
    assert out["soma_linhas"] == 120.0


def test_historico_guarda_e_lista(tmp_path):
    db = _db(tmp_path)
    _caixa(db, dinheiro=150.0)
    out = conferencia_adm.avaliar(db, "2026-10-26", _extrato(150.0))
    salvo = conferencia_adm.registrar(db, out)
    assert salvo["id"]
    assert salvo["status"] == conferencia_adm.STATUS_BATE

    lista = conferencia_adm.listar(db)
    assert len(lista) == 1
    assert lista[0]["data"] == "2026-10-26"
    assert lista[0]["linhas"][0]["descricao"] == "FECHAMENTO"
