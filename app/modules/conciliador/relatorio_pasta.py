"""Localizacao do relatorio CSV do restaurante em uma pasta configuravel.

O PagBank exporta o relatorio com o nome ``pagMMDD.csv`` (ex.: ``pag1024.csv``
para 24 de outubro).  A pasta e configurada em Configuracoes > Geral e o
arquivo do dia do caixa e importado automaticamente.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

REPORT_PATTERN = re.compile(r"^pag(\d{3,4})\.csv$", re.IGNORECASE)


def _month_day_from_token(token: str) -> tuple[int, int] | None:
    if len(token) == 4:
        month, day = int(token[:2]), int(token[2:])
    else:
        month, day = int(token[0]), int(token[1:])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return month, day


def report_filename_for_date(iso_date: str) -> str:
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"pag{dt.month:02d}{dt.day:02d}.csv"


def find_report_file(directory: str | Path, iso_date: str) -> Path | None:
    """Return the ``pagMMDD.csv`` that matches ``iso_date``, if any."""
    if not directory:
        return None
    base = Path(directory).expanduser()
    if not base.is_dir():
        return None
    try:
        dt = datetime.strptime(str(iso_date), "%Y-%m-%d")
    except (TypeError, ValueError):
        return None

    matches: list[Path] = []
    try:
        entries = list(base.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.is_file():
            continue
        match = REPORT_PATTERN.match(entry.name)
        if not match:
            continue
        if _month_day_from_token(match.group(1)) == (dt.month, dt.day):
            matches.append(entry)

    if not matches:
        return None
    expected = report_filename_for_date(iso_date).lower()
    matches.sort(key=lambda p: (0 if p.name.lower() == expected else 1, p.name.lower()))
    return matches[0]


def list_reports(directory: str | Path) -> list[Path]:
    base = Path(directory).expanduser() if directory else None
    if not base or not base.is_dir():
        return []
    try:
        entries = [p for p in base.iterdir() if p.is_file() and REPORT_PATTERN.match(p.name)]
    except OSError:
        return []
    return sorted(entries, key=lambda p: p.name.lower())


def resolve_report_file(directory: str | Path, filename: str) -> Path:
    """Resolve ``filename`` inside ``directory``, rejecting path traversal."""
    if not directory:
        raise ValueError("Pasta padrao do relatorio CSV nao configurada.")
    base = Path(directory).expanduser()
    if not base.is_dir():
        raise ValueError("Pasta configurada nao existe ou nao e um diretorio.")

    name = (filename or "").strip()
    if not name or Path(name).name != name:
        raise ValueError("Nome de arquivo invalido.")

    candidate = base / name
    if not candidate.is_file():
        lowered = name.lower()
        for entry in base.iterdir():
            if entry.is_file() and entry.name.lower() == lowered:
                candidate = entry
                break

    if not candidate.is_file():
        raise ValueError("Arquivo nao encontrado na pasta configurada.")

    resolved = candidate.resolve()
    if resolved.parent != base.resolve():
        raise ValueError("Arquivo fora da pasta configurada.")
    return resolved
