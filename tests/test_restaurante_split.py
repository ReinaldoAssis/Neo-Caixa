CSV = (
    "Código da Transação;Status;Bandeira;Forma de Pagamento;Valor Bruto;Data da Transação\n"
    "1;Aprovada;Visa;Crédito;10,00;19/07/2026 10:00\n"
    "2;Aprovada;Visa;Crédito;20,00;19/07/2026 15:00\n"
    "3;Aprovada;;Pix;5,00;19/07/2026 09:00\n"
    "4;Negada;Visa;Crédito;99,00;19/07/2026 09:00\n"
    "5;Aprovada;Mastercard;Débito;30,00;19/07/2026 20:00\n"
)


def test_split_by_time_places_transactions_in_turns():
    from app.modules.conciliador.parsers import parse_restaurante_pagbank_split

    result = parse_restaurante_pagbank_split(
        CSV.encode("utf-8"), "pag1907.csv", "14:00"
    )

    turno1 = result["turno1"]
    turno2 = result["turno2"]

    assert turno1["registros_aprovados"] == 2
    assert turno1["categorias"]["VISA"]["real"] == 10.0
    assert turno1["categorias"]["PIX"]["real"] == 5.0

    assert turno2["registros_aprovados"] == 2
    assert turno2["categorias"]["VISA"]["real"] == 20.0
    assert turno2["categorias"]["MAESTRO"]["real"] == 30.0
    assert turno2["categorias"]["DINHEIRO"]["real"] == 0.0


def test_split_invalid_time_raises():
    from app.modules.conciliador.parsers import parse_restaurante_pagbank_split

    try:
        parse_restaurante_pagbank_split(CSV.encode("utf-8"), "x.csv", "25:99")
    except ValueError as exc:
        assert "HH:MM" in str(exc)
    else:
        raise AssertionError("esperava ValueError")
