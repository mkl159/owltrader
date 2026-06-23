"""Backtest vectorisé d'une stratégie de croisement de moyennes (long-only).

Stratégie par défaut : on est acheté quand SMA courte > SMA longue, à plat sinon.
Comparé à l'achat-conservation (buy & hold). Métriques de performance complètes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..indicators.technical import sma


@dataclass
class BacktestResult:
    symbol: str
    short: int
    long: int
    start: pd.Timestamp
    end: pd.Timestamp
    strategy_return: float       # rendement total de la stratégie (fraction, 0.25 = +25%)
    buyhold_return: float        # rendement de l'achat-conservation
    n_trades: int
    win_rate: float              # part des trades gagnants (0–1)
    max_drawdown: float          # perte max depuis un sommet (fraction négative)
    exposure: float              # part du temps investi (0–1)

    def beats_buyhold(self) -> bool:
        return self.strategy_return > self.buyhold_return


def run_backtest(symbol: str, df: pd.DataFrame, short: int = 20, long: int = 50) -> BacktestResult | None:
    """Backtest sur l'historique fourni (colonne 'close' requise)."""
    if df is None or "close" not in df.columns or len(df) < long + 5:
        return None

    close = df["close"].astype(float)
    sma_s, sma_l = sma(close, short), sma(close, long)

    # Position : 1 (acheté) si SMA courte > SMA longue, sinon 0. On entre le lendemain
    # du signal pour éviter le biais d'anticipation (look-ahead).
    signal = (sma_s > sma_l).astype(float)
    position = signal.shift(1).fillna(0.0)

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = position * daily_ret

    equity = (1 + strat_ret).cumprod()
    buyhold = (1 + daily_ret).cumprod()

    # Drawdown maximal de la stratégie
    drawdown = equity / equity.cummax() - 1
    max_dd = float(drawdown.min())

    # Trades : transitions 0→1 (entrée) … 1→0 (sortie), rendement par trade
    pos = position.values
    entries = np.where((pos[1:] == 1) & (pos[:-1] == 0))[0] + 1
    trades_returns = []
    for e in entries:
        # cherche la sortie correspondante
        exit_idx = e
        while exit_idx < len(pos) and pos[exit_idx] == 1:
            exit_idx += 1
        seg = close.iloc[e - 1: min(exit_idx, len(close))]
        if len(seg) >= 2:
            trades_returns.append(seg.iloc[-1] / seg.iloc[0] - 1)

    n_trades = len(trades_returns)
    win_rate = (sum(1 for r in trades_returns if r > 0) / n_trades) if n_trades else 0.0

    return BacktestResult(
        symbol=symbol,
        short=short,
        long=long,
        start=close.index[0],
        end=close.index[-1],
        strategy_return=float(equity.iloc[-1] - 1),
        buyhold_return=float(buyhold.iloc[-1] - 1),
        n_trades=n_trades,
        win_rate=win_rate,
        max_drawdown=max_dd,
        exposure=float(position.mean()),
    )
