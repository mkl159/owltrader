"""Source Yahoo Finance via la lib yfinance (gratuite, sans clé, large couverture)."""

from __future__ import annotations

import logging
from datetime import timezone
from typing import Optional

import pandas as pd

from ..models import Quote, now_utc
from ..symbols import Asset
from .base import DataProvider

log = logging.getLogger(__name__)


def _to_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    idx = pd.to_datetime(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    df.index = idx
    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(
        columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
        }
    )
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep].dropna(how="all")
    return _to_utc_index(df)


class YFinanceProvider(DataProvider):
    name = "yfinance"

    def __init__(self):
        import yfinance as yf  # import paresseux pour démarrage rapide
        self._yf = yf

    def get_quote(self, asset: Asset) -> Optional[Quote]:
        sym = asset.yahoo_symbol
        try:
            t = self._yf.Ticker(sym)
            # Cours intraday le plus récent (≈ temps réel, léger différé selon le marché)
            intra = t.history(period="1d", interval="1m")
            if intra is None or intra.empty:
                intra = t.history(period="5d", interval="1d")
            if intra is None or intra.empty:
                return None
            intra = _to_utc_index(intra)
            last = intra.iloc[-1]
            price = float(last["Close"])
            ts = intra.index[-1].to_pydatetime().astimezone(timezone.utc)

            prev_close = None
            currency = None
            try:
                fi = t.fast_info
                prev_close = fi.get("previous_close") if hasattr(fi, "get") else fi.previous_close
                currency = fi.get("currency") if hasattr(fi, "get") else getattr(fi, "currency", None)
            except Exception:
                pass
            if prev_close is None:
                daily = t.history(period="5d", interval="1d")
                if daily is not None and len(daily) >= 2:
                    prev_close = float(daily["Close"].iloc[-2])

            return Quote(
                symbol=asset.raw, price=price, timestamp=ts, source=self.name,
                previous_close=float(prev_close) if prev_close else None, currency=currency,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("yfinance get_quote(%s) a échoué : %s", sym, e)
            return None

    def get_history(self, asset: Asset, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
        try:
            df = self._yf.Ticker(asset.yahoo_symbol).history(period=period, interval=interval)
            if df is None or df.empty:
                return None
            return _normalize(df)
        except Exception as e:  # noqa: BLE001
            log.warning("yfinance get_history(%s) a échoué : %s", asset.yahoo_symbol, e)
            return None
