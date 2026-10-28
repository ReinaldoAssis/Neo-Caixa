"""
Sessão persistente de automação do Cloudfy.

Mantém UM navegador vivo entre rodadas, num thread próprio com loop asyncio
permanente (o ``asyncio.run`` antigo matava o browser a cada chamada).

- ``otimizar=True``: a sessão sobrevive entre requisições e é aquecida no boot.
- ``otimizar=False``: mesma implementação, mas o browser é fechado no fim de
  cada chamada (comportamento antigo, útil como fallback).

Troca headless → headed: o Chromium não troca de modo em runtime, então a
sessão fecha o browser e relança com ``storage_state`` (cookies + localStorage),
sem refazer login. Se o Cloudfy exigir login de novo, o relogin acontece na
janela visível.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
import time
from typing import Any, Callable, Coroutine

from app.core.logger import logger


class AutomacaoOcupada(RuntimeError):
    """Já existe uma rodada de automação em andamento."""


class AutomacaoIndisponivel(RuntimeError):
    """Navegador/loop não pôde ser iniciado."""


class AutomacaoSession:
    def __init__(self) -> None:
        self._thread_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        self._busy = threading.Lock()

        self._state_lock = threading.Lock()
        self._state = "off"
        self._detail = ""

        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._headed = False
        self._headed_lancar = False
        self._debug = False
        self._perfil: tuple[str, str] | None = None
        self._ultima_atividade = 0.0

    # ── Loop dedicado ─────────────────────────────────────────────

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive() and self._loop is not None:
                return self._loop
            self._loop_ready.clear()
            self._thread = threading.Thread(
                target=self._loop_main, name="automacao-loop", daemon=True
            )
            self._thread.start()
        if not self._loop_ready.wait(10):
            raise AutomacaoIndisponivel("Loop da automacao nao iniciou.")
        assert self._loop is not None
        return self._loop

    def _loop_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                pendentes = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for tarefa in pendentes:
                    tarefa.cancel()
                if pendentes:
                    loop.run_until_complete(
                        asyncio.gather(*pendentes, return_exceptions=True)
                    )
            except Exception:
                pass
            loop.close()
            self._loop = None

    def _submit(
        self,
        fabrica: Callable[[], Coroutine],
        timeout: float = 240,
        wait: float = 10,
        blocking: bool = False,
    ):
        espera = timeout if blocking else wait
        adquiriu = self._busy.acquire(blocking=True, timeout=espera)
        if not adquiriu:
            raise AutomacaoOcupada("Automacao ja esta rodando. Aguarde a rodada atual.")
        try:
            loop = self._ensure_loop()

            async def _rodar():
                return await asyncio.wait_for(fabrica(), timeout=timeout)

            futuro = asyncio.run_coroutine_threadsafe(_rodar(), loop)
            return futuro.result(timeout + 10)
        finally:
            self._busy.release()

    # ── Estado ───────────────────────────────────────────────────

    def _set_state(self, state: str, detail: str = "") -> None:
        with self._state_lock:
            self._state = state
            self._detail = detail

    def status(self) -> dict[str, Any]:
        from app.modules.conciliador.automacao import tempos_recentes

        with self._state_lock:
            state = self._state
            detail = self._detail
        return {
            "state": state,
            "detail": detail,
            "headed": bool(self._headed),
            "browser_aberto": self._browser_ok(),
            "ocupado": self._busy.locked(),
            "ultima_atividade": self._ultima_atividade,
            "timings_ms": {k: int(round(v * 1000)) for k, v in tempos_recentes().items()},
        }

    def _marcar_atividade(self) -> None:
        self._ultima_atividade = time.time()

    # ── Browser ──────────────────────────────────────────────────

    def _browser_ok(self) -> bool:
        try:
            if self._browser is None or not self._browser.is_connected():
                return False
            if self._page is None or self._page.is_closed():
                return False
            return True
        except Exception:
            return False

    async def _ensure_playwright(self):
        if self._pw is None:
            from playwright.async_api import async_playwright

            self._pw = await async_playwright().start()
        return self._pw

    async def _bloquear_assets(self, context) -> None:
        async def handler(route):
            try:
                if route.request.resource_type in ("image", "media", "font"):
                    await route.abort()
                else:
                    await route.continue_()
            except Exception:
                pass

        try:
            await context.route("**/*", handler)
        except Exception:
            logger.warning("[automacao] nao foi possivel registrar bloqueio de assets")

    async def _launch(self, headless: bool, storage_state: dict | None = None) -> None:
        pw = await self._ensure_playwright()
        browser = None
        erros: list[str] = []
        for kwargs in ({"channel": "chrome", "headless": headless}, {"headless": headless}):
            try:
                browser = await pw.chromium.launch(**kwargs)
                break
            except Exception as exc:  # noqa: BLE001 - tenta o canal bundled
                erros.append(str(exc))

        if browser is None:
            raise AutomacaoIndisponivel(
                "Navegador nao encontrado. Instale o Google Chrome ou execute "
                "'playwright install chromium'. Detalhe: " + (erros[-1] if erros else "")
            )

        context = await browser.new_context(storage_state=storage_state)
        if headless:
            await self._bloquear_assets(context)
        page = await context.new_page()
        page.set_default_timeout(15000)

        self._browser = browser
        self._context = context
        self._page = page
        self._headed = not headless
        logger.info("[automacao] navegador %s iniciado", "visivel" if self._headed else "headless")

    async def _fechar_browser(self, manter_playwright: bool = True) -> None:
        browser = self._browser
        self._browser = None
        self._context = None
        self._page = None
        self._headed = False
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if not manter_playwright and self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None

    async def _switch_mode(self, headed: bool) -> None:
        storage_state = None
        if self._context is not None:
            try:
                storage_state = await self._context.storage_state()
            except Exception:
                storage_state = None
        logger.info(
            "[automacao] trocando para %s%s",
            "janela visivel" if headed else "headless",
            " (com storage_state)" if storage_state else "",
        )
        await self._fechar_browser(manter_playwright=True)
        await self._launch(headless=not headed, storage_state=storage_state)

    async def _ensure_ready(self, login: str, senha: str, debug: bool, headed: bool = False) -> None:
        if self._perfil is not None and self._perfil != (login, senha):
            await self._fechar_browser()
        self._perfil = (login, senha)
        self._debug = bool(debug)

        if not self._browser_ok():
            if self._headed_lancar and not self._debug and not headed:
                # usuário fechou a janela do lançamento (ou o browser caiu):
                # a próxima rodada volta para headless.
                self._headed_lancar = False
            await self._fechar_browser()
            await self._launch(headless=not (self._debug or headed or self._headed_lancar))
            return

        alvo_headed = bool(self._debug or headed or self._headed_lancar)
        if alvo_headed != self._headed:
            await self._switch_mode(alvo_headed)

    async def _goto_conciliador(self) -> None:
        from app.modules.conciliador import automacao as ops

        if self._page is None or self._page.is_closed():
            if self._context is None:
                raise AutomacaoIndisponivel("Sessao sem contexto de navegador.")
            self._page = await self._context.new_page()
            self._page.set_default_timeout(15000)
        await ops.navegar_conciliador(self._page, self._login_atual, self._senha_atual)

    @property
    def _login_atual(self) -> str:
        return self._perfil[0] if self._perfil else ""

    @property
    def _senha_atual(self) -> str:
        return self._perfil[1] if self._perfil else ""

    async def _recuperar_sessao(self) -> None:
        logger.info("[automacao] recuperando sessao (relogin)")
        if not self._browser_ok():
            await self._fechar_browser()
            self._headed_lancar = False
            await self._launch(headless=not self._debug)
        await self._goto_conciliador()

    def _sessao_perdida(self, exc: Exception) -> bool:
        if not self._browser_ok():
            return True
        mensagem = str(exc).lower()
        return any(
            chave in mensagem
            for chave in (
                "has been closed",
                "target closed",
                "browser has been closed",
                "execution context was destroyed",
                "navigation failed because page was closed",
            )
        ) or "login" in str(getattr(self._page, "url", "")).lower()

    async def _com_retry(self, funcao, *args):
        try:
            return await funcao(*args)
        except Exception as exc:
            if not self._sessao_perdida(exc):
                raise
            await self._recuperar_sessao()
            return await funcao(*args)

    # ── Execução ─────────────────────────────────────────────────

    async def _executar(self, persistente: bool, operacao):
        try:
            resultado = await operacao()
        except Exception as exc:
            if not persistente:
                await self._fechar_browser()
                self._set_state("off", "Sessao encerrada (otimizacao desligada)")
            else:
                self._set_state("error", str(exc))
            raise
        if not persistente:
            await self._fechar_browser()
            self._set_state("off", "Sessao encerrada (otimizacao desligada)")
        else:
            self._set_state("headed" if self._headed else "ready", "")
        self._marcar_atividade()
        return resultado

    # ── Operações ────────────────────────────────────────────────

    async def _op_warm(self, login: str, senha: str, debug: bool) -> dict[str, Any]:
        from app.modules.conciliador import automacao as ops

        self._set_state("warming", "Conectando ao Cloudfy...")
        try:
            await self._ensure_ready(login, senha, debug)
            await self._goto_conciliador()
        except Exception as exc:
            logger.warning("[automacao] aquecimento falhou: %s", exc)
            self._set_state("error", str(exc))
            return {"ok": False, "erro": str(exc)}

        estado = "headed" if self._headed else "ready"
        self._set_state(estado, "Sessao pronta")
        self._marcar_atividade()
        return {"ok": True, "status": self.status(), "timings_ms": ops.tempos_recentes()}

    def warm(self, login: str, senha: str, debug: bool = False) -> dict[str, Any]:
        if not login or not senha:
            return {"ok": False, "erro": "Credenciais Cloudfy nao configuradas."}
        try:
            return self._submit(lambda: self._op_warm(login, senha, debug), timeout=150, wait=0)
        except AutomacaoOcupada:
            return {"ok": False, "erro": "Automacao ocupada; aquecimento ignorado."}

    def warm_em_thread(self, login: str, senha: str, debug: bool = False) -> None:
        threading.Thread(
            target=self.warm,
            args=(login, senha, debug),
            name="automacao-warm",
            daemon=True,
        ).start()

    def reconectar(self, login: str, senha: str, debug: bool = False) -> dict[str, Any]:
        async def op():
            await self._fechar_browser()
            self._perfil = None
            self._headed_lancar = False
            return await self._op_warm(login, senha, debug)

        if not login or not senha:
            return {"ok": False, "erro": "Credenciais Cloudfy nao configuradas."}
        return self._submit(op, timeout=150)

    def listar(self, login: str, senha: str, debug: bool = False, otimizar: bool = True) -> dict:
        from app.modules.conciliador import automacao as ops
        from dataclasses import asdict

        async def op():
            await self._ensure_ready(login, senha, debug)
            await self._goto_conciliador()
            caixas = await ops.ler_caixas(self._page)
            return {"total": len(caixas), "caixas": [asdict(c) for c in caixas]}

        return self._submit(lambda: self._executar(otimizar, op), timeout=180)

    def importar(
        self,
        login: str,
        senha: str,
        chaves: list[dict],
        data_iso: str | None = None,
        debug: bool = False,
        otimizar: bool = True,
    ) -> dict:
        from dataclasses import asdict

        from app.modules.conciliador import automacao as ops

        async def op():
            await self._ensure_ready(login, senha, debug)
            await self._goto_conciliador()

            resultados: list[dict] = []
            for indice, chave in enumerate(chaves):
                caixa = None
                inicio = time.perf_counter()
                try:
                    # O detalhe/conciliação abre inline; garante a lista antes
                    # de procurar o próximo caixa (evita reusar o detalhe do T1).
                    try:
                        await ops.garantir_lista(self._page)
                    except Exception:
                        await self._goto_conciliador()

                    caixas = await ops.ler_caixas(self._page)
                    resolvidos, erros = ops.resolver_caixas(
                        caixas, [chave], data_iso
                    )
                    if erros or not resolvidos:
                        resultados.append(erros[0] if erros else {
                            "chave": chave,
                            "ok": False,
                            "erro": "Caixa nao encontrado na lista atual.",
                            "tempo_ms": 0,
                        })
                        continue

                    caixa = resolvidos[0][0]
                    detalhe = await self._com_retry(
                        ops.abrir_detalhes, self._page, self._context, caixa
                    )
                    resultados.append({
                        "chave": chave,
                        "ok": True,
                        "caixa": asdict(caixa),
                        "dinheiro": detalhe.dinheiro,
                        "pagamentos": [asdict(p) for p in detalhe.pagamentos],
                        "tempo_ms": int(round((time.perf_counter() - inicio) * 1000)),
                    })
                except Exception as exc:
                    logger.warning(
                        "[automacao] falha ao importar caixa %s/%s: %s",
                        getattr(caixa, "data", "?"),
                        getattr(caixa, "turno", "?"),
                        exc,
                    )
                    resultados.append({
                        "chave": chave,
                        "ok": False,
                        "erro": str(exc),
                        "tempo_ms": int(round((time.perf_counter() - inicio) * 1000)),
                    })
                    if self._sessao_perdida(exc):
                        for resto_chave in chaves[indice + 1:]:
                            resultados.append({
                                "chave": resto_chave,
                                "ok": False,
                                "erro": (
                                    "Sessao do Cloudfy caiu durante o lote; "
                                    "importe novamente."
                                ),
                                "tempo_ms": 0,
                            })
                        break
                    try:
                        await ops.garantir_lista(self._page)
                    except Exception:
                        try:
                            await self._goto_conciliador()
                        except Exception:
                            pass

            return {"resultados": resultados, "total": len(resultados)}

        return self._submit(lambda: self._executar(otimizar, op), timeout=600)

    def importar_por_indice(
        self,
        login: str,
        senha: str,
        caixa_idx: int,
        debug: bool = False,
        otimizar: bool = True,
    ) -> dict:
        from dataclasses import asdict

        from app.modules.conciliador import automacao as ops

        async def op():
            await self._ensure_ready(login, senha, debug)
            await self._goto_conciliador()
            caixas = await ops.ler_caixas(self._page)
            if caixa_idx < 0 or caixa_idx >= len(caixas):
                return {"erro": f"Indice invalido. {len(caixas)} disponiveis."}
            detalhe = await self._com_retry(
                ops.abrir_detalhes, self._page, self._context, caixas[caixa_idx]
            )
            return asdict(detalhe)

        return self._submit(lambda: self._executar(otimizar, op), timeout=300)

    def lancar(
        self,
        login: str,
        senha: str,
        caixa_idx: int | None = None,
        dinheiro_valor: str = "0",
        mapeamento: dict | None = None,
        categorias: dict | None = None,
        caixa: dict | None = None,
        data_iso: str | None = None,
        debug: bool = False,
        otimizar: bool = True,
    ) -> dict:
        from app.modules.conciliador import automacao as ops

        async def op():
            self._headed_lancar = True
            await self._ensure_ready(login, senha, debug, headed=True)
            await self._goto_conciliador()
            caixas = await ops.ler_caixas(self._page)

            alvo = None
            if isinstance(caixa, dict) and caixa:
                resolvidos, erros = ops.resolver_caixas(caixas, [caixa], data_iso)
                if erros:
                    return {"erro": erros[0]["erro"]}
                alvo = resolvidos[0][0]
            elif caixa_idx is not None:
                indice = int(caixa_idx)
                if indice < 0 or indice >= len(caixas):
                    return {"erro": f"Indice invalido. {len(caixas)} disponiveis."}
                alvo = caixas[indice]
                erro_data = ops.validar_data_caixa(alvo, data_iso)
                if erro_data:
                    return {"erro": erro_data}

            if alvo is None:
                return {"erro": "Informe o caixa para lancar."}

            resultado = await ops.executar_lancamento(
                self._page,
                self._context,
                alvo,
                str(dinheiro_valor),
                mapeamento or {},
                categorias or {},
            )
            self._headed_lancar = True
            self._set_state("headed", "Janela do lancamento aberta")
            return resultado

        # Lançamento sempre deixa a janela aberta, mesmo com otimização desligada.
        return self._submit(lambda: self._executar(True, op), timeout=300)

    def lancar_financeiro(
        self,
        login: str,
        senha: str,
        itens: list[dict],
        config: dict,
        debug: bool = False,
        otimizar: bool = True,
    ) -> dict:
        from app.modules.conciliador import automacao as ops

        async def op():
            if self._browser_ok() and self._headed and not self._debug:
                raise AutomacaoIndisponivel(
                    "Feche o navegador da automacao (botao 'Fechar navegador') "
                    "antes de lancar no financeiro."
                )
            await self._ensure_ready(login, senha, debug)
            if self._headed and not self._debug:
                raise AutomacaoIndisponivel(
                    "Feche o navegador da automacao (botao 'Fechar navegador') "
                    "antes de lancar no financeiro."
                )
            try:
                await ops.abrir_financeiro(self._page, login, senha)
            except Exception as exc:  # noqa: BLE001 - devolve erro claro
                logger.warning("[automacao] financeiro indisponivel: %s", exc)
                return {"erro": str(exc)}
            return await ops.executar_lancamentos_financeiros(
                self._page, itens, config
            )

        return self._submit(lambda: self._executar(otimizar, op), timeout=900)

    def conferir_extrato_adm(
        self,
        login: str,
        senha: str,
        data_iso: str,
        debug: bool = False,
        otimizar: bool = True,
    ) -> dict:
        from app.modules.conciliador import automacao as ops

        async def op():
            if self._browser_ok() and self._headed and not self._debug:
                raise AutomacaoIndisponivel(
                    "Feche o navegador da automacao (botao 'Fechar navegador') "
                    "antes de conferir o extrato."
                )
            await self._ensure_ready(login, senha, debug)
            if self._headed and not self._debug:
                raise AutomacaoIndisponivel(
                    "Feche o navegador da automacao (botao 'Fechar navegador') "
                    "antes de conferir o extrato."
                )
            try:
                await ops.abrir_financeiro(self._page, login, senha)
            except Exception as exc:  # noqa: BLE001 - devolve erro claro
                logger.warning("[automacao] financeiro indisponivel: %s", exc)
                return {"erro": str(exc)}
            return await ops.conferir_extrato_adm(self._page, data_iso)

        return self._submit(lambda: self._executar(otimizar, op), timeout=300)

    def descontos(self, login: str, senha: str, debug: bool = False, otimizar: bool = True) -> dict:
        from app.modules.conciliador import automacao as ops

        async def op():
            await self._ensure_ready(login, senha, debug)
            descontos = await self._com_retry(
                ops.baixar_relatorio_descontos, self._page, login, senha
            )
            return {"descontos": descontos, "total": len(descontos)}

        return self._submit(lambda: self._executar(otimizar, op), timeout=300)

    def fechar_navegador(self) -> dict[str, Any]:
        async def op():
            await self._fechar_browser()
            self._headed_lancar = False
            self._set_state("off", "Navegador fechado")
            return self.status()

        return self._submit(op, timeout=30)

    def fechar(self, timeout: float = 8) -> None:
        """Fecha browser + loop. Chamado no shutdown do app."""
        if self._thread is None or not self._thread.is_alive():
            return
        try:
            async def op():
                await self._fechar_browser(manter_playwright=False)
                self._set_state("off", "Sessao encerrada")

            self._submit(op, timeout=timeout, blocking=True)
        except Exception as exc:  # noqa: BLE001 - shutdown nunca deve travar o app
            logger.debug("[automacao] shutdown: %s", exc)
        loop = self._loop
        if loop is not None:
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def ping(self) -> bool:
        async def op():
            return True

        return bool(self._submit(op, timeout=15))


SESSAO = AutomacaoSession()


def warm_from_settings(database) -> dict[str, Any]:
    """Lê as configurações e aquece a sessão (não bloqueia o startup)."""
    from app.modules.conciliador.config_posto import load_settings

    try:
        settings = load_settings(database)
    except Exception as exc:
        logger.warning("[automacao] nao foi possivel ler settings: %s", exc)
        return {"ok": False, "erro": str(exc)}

    if not settings.get("otimizar_automacao", True):
        return {"ok": False, "motivo": "otimizacao desligada"}

    login = settings.get("cloudfy_login", "")
    senha = settings.get("cloudfy_senha", "")
    if not login or not senha:
        return {"ok": False, "motivo": "sem credenciais"}

    SESSAO.warm_em_thread(login, senha, bool(settings.get("cloudfy_debug", False)))
    return {"ok": True, "motivo": "aquecimento agendado"}


def fechar_sessao() -> None:
    SESSAO.fechar(8)


atexit.register(fechar_sessao)
