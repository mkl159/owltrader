"""Tests des indicateurs techniques."""

import pandas as pd

from src.indicators.technical import atr, macd, rsi, sma


def test_sma(uptrend):
    s = sma(uptrend["close"], 20)
    assert len(s) == len(uptrend)
    assert s.iloc[:19].isna().all()       # période de chauffe
    assert pd.notna(s.iloc[-1])


def test_rsi_bornes(uptrend):
    r = rsi(uptrend["close"]).dropna()
    assert (r >= 0).all() and (r <= 100).all()
    # tendance haussière -> RSI plutôt élevé en moyenne
    assert r.mean() > 50


def test_macd(uptrend):
    line, signal, hist = macd(uptrend["close"])
    assert len(line) == len(signal) == len(hist)


def test_atr_positif(uptrend):
    a = atr(uptrend).dropna()
    assert (a >= 0).all()
