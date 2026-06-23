"""Stratégie de décision PARTAGÉE entre le mode autonome (live) et la simulation.

Règle (tendance + filtre de surchauffe) :
  • ENTRÉE  : SMA courte > SMA longue ET RSI < rsi_entry_max
  • SORTIE  : SMA courte < SMA longue OU RSI > rsi_exit

Utiliser exactement la même règle des deux côtés garantit que la simulation
historique reflète fidèlement ce que fera le bot en réel.
"""

from __future__ import annotations

import pandas as pd

from .indicators.technical import rsi, sma


def position_series(
    df: pd.DataFrame,
    short: int = 20,
    long: int = 50,
    rsi_entry_max: float = 70,
    rsi_exit: float = 80,
) -> pd.Series:
    """Série 0/1 indiquant si l'on doit détenir l'actif chaque jour (avec mémoire d'état)."""
    close = df["close"].astype(float)
    s, l, r = sma(close, short), sma(close, long), rsi(close)
    out = []
    holding = False
    for i in range(len(close)):
        if pd.isna(s.iloc[i]) or pd.isna(l.iloc[i]) or pd.isna(r.iloc[i]):
            out.append(0)
            continue
        if not holding:
            if s.iloc[i] > l.iloc[i] and r.iloc[i] < rsi_entry_max:
                holding = True
        else:
            if s.iloc[i] < l.iloc[i] or r.iloc[i] > rsi_exit:
                holding = False
        out.append(1 if holding else 0)
    return pd.Series(out, index=close.index, dtype=int)


def should_hold(df: pd.DataFrame, **kw) -> bool:
    """Faut-il détenir l'actif maintenant ? (dernière valeur de la série)."""
    ps = position_series(df, **kw)
    return bool(ps.iloc[-1]) if len(ps) else False
