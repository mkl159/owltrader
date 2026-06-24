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

    def analyze(self, raw: str, with_news: bool = True) -> Analysis:
        asset = Asset.parse(raw)
        quote = self.router.get_quote(asset)
        df = self.router.get_history(asset, period="1y", interval="1d")
        sentiment = self._news_sentiment(asset.raw) if with_news else None
        signal = analyze(asset.raw, df, sentiment=sentiment) if df is not None else None
        indicators = compute_indicators(df) if df is not None else {}
        return Analysis(asset=asset, quote=quote, signal=signal, indicators=indicators)

    @staticmethod
    def _news_sentiment(raw: str) -> Optional[float]:
        """Sentiment moyen des dernières actus (None si indispo). Import paresseux."""
        try:
            from .news import get_news
            from .news.collector import aggregate_sentiment
            items = get_news(raw, 5)
            return aggregate_sentiment(items) if items else None
        except Exception:  # noqa: BLE001
            return None

    def movers(self, universe: list[str]) -> list[tuple[str, Quote]]:
        """Renvoie (actif, cotation) trié par variation du jour décroissante."""
        out: list[tuple[str, Quote]] = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(self.quote, raw): raw for raw in universe}
            for fut in as_completed(futures):
                try:
                    q = fut.result()
                except Exception:  # noqa: BLE001
                    continue
                if q is not None and q.change_pct is not None:
                    out.append((futures[fut], q))
        out.sort(key=lambda t: t[1].change_pct, reverse=True)
        return out

    def backtest(self, raw: str, short: int = 20, long: int = 50):
        from .backtest import run_backtest
        asset = Asset.parse(raw)
        df = self.router.get_history(asset, period="2y", interval="1d")
        return run_backtest(asset.raw, df, short, long) if df is not None else None

    def history(self, raw: str, period: str = "1y"):
        return self.router.get_history(Asset.parse(raw), period=period, interval="1d")

    def fetch_histories(self, universe: list[str], period: str = "2y") -> dict:
        """Récupère en parallèle l'historique de tout un univers : {actif: df}."""
        out = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(self.history, raw, period): raw for raw in universe}
            for fut in as_completed(futures):
                try:
                    df = fut.result()
                except Exception:  # noqa: BLE001
                    continue
                if df is not None:
                    out[futures[fut]] = df
        return out

    def _paper_conf(self):
        from .config import CONFIG
        return CONFIG.get("paper", {})

    def simulate_portfolio(self, universe: list[str], capital: float = 1000.0,
                           period: str | None = None, **kw):
        """Simulation historique du mode autonome (preuve de rentabilité + courbe)."""
        from .paper import simulate
        pc = self._paper_conf()
        period = period or pc.get("backtest_period", "5y")
        hist = self.fetch_histories(universe, period=period)
        if pc.get("regime_filter", False) and "market_df" not in kw:
            kw["market_df"] = hist.get(pc.get("regime_symbol", "INDEX:^GSPC"))
        return simulate(hist, capital=capital, **kw)

    def optimize_strategy(self, universe: list[str], capital: float = 1000.0,
                          period: str | None = None, **fixed):
        """Auto-tuning : meilleurs paramètres sur l'historique. -> (params, SimResult)."""
        from .paper.optimizer import optimize
        pc = self._paper_conf()
        period = period or pc.get("backtest_period", "5y")
        hist = self.fetch_histories(universe, period=period)
        if pc.get("regime_filter", False) and "market_df" not in fixed:
            fixed["market_df"] = hist.get(pc.get("regime_symbol", "INDEX:^GSPC"))
        return optimize(hist, capital=capital, **fixed)

    def should_hold(self, raw: str, **params) -> bool:
        """Décision live de la stratégie : faut-il détenir cet actif maintenant ?"""
        from .strategy import should_hold
        df = self.history(raw, period="1y")
        return should_hold(df, **params) if df is not None else False

    def trend(self, raw: str, with_news: bool = True):
        """Tendance agrégée d'un actif (indicateurs + sentiment consolidés)."""
        from .trend import aggregate_trend
        asset = Asset.parse(raw)
        df = self.history(asset.raw, period="1y")
        sentiment = self._news_sentiment(asset.raw) if with_news else None
        return aggregate_trend(asset.raw, df, sentiment) if df is not None else None

    def market_trend(self, universe: list[str]):
        """Tendance générale du marché, agrégée sur tout l'univers."""
        from .trend import aggregate_market, aggregate_trend
        histories = self.fetch_histories(universe, period="1y")
        trends = [aggregate_trend(a, df) for a, df in histories.items()]
        return aggregate_market(trends)

    def season(self):
        """Contexte saisonnier + jours fériés (aucun appel réseau)."""
        from .seasonality import days_to_next_holiday, seasonal_context, upcoming_holidays
        return seasonal_context(), upcoming_holidays(days=150), days_to_next_holiday()

    def risk_climate(self):
        """Climat de risque macro/géopolitique : VIX + scan d'actus."""
        from .news import get_news
        from .risk_climate import assess
        q = self.quote("INDEX:^VIX")
        vix = q.price if q else None
        titles = [it.title for it in get_news("INDEX:^GSPC", 12)]
        return assess(vix, titles)

    def team_votes(self, raw: str) -> dict | None:
        """Vote de chaque stratégie de l'équipe pour un actif (transparence des décisions)."""
        from .strategies import votes_now
        asset = Asset.parse(raw)
        df = self.history(asset.raw, period="1y")
        if df is None:
            return None
        return votes_now(df)

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
