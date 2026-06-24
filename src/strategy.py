"""Stratégie de décision PARTAGÉE entre le mode autonome (live) et la simulation.

Règle (tendance + filtre de surchauffe) :
  • ENTRÉE  : SMA courte > SMA longue ET RSI < rsi_entry_max
  • SORTIE  : SMA courte < SMA longue OU RSI > rsi_exit

Utiliser exactement la même règle des deux côtés garantit que la simulation
historique reflète fidèlement ce que fera le bot en réel.
"""

from __future__ import annotations

import pandas as pd



def position_series(
    df: pd.DataFrame,
    short: int = 20,
    long: int = 50,
    rsi_entry_max: float = 70,
    rsi_exit: float = 80,
) -> pd.Series:
    """Série 0/1 (détenir ou non) — décision de l'ÉQUIPE de stratégies (ensemble).

    Délègue à l'ensemble pondéré (tendance + momentum + retour à la moyenne) ; cette
    fonction reste l'unique point d'entrée partagé entre la simulation et le live.
    """
    from .strategies import ensemble_position_series
    ps = ensemble_position_series(df, short=short, long=long,
                                  rsi_entry_max=rsi_entry_max, rsi_exit=rsi_exit)
    if ps is None or len(ps) == 0:
        return pd.Series(dtype=int)
    return ps


def should_hold(df: pd.DataFrame, **kw) -> bool:
    """Faut-il détenir l'actif maintenant ? (dernière valeur de la série)."""
    ps = position_series(df, **kw)
    return bool(ps.iloc[-1]) if len(ps) else False
