"""Façade : assemble sources + indicateurs + signaux. Utilisée par le CLI et le bot."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .collectors.stooq_provider import StooqProvider
from .collectors.yfinance_provider import YFinanceProvider
from .core.router import DataRouter
from .indicators import compute_indicators
from .models import Quote, Signal
from .signals import analyze
from .symbols import Asset

log = logging.getLogger(__name__)


def build_router() -> DataRouter:
    """Construit le routeur avec les sources gratuites disponibles (yfinance + Stooq en repli)."""
    providers = []
    try:
        providers.append(YFinanceProvider())
    except Exception as e:  # noqa: BLE001
        log.warning("yfinance indisponible : %s", e)
    providers.append(StooqProvider())
    return DataRouter(providers)


@dataclass
class Analysis:
    asset: Asset
    quote: Optional[Quote]
    signal: Optional[Signal]
    indicators: dict


class MarketService:
    def __init__(self, router: DataRouter | None = None):
        self.router = router or build_router()

    def quote(self, raw: str) -> Optional[Quote]:
        return self.router.get_quote(Asset.parse(raw))

    def analyze(self, raw: str) -> Analysis:
        asset = Asset.parse(raw)
        quote = self.router.get_quote(asset)
        df = self.router.get_history(asset, period="1y", interval="1d")
        signal = analyze(asset.raw, df) if df is not None else None
        indicators = compute_indicators(df) if df is not None else {}
        return Analysis(asset=asset, quote=quote, signal=signal, indicators=indicators)
