"""Testes da máquina de estados da sessão persistente (sem navegador)."""

from __future__ import annotations

import pytest

from app.modules.conciliador.automacao_sessao import (
    AutomacaoOcupada,
    AutomacaoSession,
)


def test_status_inicial_off():
    sessao = AutomacaoSession()
    status = sessao.status()
    assert status["state"] == "off"
    assert status["browser_aberto"] is False
    assert status["ocupado"] is False


def test_loop_dedicado_sobe_e_desce():
    sessao = AutomacaoSession()
    assert sessao.ping() is True
    assert sessao.status()["state"] == "off"
    sessao.fechar(timeout=5)
    assert sessao.ping() is True  # loop é recriado sob demanda


def test_warm_sem_credenciais_nao_sobe_browser():
    sessao = AutomacaoSession()
    resultado = sessao.warm("", "")
    assert resultado["ok"] is False
    assert "Credenciais" in resultado["erro"]
    sessao.fechar(timeout=5)


def test_mutex_recusa_segunda_rodada():
    sessao = AutomacaoSession()

    async def _nada():
        return None

    assert sessao._busy.acquire(blocking=False) is True
    try:
        with pytest.raises(AutomacaoOcupada):
            sessao._submit(_nada, wait=0)
    finally:
        sessao._busy.release()
    sessao.fechar(timeout=5)


class _DBVazio:
    def search(self, table, query):
        return []


class _DBDesligado:
    def search(self, table, query):
        return [{"key": "modulo_settings", "otimizar_automacao": False}]


def test_warm_from_settings_sem_credenciais():
    from app.modules.conciliador.automacao_sessao import warm_from_settings

    resultado = warm_from_settings(_DBVazio())
    assert resultado["ok"] is False
    assert resultado["motivo"] == "sem credenciais"


def test_warm_from_settings_desligado():
    from app.modules.conciliador.automacao_sessao import warm_from_settings

    resultado = warm_from_settings(_DBDesligado())
    assert resultado["ok"] is False
    assert resultado["motivo"] == "otimizacao desligada"
