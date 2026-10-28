import ssl
from pathlib import Path
from urllib.error import URLError

import pytest

from app.core import updater
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


# ─── TLS / certificados ──────────────────────────────────────────

def test_ca_bundle_aponta_para_arquivo_existente():
    bundle = updater._ca_bundle()
    assert bundle
    assert Path(bundle).is_file()


def test_ssl_context_verifica_certificados():
    ctx = updater._ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert ctx.get_ca_certs()


def test_mensagem_erro_certificado_explica_acao():
    erro = ssl.SSLCertVerificationError(
        1, "certificate verify failed: unable to get local issuer certificate"
    )
    msg = updater.mensagem_erro(erro)
    assert "certificado" in msg.lower()
    assert "releases" in msg


def test_check_for_update_expoe_erro_de_certificado(monkeypatch):
    def _falha(url, timeout=15):
        raise URLError(
            ssl.SSLCertVerificationError(
                1, "certificate verify failed: unable to get local issuer certificate"
            )
        )

    monkeypatch.setattr(updater, "_get_json", _falha)
    resultado = updater.check_for_update("ReinaldoAssis/Neo-Caixa")
    assert resultado["update_available"] is False
    assert "certificado" in resultado["error"].lower()
