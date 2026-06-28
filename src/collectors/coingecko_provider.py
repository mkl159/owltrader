"""Source CoinGecko (gratuite, sans clé) — crypto, cours très frais (24/7)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from ..models import Quote
from ..symbols import Asset
from .base import DataProvider

log = logging.getLogger(__name__)

# Symbole interne -> identifiant CoinGecko
COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "MATIC": "matic-network", "LTC": "litecoin", "LINK": "chainlink",
}
_BASE = "https://api.coingecko.com/api/v3"


def _days_from_period(period: str) -> str:
    table = {"1mo": "30", "3mo": "90", "6mo": "180", "1y": "365",
             "2y": "730", "5y": "1825", "10y": "max", "max": "max"}
    return table.get(period, "365")


class CoinGeckoProvider(DataProvider):
    name = "coingecko"

    def supports(self, asset: Asset) -> bool:
        return asset.klass == "CRYPTO" and asset.symbol in COINGECKO_IDS

    def get_quote(self, asset: Asset) -> Optional[Quote]:
        cid = COINGECKO_IDS.get(asset.symbol)
        if not cid:
            return None
        try:
            r = requests.get(
                f"{_BASE}/simple/price",
                params={"ids": cid, "vs_currencies": "usd",
                        "include_last_updated_at": "true", "include_24hr_change": "true"},
                timeout=10, headers={"User-Agent": "OwlTrader"},
            )
            r.raise_for_status()
            d = r.json().get(cid)
            if not d or "usd" not in d:
                return None
            price = float(d["usd"])
            ts = datetime.fromtimestamp(d.get("last_updated_at", 0) or 0, tz=timezone.utc)
            chg = d.get("usd_24h_change")
            prev = price / (1 + chg / 100) if chg else None
            return Quote(symbol=asset.raw, price=price, timestamp=ts, source=self.name,
                         previous_close=float(prev) if prev else None, currency="USD")
        except Exception as e:  # noqa: BLE001
            log.info("coingecko get_quote(%s) : %s", asset.symbol, e)
            return None

    def get_history(self, asset: Asset, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
        cid = COINGECKO_IDS.get(asset.symbol)
        if not cid:
            return None
        try:
            r = requests.get(
                f"{_BASE}/coins/{cid}/market_chart",
                params={"vs_currency": "usd", "days": _days_from_period(period), "interval": "daily"},
                timeout=12, headers={"User-Agent": "OwlTrader"},
            )
            r.raise_for_status()
            prices = r.json().get("prices", [])
            if not prices:
                return None
            idx = [datetime.fromtimestamp(p[0] / 1000, tz=timezone.utc) for p in prices]
            close = [float(p[1]) for p in prices]
            df = pd.DataFrame({"open": close, "high": close, "low": close,
                               "close": close, "volume": 0.0}, index=pd.DatetimeIndex(idx))
            return df
        except Exception as e:  # noqa: BLE001
            log.info("coingecko get_history(%s) : %s", asset.symbol, e)
            return None
