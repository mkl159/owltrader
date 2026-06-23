"""Façade : assemble sources + indicateurs + signaux. Utilisée par le CLI et le bot."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

from .collectors.stooq_provider import StooqProvider
from .collectors.yfinance_provider import YFinanceProvider
from .core.router import DataRouter
from .indicators import compute_indicators
from .models import Direction, Quote, Signal
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

    def signal_for(self, raw: str) -> Optional[Signal]:
        """Signal seul (sans cotation séparée) — léger, pour le scan de marché."""
        asset = Asset.parse(raw)
        df = self.router.get_history(asset, period="1y", interval="1d")
        if df is None:
            return None
        return analyze(asset.raw, df)

    def scan(self, universe: list[str], top: int = 5,
             direction: Direction = Direction.BUY) -> list[Signal]:
        """Balaie un univers d'actifs en parallèle et renvoie les meilleures pistes.

        Renvoie en priorité les signaux dans le sens demandé (achat par défaut),
        triés par force décroissante. Si aucun, renvoie les mieux notés (à surveiller).
        """
        signals: list[Signal] = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(self.signal_for, raw): raw for raw in universe}
            for fut in as_completed(futures):
                try:
                    sig = fut.result()
                except Exception as e:  # noqa: BLE001
                    log.warning("scan %s : %s", futures[fut], e)
                    continue
                if sig is not None:
                    signals.append(sig)

        matched = [s for s in signals if s.direction == direction]
        if direction == Direction.BUY:
            matched.sort(key=lambda s: s.score, reverse=True)
            if matched:
                return matched[:top]
            # Aucune piste franche : on remonte les mieux notés à surveiller
            signals.sort(key=lambda s: s.score, reverse=True)
            return signals[:top]
        matched.sort(key=lambda s: s.score)
        return matched[:top]
