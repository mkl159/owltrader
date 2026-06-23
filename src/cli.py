"""CLI de test — vérifier les données et signaux SANS configurer Telegram.

Exemples :
    python -m src.cli prix AAPL
    python -m src.cli analyse STOCK:MSFT
    python -m src.cli analyse CRYPTO:BTC
"""

from __future__ import annotations

import argparse
import logging
import re
import sys

from .formatting import analysis_full, quote_line
from .service import MarketService


def _strip_md(text: str) -> str:
    return re.sub(r"[*_`]", "", text)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="owltrader", description="OwlTrader 🦉 — CLI de test")
    parser.add_argument("commande", choices=["prix", "analyse"], help="action à effectuer")
    parser.add_argument("actif", help="ex. AAPL, STOCK:MSFT, CRYPTO:BTC, FX:EURUSD")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs détaillés")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    svc = MarketService()
    if args.commande == "prix":
        q = svc.quote(args.actif)
        if q is None:
            print(f"❌ Aucune donnée pour {args.actif}")
            return 1
        print(_strip_md(quote_line(q)))
    else:
        a = svc.analyze(args.actif)
        print(_strip_md(analysis_full(a)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
