"""Calcul des indicateurs techniques en pandas pur (aucune dépendance fragile)."""

from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line


def bollinger(series: pd.Series, window: int = 20, k: float = 2.0):
    mid = sma(series, window)
    std = series.rolling(window).std()
    return mid + k * std, mid, mid - k * std


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def compute_indicators(df: pd.DataFrame) -> dict:
    """Renvoie un dictionnaire d'indicateurs sur la dernière bougie + séries utiles."""
    close = df["close"]
    macd_line, signal_line, hist = macd(close)
    upper, mid, lower = bollinger(close)
    has_hl = {"high", "low"}.issubset(df.columns)
    atr_series = atr(df) if has_hl else pd.Series(dtype=float)

    def last(s: pd.Series):
        return float(s.iloc[-1]) if len(s) and pd.notna(s.iloc[-1]) else None

    sma50, sma200 = sma(close, 50), sma(close, 200)
    return {
        "close": last(close),
        "sma20": last(sma(close, 20)),
        "sma50": last(sma50),
        "sma200": last(sma200),
        "ema20": last(ema(close, 20)),
        "rsi": last(rsi(close)),
        "macd": last(macd_line),
        "macd_signal": last(signal_line),
        "macd_hist": last(hist),
        "boll_upper": last(upper),
        "boll_lower": last(lower),
        "atr": last(atr_series) if len(atr_series) else None,
        # Patterns simples
        "golden_cross": _cross_up(sma50, sma200),
        "death_cross": _cross_down(sma50, sma200),
        "macd_cross_up": _cross_up(macd_line, signal_line),
        "macd_cross_down": _cross_down(macd_line, signal_line),
    }


def _cross_up(a: pd.Series, b: pd.Series) -> bool:
    if len(a) < 2 or a.iloc[-2:].isna().any() or b.iloc[-2:].isna().any():
        return False
    return a.iloc[-2] <= b.iloc[-2] and a.iloc[-1] > b.iloc[-1]


def _cross_down(a: pd.Series, b: pd.Series) -> bool:
    if len(a) < 2 or a.iloc[-2:].isna().any() or b.iloc[-2:].isna().any():
        return False
    return a.iloc[-2] >= b.iloc[-2] and a.iloc[-1] < b.iloc[-1]
