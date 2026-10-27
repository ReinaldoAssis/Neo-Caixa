"""Testes puros dos lançamentos financeiros do caixa restaurante."""

from __future__ import annotations

import pytest

import app.core  # noqa: F401 - inicializa o pacote antes do driver (evita ciclo)
from app.drivers.tinydb_driver import TinyDBDriver
from app.modules.conciliador import financeiro
from app.modules.conciliador.services import total_contagens_dinheiro


def _db(tmp_path):
    return TinyDBDriver(str(tmp_path / "test.json"))


def _contagem(total=100.0, moedas=0.0):
    return {
        "id": "c1",
        "label": "Geral",
        "editado": False,
        "notas": {"200": 0, "100": 0, "50": 0, "20": 0, "10": 0, "5": 0, "2": 0},
        "seriais_200": [],
        "moedas": moedas,
        "depositos": 0,
        "total": total,
    }


def _caixa(db, data="2026-10-27", moedas=0.0, notas=None, status="rascunho"):
    doc = {
        "id": "cx-1",
        "tipo": "restaurante",
        "data": data,
        "status": status,
        "dinheiro_ajuste": 0.0,
        "despesas_notas": notas or [],
        "dinheiro_moedas": moedas,
        "contagens_dinheiro": [_contagem(100.0, moedas)],
    }
    doc_id = db.insert("conciliacoes", doc)
    return doc_id, doc


# ─── Notas / migração ────────────────────────────────────────────

def test_normalizar_despesas_topo_soma_notas():
    data = {
        "despesas_notas": [
            {"id": "n1", "descricao": "GAS", "valor": 30.0},
            {"id": "n2", "descricao": "AGUA", "valor": 12.5},
        ],
        "dinheiro_ajuste": 999.0,
    }
    out = financeiro.normalizar_despesas(data)
    assert out["dinheiro_ajuste"] == 42.5
    assert len(out["despesas_notas"]) == 2


def test_normalizar_despesas_migra_ajuste_legado():
    out = financeiro.normalizar_despesas({"dinheiro_ajuste": 20.0})
    assert out["dinheiro_ajuste"] == 20.0
    assert len(out["despesas_notas"]) == 1
    nota = out["despesas_notas"][0]
    assert nota["descricao"] == "AJUSTE MANUAL"
    assert nota["legado"] is True
    assert nota["valor"] == 20.0


def test_normalizar_despesas_split_por_turno():
    data = {
        "split_mode": True,
        "turnos": {
            "1": {
                "despesas_notas": [{"id": "t1n", "descricao": "GAS", "valor": 10.0}],
                "dinheiro_ajuste": 0,
            },
            "2": {
                "dinheiro_ajuste": 15.0,
                "despesas_notas": [],
            },
        },
    }
    out = financeiro.normalizar_despesas(data)
    assert out["turnos"]["1"]["dinheiro_ajuste"] == 10.0
    assert out["turnos"]["2"]["dinheiro_ajuste"] == 15.0
    assert out["turnos"]["2"]["despesas_notas"][0]["legado"] is True
    assert out["dinheiro_ajuste"] == 25.0
    assert len(out["despesas_notas"]) == 2


def test_notas_do_caixa_split_traz_turno():
    doc = {
        "split_mode": True,
        "turnos": {
            "1": {"despesas_notas": [{"id": "a", "descricao": "A", "valor": 5.0}]},
            "2": {"despesas_notas": [{"id": "b", "descricao": "B", "valor": 7.0}]},
        },
    }
    notas = financeiro.notas_do_caixa(doc)
    assert [(n["id"], n["turno"]) for n in notas] == [("a", 1), ("b", 2)]


# ─── Moedas do dia ──────────────────────────────────────────────

def test_valor_moedas_do_dia_soma_so_restaurante_da_data(tmp_path):
    db = _db(tmp_path)
    _caixa(db, data="2026-10-27", moedas=10.0)
    _caixa(db, data="2026-10-27", moedas=2.5)
    _caixa(db, data="2026-10-26", moedas=99.0)
    db.insert("conciliacoes", {"tipo": "posto", "data": "2026-10-27", "dinheiro_moedas": 50.0})
    assert financeiro.valor_moedas_do_dia(db, "2026-10-27") == 12.5


# ─── Pendentes / dedupe / complemento ───────────────────────────

def test_pendentes_traz_moedas_e_despesas(tmp_path):
    db = _db(tmp_path)
    caixa_id, _ = _caixa(
        db,
        moedas=10.0,
        notas=[
            {"id": "n1", "descricao": "GAS", "valor": 30.0},
            {"id": "n2", "descricao": "AGUA", "valor": 12.5},
        ],
    )
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    itens = pend["itens"]
    moedas = next(i for i in itens if i["tipo"] == financeiro.TIPO_MOEDAS)
    assert moedas["valor"] == 10.0
    assert moedas["chave"] == "transferencia_moedas|2026-10-27"
    despesas = [i for i in itens if i["tipo"] == financeiro.TIPO_DESPESA]
    assert [d["descricao"] for d in despesas] == ["GAS", "AGUA"]
    assert all(d["selecionavel"] for d in despesas)
    assert pend["resumo"]["pendencias"] == 3


def test_moedas_lancada_nao_fica_pendente(tmp_path):
    db = _db(tmp_path)
    caixa_id, _ = _caixa(db, moedas=10.0)
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    item = next(i for i in pend["itens"] if i["tipo"] == financeiro.TIPO_MOEDAS)
    financeiro.registrar_resultado(db, item, True)

    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    moedas = [i for i in pend["itens"] if i["tipo"] == financeiro.TIPO_MOEDAS]
    assert len(moedas) == 1
    assert moedas[0]["status"] == financeiro.STATUS_LANCADO
    assert moedas[0]["selecionavel"] is False
    assert moedas[0]["lancado_em"]


def test_moedas_complemento_quando_total_aumenta(tmp_path):
    db = _db(tmp_path)
    caixa_id, doc = _caixa(db, moedas=10.0)
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    item = next(i for i in pend["itens"] if i["tipo"] == financeiro.TIPO_MOEDAS)
    financeiro.registrar_resultado(db, item, True)

    doc["dinheiro_moedas"] = 15.0
    db.update("conciliacoes", caixa_id, doc)

    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    delta = next(
        i for i in pend["itens"]
        if i["tipo"] == financeiro.TIPO_MOEDAS and i["selecionavel"]
    )
    assert delta["valor"] == 5.0
    assert delta["complemento"] is True
    assert "delta" in delta["chave"]

    financeiro.registrar_resultado(db, delta, True)
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    assert not any(
        i["tipo"] == financeiro.TIPO_MOEDAS and i["selecionavel"]
        for i in pend["itens"]
    )


def test_moedas_divergente_quando_total_diminui(tmp_path):
    db = _db(tmp_path)
    caixa_id, doc = _caixa(db, moedas=10.0)
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    item = next(i for i in pend["itens"] if i["tipo"] == financeiro.TIPO_MOEDAS)
    financeiro.registrar_resultado(db, item, True)

    doc["dinheiro_moedas"] = 4.0
    db.update("conciliacoes", caixa_id, doc)

    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    divergente = next(
        i for i in pend["itens"] if i["status"] == financeiro.STATUS_DIVERGENTE
    )
    assert divergente["selecionavel"] is False


def test_despesa_lancada_exige_forcar_para_relancar(tmp_path):
    db = _db(tmp_path)
    caixa_id, _ = _caixa(
        db, notas=[{"id": "n1", "descricao": "GAS", "valor": 30.0}]
    )
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    item = next(i for i in pend["itens"] if i["tipo"] == financeiro.TIPO_DESPESA)
    financeiro.registrar_resultado(db, item, True)

    with pytest.raises(ValueError):
        financeiro.selecionar_por_chaves(db, caixa_id, [item["chave"]], False, {})

    itens = financeiro.selecionar_por_chaves(
        db, caixa_id, [item["chave"]], True, {}
    )
    assert len(itens) == 1
    assert itens[0]["valor"] == 30.0


def test_caixa_arquivado_bloqueia(tmp_path):
    db = _db(tmp_path)
    caixa_id, _ = _caixa(db, moedas=10.0, status="arquivado")
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    assert pend["resumo"]["bloqueado"] is True
    assert all(not i["selecionavel"] for i in pend["itens"])
    with pytest.raises(ValueError):
        financeiro.selecionar_por_chaves(
            db, caixa_id, ["transferencia_moedas|2026-10-27"], False, {}
        )


def test_caixa_sem_data_bloqueia(tmp_path):
    db = _db(tmp_path)
    caixa_id, _ = _caixa(db, data="", moedas=10.0)
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    assert pend["resumo"]["bloqueado"] is True


def test_config_financeiro_defaults():
    cfg = financeiro.config_financeiro({})
    assert cfg["financeiro_origem"] == "CAIXA ADM"
    assert cfg["financeiro_destino"] == "MOEDAS"
    assert cfg["financeiro_descricao_moedas"] == "MOEDAS"
    assert cfg["financeiro_categoria"] == "02.03.01 Fornecedores"
    assert cfg["financeiro_conta"] == "CAIXA ADM"
    assert cfg["financeiro_centro_custo"] == "LAGOA CAFE CONVENIENCIA"
    assert cfg["financeiro_tipo_documento"] == "DINHEIRO"


# ─── Conciliação: DINHEIRO = contagem + notas ───────────────────

def test_normalize_restaurante_com_notas(tmp_path):
    from app.modules.conciliador import _normalize_restaurante

    doc = {
        "data": "2026-10-24",
        "tipo": "restaurante",
        "categorias": {"DINHEIRO": {"sistema": 0.0, "real": 0.0}},
        "contagens_dinheiro": [_contagem(100.0)],
        "despesas_notas": [
            {"id": "n1", "descricao": "GAS", "valor": 20.0},
        ],
    }
    out = _normalize_restaurante(doc)
    assert out["dinheiro_ajuste"] == 20.0
    assert out["dinheiro_real"] == 120.0
    assert total_contagens_dinheiro(out["contagens_dinheiro"]) == 100.0


def test_normalize_restaurante_migra_ajuste_antigo():
    from app.modules.conciliador import _normalize_restaurante

    out = _normalize_restaurante({
        "data": "2026-10-24",
        "tipo": "restaurante",
        "categorias": {},
        "contagens_dinheiro": [_contagem(100.0)],
        "dinheiro_ajuste": 20.0,
    })
    assert out["dinheiro_ajuste"] == 20.0
    assert out["dinheiro_real"] == 120.0
    assert out["despesas_notas"][0]["legado"] is True


def test_falha_no_relancamento_preserva_valor_lancado(tmp_path):
    db = _db(tmp_path)
    caixa_id, doc = _caixa(
        db, notas=[{"id": "n1", "descricao": "GAS", "valor": 30.0}]
    )
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    item = next(i for i in pend["itens"] if i["tipo"] == financeiro.TIPO_DESPESA)
    financeiro.registrar_resultado(db, item, True)

    doc["despesas_notas"] = [{"id": "n1", "descricao": "GAS", "valor": 40.0}]
    db.update("conciliacoes", caixa_id, doc)
    pend = financeiro.pendentes_caixa(db, caixa_id, {})
    relancar = next(i for i in pend["itens"] if i["tipo"] == financeiro.TIPO_DESPESA)
    assert relancar["valor"] == 30.0
    assert relancar["valor_atual"] == 40.0

    financeiro.registrar_resultado(
        db,
        {**relancar, "valor": 40.0},
        False,
        "Cloudfy recusou",
    )
    registro = next(
        r for r in db.all(financeiro.TABLE)
        if r["chave"] == relancar["chave"]
    )
    assert registro["valor"] == 30.0
    assert registro["lancado_em"]
    assert registro["erro"] == "Cloudfy recusou"
