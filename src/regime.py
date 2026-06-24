"""Filtre de régime de marché : n'acheter que quand le marché global est porteur.

Technique classique des suiveurs de tendance : si l'indice de référence (S&P 500) est
sous sa moyenne 200 jours, on cesse d'OUVRIR de nouvelles positions (on garde/solde les
existantes). Objectif : éviter d'acheter en plein bear market et réduire les drawdowns.
"""

from __future__ import annotations

import pandas as pd

from .indicators.technical import sma


def regime_series(market_df: pd.DataFrame, window: int = 200) -> pd.Series:
    """Série booléenne : True quand le marché est au-dessus de sa MM `window` (achats permis)."""
    if market_df is None or "close" not in market_df.columns:
        return pd.Series(dtype=bool)
    close = market_df["close"].astype(float)
    ok = close > sma(close, window)
    return ok.fillna(False)


def market_ok_now(market_df: pd.DataFrame, window: int = 200) -> bool:
    """Le marché autorise-t-il les achats maintenant ? (True si pas de donnée → neutre)."""
    s = regime_series(market_df, window)
    return bool(s.iloc[-1]) if len(s) else True
