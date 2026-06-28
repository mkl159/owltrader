"""Connecteur d'échanges crypto via CCXT (Binance, Kraken, Coinbase, OKX… 100+).

Une seule interface pour de nombreux organismes de trading. Configuration via .env :
EXCHANGE_NAME (ex. binance), EXCHANGE_API_KEY, EXCHANGE_API_SECRET.
Beaucoup d'échanges offrent un *testnet/sandbox* pour s'entraîner sans risque.
"""

from __future__ import annotations

from ..config import get_secret
from ..symbols import Asset
from .base import Broker


def to_ccxt_symbol(raw: str, quote: str = "USDT") -> str | None:
    a = Asset.parse(raw)
    if a.klass == "CRYPTO":
        return f"{a.symbol}/{quote}"
    return None  # ccxt = crypto uniquement ici


class CCXTBroker(Broker):
    name = "ccxt"

    def __init__(self, exchange: str | None = None, key: str | None = None,
                 secret: str | None = None, sandbox: bool = True):
        import ccxt  # import paresseux
        self.exchange_name = exchange or get_secret("EXCHANGE_NAME")
        key = key or get_secret("EXCHANGE_API_KEY")
        secret = secret or get_secret("EXCHANGE_API_SECRET")
        if not self.exchange_name:
            raise RuntimeError(
                "Aucun échange configuré. Mets EXCHANGE_NAME (ex. binance) + EXCHANGE_API_KEY "
                "+ EXCHANGE_API_SECRET dans .env. / No exchange configured."
            )
        if not hasattr(ccxt, self.exchange_name):
            raise RuntimeError(f"Échange inconnu de ccxt : {self.exchange_name}")
        klass = getattr(ccxt, self.exchange_name)
        self.ex = klass({"apiKey": key, "secret": secret, "enableRateLimit": True})
        if sandbox:
            try:
                self.ex.set_sandbox_mode(True)  # testnet quand disponible
            except Exception:  # noqa: BLE001
                pass

    def get_account(self) -> dict:
        bal = self.ex.fetch_balance()
        total = bal.get("total", {})
        cash = float(total.get("USDT", 0) or total.get("USD", 0) or 0)
        return {"cash": cash, "equity": cash, "currency": "USDT",
                "status": f"{self.exchange_name} (sandbox)"}

    def get_positions(self) -> list[dict]:
        bal = self.ex.fetch_balance()
        out = []
        for coin, amount in (bal.get("total") or {}).items():
            if amount and float(amount) > 0 and coin not in ("USDT", "USD"):
                out.append({"symbol": coin, "qty": float(amount), "avg_entry_price": 0.0,
                            "market_value": 0.0, "unrealized_plpc": 0.0})
        return out

    def submit_order(self, symbol: str, qty: float, side: str) -> dict:
        return self.ex.create_order(symbol, "market", side, qty)
