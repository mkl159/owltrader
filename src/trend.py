"""Tendance AGRÉGÉE : consolide plusieurs sources/indicateurs en un seul verdict.

Par actif : combine tendance (SMA), momentum (MACD, rendements 1/3 mois), régime (RSI)
et sentiment des actus en un score -100..+100 et un libellé.
Au niveau marché : agrège l'ensemble de l'univers (breadth) en une tendance générale.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators.technical import ema, macd, rsi, sma


@dataclass
class Trend:
    symbol: str
    score: float          # -100 (très baissier) … +100 (très haussier)
    label: str
    components: dict      # détail par source

    @property
    def emoji(self) -> str:
        if self.score >= 50:
            return "🟢🟢"
        if self.score >= 15:
            return "🟢"
        if self.score <= -50:
            return "🔴🔴"
        if self.score <= -15:
            return "🔴"
        return "⚪"


def _label(score: float) -> str:
    if score >= 50:
        return "Fortement haussière"
    if score >= 15:
        return "Haussière"
    if score <= -50:
        return "Fortement baissière"
    if score <= -15:
        return "Baissière"
    return "Neutre / indécise"


def aggregate_trend(symbol: str, df: pd.DataFrame, sentiment: float | None = None) -> Trend | None:
    """Agrège plusieurs signaux en une tendance consolidée pour un actif."""
    if df is None or "close" not in df.columns or len(df) < 60:
        return None
    close = df["close"].astype(float)
    price = float(close.iloc[-1])
    comp: dict[str, float] = {}

    # 1) Tendance de fond (position vs SMA50/200)
    s50, s200 = sma(close, 50), sma(close, 200)
    if pd.notna(s50.iloc[-1]):
        comp["SMA50"] = 1.0 if price > s50.iloc[-1] else -1.0
    if pd.notna(s200.iloc[-1]):
        comp["SMA200"] = 1.5 if price > s200.iloc[-1] else -1.5
    if pd.notna(s50.iloc[-1]) and pd.notna(s200.iloc[-1]):
        comp["alignement"] = 1.5 if s50.iloc[-1] > s200.iloc[-1] else -1.5

    # 2) Momentum MACD
    macd_line, signal_line, _ = macd(close)
    if pd.notna(macd_line.iloc[-1]) and pd.notna(signal_line.iloc[-1]):
        comp["MACD"] = 1.0 if macd_line.iloc[-1] > signal_line.iloc[-1] else -1.0

    # 3) Rendements 1 mois / 3 mois
    if len(close) > 21:
        comp["perf_1m"] = 1.0 if close.iloc[-1] > close.iloc[-21] else -1.0
    if len(close) > 63:
        comp["perf_3m"] = 1.0 if close.iloc[-1] > close.iloc[-63] else -1.0

    # 4) Régime RSI
    r = rsi(close).iloc[-1]
    if pd.notna(r):
        if r >= 55:
            comp["RSI"] = 1.0
        elif r <= 45:
            comp["RSI"] = -1.0
        else:
            comp["RSI"] = 0.0

    # 5) EMA20 pente (accélération)
    e20 = ema(close, 20)
    if len(e20) > 5 and pd.notna(e20.iloc[-1]) and pd.notna(e20.iloc[-6]):
        comp["pente"] = 1.0 if e20.iloc[-1] > e20.iloc[-6] else -1.0

    # 6) Sentiment des actus (source externe agrégée)
    if sentiment is not None and abs(sentiment) > 0.05:
        comp["actus"] = max(-1.5, min(1.5, sentiment * 1.5))

    # Agrégation normalisée en -100..100
    total = sum(comp.values())
    max_total = sum(abs(v) if v != 0 else 1.0 for v in comp.values()) or 1.0
    # borne théorique : poids max possibles
    weight_cap = 1 + 1.5 + 1.5 + 1 + 1 + 1 + 1 + 1 + 1.5  # ~10.5
    score = max(-100.0, min(100.0, total / weight_cap * 100))

    return Trend(symbol=symbol, score=round(score, 1), label=_label(score), components=comp)


@dataclass
class MarketTrend:
    n: int
    bullish: int
    bearish: int
    neutral: int
    avg_score: float
    top: list           # (symbol, score) plus haussiers
    bottom: list        # plus baissiers

    @property
    def breadth(self) -> float:
        """% d'actifs haussiers (largeur de marché)."""
        return self.bullish / self.n * 100 if self.n else 0.0

    @property
    def label(self) -> str:
        return _label(self.avg_score)

    @property
    def emoji(self) -> str:
        if self.avg_score >= 15:
            return "🟢"
        if self.avg_score <= -15:
            return "🔴"
        return "⚪"


def aggregate_market(trends: list[Trend]) -> MarketTrend | None:
    """Agrège les tendances de tout l'univers en une tendance générale de marché."""
    trends = [t for t in trends if t is not None]
    if not trends:
        return None
    bullish = sum(1 for t in trends if t.score >= 15)
    bearish = sum(1 for t in trends if t.score <= -15)
    neutral = len(trends) - bullish - bearish
    avg = sum(t.score for t in trends) / len(trends)
    ranked = sorted(trends, key=lambda t: t.score, reverse=True)
    return MarketTrend(
        n=len(trends), bullish=bullish, bearish=bearish, neutral=neutral,
        avg_score=round(avg, 1),
        top=[(t.symbol, t.score) for t in ranked[:3]],
        bottom=[(t.symbol, t.score) for t in ranked[-3:][::-1]],
    )
