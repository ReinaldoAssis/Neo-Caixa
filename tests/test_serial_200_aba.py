"""Serial obrigatorio: aba com nota de R$ 200 precisa de nome proprio."""

from __future__ import annotations

from app.modules.conciliador.services import validate_contagens


def _contagem(label: str, qty200: int = 1, serial: str = "12345", editado: bool = False):
    return {
        "label": label,
        "editado": editado,
        "notas": {"200": qty200},
        "seriais_200": [serial] * qty200 if qty200 else [],
    }


def test_aba_numerica_com_200_exige_nome_proprio():
    erros = validate_contagens([_contagem("1")], "obrigatorio_todas")
    assert len(erros) == 1
    assert "renomeie" in erros[0].lower()


def test_aba_com_nome_proprio_passa():
    assert validate_contagens([_contagem("Joao")], "obrigatorio_todas") == []


def test_aba_geral_nao_exige_renomear():
    assert validate_contagens([_contagem("Geral")], "obrigatorio_todas") == []


def test_modo_opcional_nao_exige_renomear():
    assert validate_contagens([_contagem("1")], "opcional_todas") == []


def test_aba_numerica_sem_200_nao_exige_renomear():
    assert validate_contagens([_contagem("1", qty200=0)], "obrigatorio_todas") == []


def test_renomear_e_serial_sao_erros_separados():
    erros = validate_contagens([_contagem("2", serial="12")], "obrigatorio_todas")
    assert len(erros) == 2
    assert "renomeie" in erros[0].lower()
    assert "serial" in erros[1].lower()
