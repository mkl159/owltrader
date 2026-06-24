"""L'« équipe de traders » : plusieurs stratégies indépendantes qui votent ensemble.

- 📈 Suiveur de tendance : croisement de moyennes + filtre RSI (le cœur)
- 🚀 Momentum : achète la force (au-dessus SMA50, perf 3 mois positive, MACD haussier)
- 🔄 Retour à la moyenne : achète les excès de baisse (RSI bas + sous Bollinger)

Chaque stratégie produit une série 0/1 (détenir ou non). L'ENSEMBLE combine les votes
pondérés → décision finale. La même fonction sert au live ET à la simulation (cohérence).
"""

from __future__ import annotations

import pandas as pd

from .indicators.technical import bollinger, macd, rsi, sma


def _state_machine(enter: pd.Series, exit_: pd.Series) -> pd.Series:
    """Construit une série 0/1 avec mémoire : on entre sur `enter`, on sort sur `exit_`."""
    out = []
    holding = False
    e = enter.fillna(False).values
    x = exit_.fillna(False).values
    for i in range(len(enter)):
        if not holding:
            if e[i]:
                holding = True
        else:
            if x[i]:
                holding = False
        out.append(1 if holding else 0)
    return pd.Series(out, index=enter.index, dtype=int)


def trend_position(df: pd.DataFrame, short: int = 20, long: int = 50,
                   rsi_entry_max: float = 70, rsi_exit: float = 80) -> pd.Series:
    close = df["close"].astype(float)
    s, l, r = sma(close, short), sma(close, long), rsi(close)
    enter = (s > l) & (r < rsi_entry_max)
    exit_ = (s < l) | (r > rsi_exit)
    return _state_machine(enter, exit_)


def momentum_position(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    s50 = sma(close, 50)
    macd_line, signal_line, _ = macd(close)
    ret3m = close.pct_change(63)
    enter = (close > s50) & (ret3m > 0) & (macd_line > signal_line)
    exit_ = (close < s50) | (macd_line < signal_line)
    return _state_machine(enter, exit_)


def meanrev_position(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    r = rsi(close)
    _, mid, lower = bollinger(close, 20, 2.0)
    s20 = sma(close, 20)
    enter = (r < 35) & (close < lower)
    exit_ = (r > 55) | (close > s20)
    return _state_machine(enter, exit_)


def breakout_position(df: pd.DataFrame, entry_window: int = 20, exit_window: int = 10) -> pd.Series:
    """Cassure de Donchian — le système des Turtle Traders (Richard Dennis).

    Achat à la cassure du plus-haut sur `entry_window` jours, sortie sous le plus-bas
    sur `exit_window` jours. Approche trend-following historique et robuste.
    """
    close = df["close"].astype(float)
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    upper = high.rolling(entry_window).max().shift(1)
    lower = low.rolling(exit_window).min().shift(1)
    enter = close >= upper
    exit_ = close <= lower
    return _state_machine(enter, exit_)


def ensemble_position_series(df: pd.DataFrame, short: int = 20, long: int = 50,
                             rsi_entry_max: float = 70, rsi_exit: float = 80,
                             w_trend: float = 0.5, w_mom: float = 0.3, w_mr: float = 0.2,
                             threshold: float = 0.45) -> pd.Series:
    """Vote pondéré de l'équipe → 1 si le score atteint le seuil (détenir), 0 sinon."""
    if df is None or "close" not in df.columns or len(df) < 60:
        return pd.Series(dtype=int)
    t = trend_position(df, short, long, rsi_entry_max, rsi_exit)
    m = momentum_position(df)
    r = meanrev_position(df)
    score = w_trend * t + w_mom * m + w_mr * r
    return (score >= threshold).astype(int)


def votes_now(df: pd.DataFrame, **params) -> dict:
    """Détail du vote de chaque stratégie sur la dernière bougie (pour expliquer une décision)."""
    sp = {k: params[k] for k in ("short", "long", "rsi_entry_max", "rsi_exit") if k in params}
    out = {}
    for name, fn in (("tendance", lambda d: trend_position(d, **sp)),
                     ("momentum", momentum_position),
                     ("retour_moyenne", meanrev_position),
                     ("turtle", breakout_position)):
        try:
            s = fn(df)
            out[name] = bool(s.iloc[-1]) if len(s) else False
        except Exception:  # noqa: BLE001
            out[name] = False
    return out
