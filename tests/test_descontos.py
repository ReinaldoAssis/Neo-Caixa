"""Parser do relatorio de descontos do Cloudfy (venda a prazo + >10%)."""

from __future__ import annotations

from pathlib import Path

import openpyxl

from app.modules.conciliador import automacao as aut
from app.modules.conciliador.descontos import normalize_desconto


def _salvar(tmp_path: Path, header: list, linhas: list) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    for linha in linhas:
        ws.append(linha)
    destino = tmp_path / "descontos.xlsx"
    wb.save(destino)
    wb.close()
    return str(destino)


HEADER = [
    "Tipo", "Motivo", "Data", "Caixa", "Cupom", "Qtde. itens",
    "Valor", "Cliente", "Forma de pagamento",
]


def test_parser_mantem_venda_a_prazo_e_desconto_acima_de_10(tmp_path):
    caminho = _salvar(tmp_path, HEADER, [
        ["DESCONTO", "DESCONTO COLABORADOR (10%)", "01/09/2026", "PDV", "1", 2, 1.99, "", "PIX"],
        ["DESCONTO", "DESCONTO BIU (15%)", "02/09/2026", "PDV", "2", 1, 10.0, "", "CARTAO DEBITO"],
        ["DESCONTO", "MOTIVO NAO INFORMADO", "03/09/2026", "PDV", "3", 1, 5.0, "", "Venda a prazo"],
        ["DESCONTO", "DESCONTO (5%)", "04/09/2026", "PDV", "4", 1, 5.0, "", "PIX"],
        ["DESCONTO", "DESCONTO 12,5%", "05/09/2026", "PDV", "5", 1, 7.0, "", "DINHEIRO"],
    ])
    cupons = aut.parse_descontos_xlsx(caminho)
    assert [c["cupom"] for c in cupons] == ["2", "3", "5"]
    assert cupons[0]["percentual"] == 15.0
    assert cupons[1]["percentual"] == 0.0
    assert cupons[2]["percentual"] == 12.5


def test_parser_usa_coluna_percentual_em_fracao(tmp_path):
    header = HEADER + ["Percentual"]
    caminho = _salvar(tmp_path, header, [
        ["DESCONTO", "OUTRO MOTIVO", "01/09/2026", "PDV", "10", 1, 20.0, "", "PIX", 0.2],
        ["DESCONTO", "OUTRO MOTIVO", "02/09/2026", "PDV", "11", 1, 30.0, "", "PIX", 5],
    ])
    cupons = aut.parse_descontos_xlsx(caminho)
    assert [c["cupom"] for c in cupons] == ["10"]
    assert cupons[0]["percentual"] == 20.0


def test_parser_sem_cupom_valido_nao_quebra(tmp_path):
    caminho = _salvar(tmp_path, HEADER, [
        ["DESCONTO", "MOTIVO NAO INFORMADO", "01/09/2026", "PDV", "1", 1, 1.0, "", "PIX"],
    ])
    assert aut.parse_descontos_xlsx(caminho) == []


def test_normalize_desconto_guarda_percentual():
    doc = normalize_desconto({
        "data": "01/09/2026",
        "cupom": "1",
        "valor": "12,34",
        "percentual": "15%",
    })
    assert doc["percentual"] == 15.0
    assert doc["valor"] == 12.34


def test_upsert_faz_backfill_do_percentual_sem_perder_conferido(tmp_path):
    from app.drivers.tinydb_driver import TinyDBDriver
    from app.modules.conciliador.descontos import upsert_descontos

    db = TinyDBDriver(str(tmp_path / "descontos.json"))
    db.insert("descontos", {
        "chave": "01/09/2026|1",
        "data": "01/09/2026",
        "cupom": "1",
        "valor": 5.0,
        "conferido": True,
    })

    resumo = upsert_descontos(db, [{
        "data": "01/09/2026",
        "cupom": "1",
        "valor": 5.0,
        "percentual": 15.0,
    }])

    assert resumo["inseridos"] == 0
    assert resumo["ignorados"] == 1
    salvo = db.all("descontos")[0]
    assert salvo["percentual"] == 15.0
    assert salvo["conferido"] is True
