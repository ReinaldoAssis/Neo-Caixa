from app.modules.conciliador.services import total_contagens_dinheiro


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


def test_total_contagens_sums_all_gerais():
    assert total_contagens_dinheiro([_contagem(100), _contagem(50)]) == 150.0
    assert total_contagens_dinheiro([]) == 0.0
    assert total_contagens_dinheiro(None) == 0.0


def test_normalize_restaurante_applies_dinheiro_ajuste():
    from app.modules.conciliador import _normalize_restaurante

    doc = {
        "data": "2026-10-24",
        "tipo": "restaurante",
        "categorias": {"DINHEIRO": {"sistema": 0.0, "real": 120.0}},
        "contagens_dinheiro": [_contagem(100.0)],
        "dinheiro_ajuste": 20.0,
    }

    out = _normalize_restaurante(doc)

    assert out["dinheiro_ajuste"] == 20.0
    assert out["dinheiro_real"] == 120.0

    from app.modules.conciliador.services import build_conciliation_rows_restaurante

    rows = build_conciliation_rows_restaurante(out["categorias"], [], out["dinheiro_real"])
    dinheiro = next(row for row in rows if row["key"] == "DINHEIRO")
    assert dinheiro["real"] == 120.0


def test_normalize_restaurante_without_ajuste_uses_contagem():
    from app.modules.conciliador import _normalize_restaurante

    doc = {
        "data": "2026-10-24",
        "tipo": "restaurante",
        "categorias": {},
        "contagens_dinheiro": [_contagem(80.0)],
    }

    out = _normalize_restaurante(doc)

    assert out["dinheiro_ajuste"] == 0.0
    assert out["dinheiro_real"] == 80.0
