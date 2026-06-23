"""Source Stooq (gratuite, sans clé) — utilisée en repli. CSV simple."""

from __future__ import annotations

import io
import logging
from datetime import timezone
from typing import Optional

import pandas as pd
import requests

from ..models import Quote
from ..symbols import Asset
from .base import DataProvider

log = logging.getLogger(__name__)


class StooqProvider(DataProvider):
    name = "stooq"

    def supports(self, asset: Asset) -> bool:
        return asset.stooq_symbol is not None

    def _download(self, symbol: str, interval: str = "d") -> Optional[pd.DataFrame]:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i={interval}"
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (OwlTrader)"})
            r.raise_for_status()
            # Stooq renvoie une page HTML quand la limite quotidienne est atteinte → repli silencieux
            if not r.text.lstrip().lower().startswith("date"):
                log.info("stooq indisponible pour %s (réponse non-CSV, limite ?)", symbol)
                return None
            df = pd.read_csv(io.StringIO(r.text))
            if df.empty or "Close" not in df.columns:
                return None
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
            df.index = df.index.tz_localize("UTC")
            return df.rename(columns={
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "volume",
            })
        except Exception as e:  # noqa: BLE001
            log.warning("stooq téléchargement(%s) a échoué : %s", symbol, e)
            return None

    def get_quote(self, asset: Asset) -> Optional[Quote]:
        sym = asset.stooq_symbol
        if not sym:
            return None
        df = self._download(sym)
        if df is None or df.empty:
            return None
        last = df.iloc[-1]
        prev = df["close"].iloc[-2] if len(df) >= 2 else None
        ts = df.index[-1].to_pydatetime().astimezone(timezone.utc)
        return Quote(
            symbol=asset.raw, price=float(last["close"]), timestamp=ts,
            source=self.name, previous_close=float(prev) if prev is not None else None,
        )

    def get_history(self, asset: Asset, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
        sym = asset.stooq_symbol
        if not sym:
            return None
        df = self._download(sym)
        if df is None:
            return None
        return df[[c for c in ("open", "high", "low", "close", "volume") if c in df.columns]]
