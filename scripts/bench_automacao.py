"""Mede os tempos da automação Cloudfy.

Requer credenciais configuradas no app. Uso:

    python scripts/bench_automacao.py            # lista + importa até 2 caixas
    python scripts/bench_automacao.py -n 4       # importa até 4 caixas
    python scripts/bench_automacao.py --no-warm  # desliga a sessão persistente

Imprime os tempos por etapa e o total, para comparar com as metas:
listar ≤2s · importar ≤4s/caixa · lote T1+T2 ≤7s.
"""

from __future__ import annotations

import argparse
import time

from app.core import app_context
from app.modules.conciliador.automacao import (
    chave_de_caixa,
    importar_caixas_cloudfy,
    listar_caixas_cloudfy,
    tempos_recentes,
)
from app.modules.conciliador.config_posto import load_settings


def _config() -> tuple[str, str, bool, bool]:
    settings = load_settings(app_context.database)
    return (
        settings.get("cloudfy_login", ""),
        settings.get("cloudfy_senha", ""),
        bool(settings.get("cloudfy_debug", False)),
        bool(settings.get("otimizar_automacao", True)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark da automacao Cloudfy")
    parser.add_argument("-n", "--caixas", type=int, default=2, help="quantos caixas importar")
    parser.add_argument("--no-warm", action="store_true", help="sessao efemera por chamada")
    args = parser.parse_args()

    login, senha, debug, otimizar = _config()
    if not login or not senha:
        raise SystemExit("Credenciais Cloudfy nao configuradas no app.")

    otimizar = otimizar and not args.no_warm

    print(f"[bench] otimizar={otimizar} debug={debug}")
    inicio = time.perf_counter()
    listagem = listar_caixas_cloudfy(login, senha, debug=debug, otimizar=otimizar)
    total_listar = time.perf_counter() - inicio
    caixas = listagem.get("caixas", [])
    print(f"[bench] listar: {total_listar:.2f}s ({len(caixas)} caixas fechados)")
    for etapa, segundos in tempos_recentes().items():
        print(f"    {etapa}: {segundos:.2f}s")

    if not caixas:
        return

    selecionados = caixas[: max(1, args.caixas)]
    chaves = [chave_de_caixa(c) for c in selecionados]
    inicio = time.perf_counter()
    lote = importar_caixas_cloudfy(login, senha, chaves, debug=debug, otimizar=otimizar)
    total_lote = time.perf_counter() - inicio
    print(f"[bench] importar {len(chaves)} caixa(s): {total_lote:.2f}s")
    for etapa, segundos in tempos_recentes().items():
        print(f"    {etapa}: {segundos:.2f}s")

    for resultado in lote.get("resultados", []):
        if resultado.get("ok"):
            print(
                f"    ok {resultado['caixa']['data']} T{resultado['caixa']['turno']}"
                f" -> {resultado['tempo_ms']}ms"
            )
        else:
            print(f"    erro {resultado.get('chave')}: {resultado.get('erro')}")


if __name__ == "__main__":
    main()
