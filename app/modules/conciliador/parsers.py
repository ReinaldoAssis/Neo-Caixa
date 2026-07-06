from __future__ import annotations

import csv
import re
import tempfile
from pathlib import Path

from app.modules.conciliador.constants import (
    empty_categories_posto,
    empty_categories_restaurante,
    CATEGORIAS_RESTAURANTE,
)

OLE2_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


def parse_money(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("R$", "").replace("\xa0", " ").strip()
    text = re.sub(r"[^\d,.\-]", "", text)
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError as exc:
        raise ValueError(f"Valor monetario invalido: {value!r}") from exc


def normalize_text(text: object) -> str:
    raw = "" if text is None else str(text)
    replacements = {
        "Á": "A", "À": "A", "Â": "A", "Ã": "A", "Ä": "A",
        "É": "E", "Ê": "E", "Í": "I", "Ó": "O", "Ô": "O",
        "Õ": "O", "Ú": "U", "Ü": "U", "Ç": "C",
    }
    out = raw.strip().upper()
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return " ".join(out.split())


# ─── Posto: Caixa CSV ────────────────────────────────────────────

SYSTEM_CATEGORY_MAP = {
    "BR PREMMIA CARTAO": "PREMMIA_CARTAO",
    "BR PREMMIA GENERICO": "PREMMIA_CUPOM",
    "BR PREMMIA GENERICO / CUPOM": "PREMMIA_CUPOM",
    "BR PREMMIA CUPOM": "PREMMIA_CUPOM",
    "BR PREMMIA PIX": "PREMMIA_PIX",
    "BR PREMMIA VALE": "PREMMIA_VALE",
    "CARTAO FITCARD": "FITCARD",
    "PAG PIX": "PAG_PIX",
    "POS PAGSEGURO MASTER.CRE": "MASTERCARD_CREDITO",
    "SMART PAGSEGURO MASTER.C": "MASTERCARD_CREDITO",
    "POS PAGSEGURO MASTER.DEB": "MASTERCARD_DEBITO",
    "SMART PAGSEGURO MASTER.D": "MASTERCARD_DEBITO",
    "POS PAGSEGURO ELO CRED": "ELO_CREDITO",
    "SMART PAGSEGURO ELO CRED": "ELO_CREDITO",
    "POS PAGSEGURO ELO DEBITO": "ELO_DEBITO",
    "SMART PAGSEGURO ELO DEBI": "ELO_DEBITO",
    "POS PAGSEGURO VISA CREDI": "VISA_CREDITO",
    "SMART PAGSEGURO VISA CRE": "VISA_CREDITO",
    "POS PAGSEGURO VISA DEBIT": "VISA_DEBITO",
    "SMART PAGSEGURO VISA DEB": "VISA_DEBITO",
}

INFO_FIELDS = {
    "SANGRIA": "sangria",
    "NOTAS A PRAZO": "notas_a_prazo",
    "DESPESAS DO POSTO": "despesas",
}


def parse_caixa_csv(file_content: bytes, filename: str) -> dict:
    temp_path = Path(tempfile.gettempdir()) / f"caixa_{filename}"
    temp_path.write_bytes(file_content)
    try:
        return _parse_caixa_csv(temp_path)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def _parse_caixa_csv(path: Path) -> dict:
    with open(path, "r", encoding="latin-1", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))

    first_lines = [";".join(row) for row in rows[:5]]
    if not any("CAIXA GERAL" in line.upper() for line in first_lines):
        raise ValueError("O arquivo selecionado nao parece ser um CSV do CAIXA GERAL.")

    header_index = None
    for idx, row in enumerate(rows):
        normalized = [normalize_text(cell) for cell in row]
        if len(normalized) >= 2 and normalized[0] == "ENTRADAS" and normalized[1].startswith("SA"):
            header_index = idx
            break
    if header_index is None:
        raise ValueError("Nao encontrei a secao FINANCEIRO com o cabecalho Entradas/Saidas.")

    categorias = empty_categories_posto()
    info = {"sangria": 0.0, "notas_a_prazo": 0.0, "despesas": 0.0}
    detected: list[dict] = []

    for row in rows[header_index + 1:]:
        if not row:
            continue
        if normalize_text(row[0]).startswith("SUBTOTAL"):
            break
        if len(row) < 4:
            continue
        name = normalize_text(row[2])
        value_text = row[3].strip() if len(row) > 3 else ""
        if not name or not value_text:
            continue
        value = parse_money(value_text)
        if name in SYSTEM_CATEGORY_MAP:
            key = SYSTEM_CATEGORY_MAP[name]
            categorias[key]["sistema"] = round(categorias[key]["sistema"] + value, 2)
            detected.append({"nome": name, "categoria": key, "valor": value})
        elif name in INFO_FIELDS:
            info[INFO_FIELDS[name]] = value
            detected.append({"nome": name, "categoria": INFO_FIELDS[name], "valor": value})

    return {
        "categorias": categorias,
        "sangria": info["sangria"],
        "notas_a_prazo": info["notas_a_prazo"],
        "despesas": info["despesas"],
        "detected": detected,
        "total_saidas": round(sum(item["valor"] for item in detected), 2),
    }


# ─── Posto: PagBank CSV ──────────────────────────────────────────

def _posto_pagbank_category(bandeira: str, forma: str) -> str | None:
    brand = normalize_text(bandeira)
    method = normalize_text(forma)
    if method == "PIX" or (not brand and method == "PIX"):
        return "PAG_PIX"
    if brand == "VISA" and method.startswith("DEBIT"):
        return "VISA_DEBITO"
    if brand == "VISA" and method.startswith("CREDIT"):
        return "VISA_CREDITO"
    if brand == "MASTERCARD" and method.startswith("DEBIT"):
        return "MASTERCARD_DEBITO"
    if brand == "MASTERCARD" and method.startswith("CREDIT"):
        return "MASTERCARD_CREDITO"
    if brand == "ELO" and method.startswith("DEBIT"):
        return "ELO_DEBITO"
    if brand == "ELO" and method.startswith("CREDIT"):
        return "ELO_CREDITO"
    return None


def parse_pagbank_csv(file_content: bytes, filename: str) -> dict:
    temp_path = Path(tempfile.gettempdir()) / f"pagbank_{filename}"
    temp_path.write_bytes(file_content)
    try:
        return _parse_pagbank_csv(temp_path)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def _parse_pagbank_csv(path: Path) -> dict:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames or "Código da Transação" not in reader.fieldnames:
            raise ValueError("O arquivo selecionado nao parece ser o CSV PagBank esperado.")

        categorias = empty_categories_posto()
        approved = 0
        ignored = 0
        for row in reader:
            if normalize_text(row.get("Status")) != "APROVADA":
                ignored += 1
                continue
            key = _posto_pagbank_category(row.get("Bandeira", ""), row.get("Forma de Pagamento", ""))
            if not key:
                ignored += 1
                continue
            value = parse_money(row.get("Valor Bruto", "0"))
            categorias[key]["site"] = round(categorias[key]["site"] + value, 2)
            approved += 1

    return {
        "categorias": categorias,
        "registros_aprovados": approved,
        "registros_ignorados": ignored,
    }


# ─── Posto: Premmia XLS ──────────────────────────────────────────

def detectar_formato_premmia(content: bytes) -> str:
    return "xls" if content[:8] == OLE2_MAGIC else "csv"


def _premmia_category(forma: object) -> str | None:
    method = normalize_text(forma)
    if method == "PIX":
        return "PREMMIA_PIX"
    if method in {"CARTAO APP", "CARTAO"}:
        return "PREMMIA_CARTAO"
    if method in {"DESCONTO", "CUPOM"}:
        return "PREMMIA_CUPOM"
    return None


def _rows_from_xls(content: bytes) -> list[dict]:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("Instale xlrd para processar arquivos Premmia.") from exc

    temp = tempfile.NamedTemporaryFile(suffix=".xls", delete=False)
    try:
        temp.write(content)
        temp.close()
        book = xlrd.open_workbook(temp.name)
    finally:
        try:
            Path(temp.name).unlink()
        except OSError:
            pass

    if "Conferência" in book.sheet_names():
        sheet = book.sheet_by_name("Conferência")
    elif "Conferencia" in book.sheet_names():
        sheet = book.sheet_by_name("Conferencia")
    else:
        raise ValueError("Nao encontrei a planilha 'Conferencia' no arquivo Premmia.")

    header_row = None
    headers: list[str] = []
    for row_idx in range(sheet.nrows):
        values = [str(sheet.cell_value(row_idx, col)).strip() for col in range(sheet.ncols)]
        normalized = [normalize_text(v) for v in values]
        if "CPF" in normalized and "STATUS" in normalized:
            header_row = row_idx
            headers = values
            break
    if header_row is None:
        raise ValueError("Nao encontrei o cabecalho esperado no arquivo Premmia.")

    records = []
    for row_idx in range(header_row + 1, sheet.nrows):
        record = {}
        for col_idx, header in enumerate(headers):
            record[header] = sheet.cell_value(row_idx, col_idx)
        records.append(record)
    return records


def _premmia_get(record: dict, wanted: str) -> object:
    wanted_norm = normalize_text(wanted)
    for key, value in record.items():
        if normalize_text(key) == wanted_norm:
            return value
    return ""


def parse_premmia_file(file_content: bytes, filename: str) -> dict:
    formato = detectar_formato_premmia(file_content)
    if formato != "xls":
        raise ValueError("O relatorio Premmia deve ser um arquivo Excel .xls valido.")
    records = _rows_from_xls(file_content)
    categorias = empty_categories_posto()
    processed = 0
    ignored = 0

    for record in records:
        if normalize_text(_premmia_get(record, "Status")) != "PROCESSADA":
            ignored += 1
            continue
        key = _premmia_category(_premmia_get(record, "Forma de Pagamento"))
        if not key:
            ignored += 1
            continue
        value = parse_money(_premmia_get(record, "Valor líquido"))
        categorias[key]["site"] = round(categorias[key]["site"] + value, 2)
        processed += 1

    return {
        "formato": formato,
        "categorias": categorias,
        "transacoes_processadas": processed,
        "transacoes_ignoradas": ignored,
    }


# ─── Restaurante: PagBank CSV ────────────────────────────────────

RESTAURANTE_CATEGORY_MAP: dict[tuple[str, str], str] = {
    ("PIX", "PIX"): "PIX",
    ("ELO", "DEBITO"): "ELO_DEBITO",
    ("ELO", "CREDITO"): "ELO_CR",
    ("MASTERCARD", "DEBITO"): "MAESTRO",
    ("MASTERCARD", "CREDITO"): "MASTERCARD",
    ("VISA", "DEBITO"): "VC_ELECTRON",
    ("VISA", "CREDITO"): "VISA",
    ("AMEX", "CREDITO"): "AMEX",
    ("AMEX", "AMBOS"): "AMEX",
}


def _restaurante_category_key(bandeira: str, forma: str) -> tuple[str, str]:
    brand = normalize_text(bandeira)
    method = normalize_text(forma)
    if not brand and method == "PIX":
        return ("PIX", "PIX")
    if brand == "ELO":
        return ("ELO", "DEBITO" if method.startswith("DEBIT") else "CREDITO")
    if brand == "MASTERCARD":
        return ("MASTERCARD", "DEBITO" if method.startswith("DEBIT") else "CREDITO")
    if brand == "VISA":
        return ("VISA", "DEBITO" if method.startswith("DEBIT") else "CREDITO")
    if brand == "AMEX":
        return ("AMEX", "CREDITO" if method.startswith("CREDIT") else method)
    return (brand, method)


def parse_restaurante_pagbank_csv(
    file_content: bytes,
    filename: str,
    hora_ini: str | None = None,
    hora_fim: str | None = None,
) -> dict:
    temp_path = Path(tempfile.gettempdir()) / f"rest_pagbank_{filename}"
    temp_path.write_bytes(file_content)
    try:
        return _parse_restaurante_pagbank_csv(temp_path, hora_ini, hora_fim)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def _parse_restaurante_pagbank_csv(
    path: Path,
    hora_ini: str | None = None,
    hora_fim: str | None = None,
) -> dict:
    from datetime import datetime

    t_ini = None
    t_fim = None
    if hora_ini and hora_fim:
        try:
            t_ini = datetime.strptime(hora_ini.strip(), "%H:%M").time()
            t_fim = datetime.strptime(hora_fim.strip(), "%H:%M").time()
        except ValueError:
            raise ValueError("Horario invalido. Use o formato HH:MM.")

    categorias = empty_categories_restaurante()
    approved = 0

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames or "Código da Transação" not in reader.fieldnames:
            raise ValueError("O arquivo selecionado nao parece ser o CSV PagBank esperado.")

        for row in reader:
            if normalize_text(row.get("Status", "")) != "APROVADA":
                continue
            raw_key = _restaurante_category_key(
                row.get("Bandeira", ""), row.get("Forma de Pagamento", "")
            )
            key = RESTAURANTE_CATEGORY_MAP.get(raw_key)
            if not key or key == "DINHEIRO":
                continue

            if t_ini and t_fim:
                dt_str = row.get("Data da Transação", "")
                if dt_str:
                    try:
                        tx_dt = datetime.strptime(dt_str.strip(), "%d/%m/%Y %H:%M")
                        tx_time = tx_dt.time()
                        if not (t_ini <= tx_time <= t_fim):
                            continue
                    except ValueError:
                        pass

            value = parse_money(row.get("Valor Bruto", "0"))
            categorias[key]["real"] = round(categorias[key]["real"] + value, 2)
            approved += 1

    return {
        "categorias": categorias,
        "registros_aprovados": approved,
    }
