from datetime import date

import pytest

from app.modules.conciliador.relatorio_pasta import (
    find_report_file,
    list_reports,
    report_filename_for_date,
    resolve_report_file,
)


def _touch(directory, name):
    path = directory / name
    path.write_text("conteudo", encoding="utf-8")
    return path


def test_report_filename_for_date_is_padded():
    assert report_filename_for_date("2026-10-24") == "pag1024.csv"
    assert report_filename_for_date("2026-01-05") == "pag0105.csv"


def test_find_report_file_padded(tmp_path):
    _touch(tmp_path, "pag1024.csv")
    _touch(tmp_path, "pag1025.csv")
    found = find_report_file(tmp_path, "2026-10-24")
    assert found is not None
    assert found.name == "pag1024.csv"


def test_find_report_file_case_insensitive(tmp_path):
    _touch(tmp_path, "PAG1024.CSV")
    found = find_report_file(tmp_path, "2026-10-24")
    assert found is not None
    assert found.name.upper() == "PAG1024.CSV"


def test_find_report_file_accepts_unpadded(tmp_path):
    _touch(tmp_path, "pag924.csv")
    found = find_report_file(tmp_path, "2026-09-24")
    assert found is not None
    assert found.name == "pag924.csv"


def test_find_report_file_no_match(tmp_path):
    _touch(tmp_path, "pag1024.csv")
    assert find_report_file(tmp_path, "2026-10-25") is None


def test_find_report_file_missing_directory(tmp_path):
    assert find_report_file(tmp_path / "nao_existe", "2026-10-24") is None


def test_resolve_report_file_rejects_traversal(tmp_path):
    _touch(tmp_path, "pag1024.csv")
    with pytest.raises(ValueError):
        resolve_report_file(tmp_path, "../pag1024.csv")
    with pytest.raises(ValueError):
        resolve_report_file(tmp_path, "sub/pag1024.csv")


def test_resolve_report_file_case_fallback(tmp_path):
    _touch(tmp_path, "PAG1024.CSV")
    path = resolve_report_file(tmp_path, "pag1024.csv")
    assert path.name.upper() == "PAG1024.CSV"


def test_list_reports_filters_pattern(tmp_path):
    _touch(tmp_path, "pag1024.csv")
    _touch(tmp_path, "outro.csv")
    _touch(tmp_path, "pag1025.csv")
    reports = list_reports(tmp_path)
    assert [p.name for p in reports] == ["pag1024.csv", "pag1025.csv"]
