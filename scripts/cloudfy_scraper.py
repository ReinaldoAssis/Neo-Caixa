"""
Cloudfy Scraper CLI — Wrapper para o modulo de automacao do conciliador.

Uso:
    python scripts/cloudfy_scraper.py --login USUARIO --senha SENHA [--debug]

Requer o diretorio raiz do projeto no PYTHONPATH.
Execute da raiz do projeto:
    python scripts/cloudfy_scraper.py --login USUARIO --senha SENHA --listar --debug
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.conciliador.automacao import (
    CloudfyScraper,
    CaixaResumo,
    CaixaDetalhe,
    asdict,
)


def main():
    parser = argparse.ArgumentParser(
        description="Cloudfy Scraper — Conciliador de Fechamento"
    )
    parser.add_argument("--login", required=True, help="Usuario Cloudfy")
    parser.add_argument("--senha", required=True, help="Senha Cloudfy")
    parser.add_argument(
        "--caixa", type=int, default=None, help="Indice do caixa a extrair (0-based)"
    )
    parser.add_argument(
        "--listar", action="store_true", help="Apenas listar caixas pendentes"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Modo visivel (nao-headless)"
    )
    parser.add_argument("--output", type=str, default=None, help="Arquivo JSON de saida")

    args = parser.parse_args()

    if not args.listar and args.caixa is None:
        print(
            "[ERRO] Use --listar para ver caixas OU --caixa N para extrair um.",
            file=sys.stderr,
        )
        sys.exit(1)

    async def run():
        async with CloudfyScraper(args.login, args.senha, debug=args.debug) as scraper:
            result = await scraper.executar(
                caixa_idx=args.caixa,
                apenas_listar=args.listar,
            )
            return result

    result = asyncio.run(run())
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[OK] Resultado salvo em {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
