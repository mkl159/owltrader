"""Connecteur Alpaca — paper-trading via API REST (gratuit, vraie API, faux argent).

Compte gratuit sur https://alpaca.markets → génère des clés *paper* et renseigne
ALPACA_API_KEY_ID / ALPACA_API_SECRET dans .env. Aucune dépendance lourde (requests).
"""

from __future__ import annotations

import requests

from ..config import get_secret
from ..symbols import Asset
from .base import Broker

ALPACA_PAPER = "https://paper-api.alpaca.markets"


def to_alpaca_symbol(raw: str) -> str | None:
    """Convertit un actif interne vers le symbole Alpaca (None si non supporté)."""
    a = Asset.parse(raw)
    if a.klass == "CRYPTO":
        return f"{a.symbol}/USD"
    if a.klass == "STOCK":
        return a.symbol
    return None  # indices, FX, matières : non gérés par Alpaca simplement


class AlpacaBroker(Broker):
    name = "alpaca"

    def __init__(self, key: str | None = None, secret: str | None = None,
                 base: str = ALPACA_PAPER, session: requests.Session | None = None):
        self.key = key or get_secret("ALPACA_API_KEY_ID")
        self.secret = secret or get_secret("ALPACA_API_SECRET")
        if not (self.key and self.secret):
            raise RuntimeError(
                "Clés Alpaca manquantes. Crée un compte gratuit sur alpaca.markets, "
                "génère des clés *paper* et mets ALPACA_API_KEY_ID / ALPACA_API_SECRET dans .env."
            )
        self.base = base
        self.s = session or requests.Session()
        self.s.headers.update({
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret,
        })

    def _get(self, path: str):
        r = self.s.get(self.base + path, timeout=12)
        r.raise_for_status()
        return r.json()

    def get_account(self) -> dict:
        a = self._get("/v2/account")
        return {
            "cash": float(a["cash"]),
            "equity": float(a["equity"]),
            "currency": a.get("currency", "USD"),
            "status": a.get("status", "?"),
        }

    def get_positions(self) -> list[dict]:
        return [
            {
                "symbol": p["symbol"],
                "qty": float(p["qty"]),
                "avg_entry_price": float(p["avg_entry_price"]),
                "market_value": float(p["market_value"]),
                "unrealized_plpc": float(p.get("unrealized_plpc", 0.0)) * 100,
            }
            for p in self._get("/v2/positions")
        ]

    def submit_order(self, symbol: str, qty: float, side: str) -> dict:
        r = self.s.post(
            self.base + "/v2/orders",
            json={"symbol": symbol, "qty": qty, "side": side,
                  "type": "market", "time_in_force": "day"},
            timeout=12,
        )
        r.raise_for_status()
        return r.json()
