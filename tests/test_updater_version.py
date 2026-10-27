import pytest

from app.core.updater import _normalize, _parse_version, is_newer


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("v1.0.8", "1.0.8"),
        ("V1.2.3", "1.2.3"),
        ("v.0.1.6", "0.1.6"),
        ("1.0.9-beta", "1.0.9-beta"),
        ("  v2.0.0  ", "2.0.0"),
    ],
)
def test_normalize_strips_version_prefix(tag, expected):
    assert _normalize(tag) == expected


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("v1.0.8", (1, 0, 8)),
        ("v.0.1.6", (0, 1, 6)),
        ("V2.0.0", (2, 0, 0)),
        ("1.0.9-beta", (1, 0, 9)),
        ("1", (1, 0, 0)),
        ("", (0, 0, 0)),
    ],
)
def test_parse_version(tag, expected):
    assert _parse_version(tag) == expected


def test_is_newer_handles_dotted_v_tags():
    assert is_newer("v1.0.8", "0.1.0") is True
    assert is_newer("v.0.1.6", "0.1.5") is True
    assert is_newer("v.0.1.5", "0.1.6") is False
    assert is_newer("v1.0.8", "1.0.8") is False
