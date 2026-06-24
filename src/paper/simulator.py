"""Simulateur historique de portefeuille autonome (multi-actifs, avec frais).

Rejoue jour par jour la stratégie partagée sur un univers d'actifs, en partant d'un
capital donné, avec frais de courtage à l'achat et à la vente. Sert à la fois à
prouver la rentabilité (backtest) et à l'auto-tuning des paramètres.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..strategy import position_series
from .fees import courtage


@dataclass
class SimResult:
    capital: float
    final_equity: float
    equity_curve: pd.Series
    trades: list[dict]
    fees_total: float
    n_trades: int
    win_rate: float
    max_drawdown: float
    sharpe: float = 0.0
    cagr: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    volatility: float = 0.0
    profit_factor: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    params: dict = field(default_factory=dict)

    @property
    def profit(self) -> float:
        return self.final_equity - self.capital

    @property
    def total_return(self) -> float:
        return self.final_equity / self.capital - 1 if self.capital else 0.0


def simulate(
    histories: dict[str, pd.DataFrame],
    capital: float = 1000.0,
    fee_pct: float = 0.20,
    fee_min: float = 1.0,
    max_positions: int = 5,
    alloc_pct: float = 20.0,
    short: int = 20,
    long: int = 50,
    rsi_entry_max: float = 70,
    rsi_exit: float = 80,
    stop_loss_pct: float = 0.0,
    max_dd_pause: float = 0.0,
    trailing_stop_pct: float = 0.0,
    market_df=None,
    seasonal_filter: bool = False,
    vix_df=None,
    vix_max: float = 0.0,
    vol_target: float = 0.0,
) -> SimResult | None:
    """Simule la gestion autonome sur l'historique fourni. histories: {actif: df OHLCV}."""
    histories = {k: v for k, v in histories.items() if v is not None and "close" in v and len(v) > long + 5}
    if not histories:
        return None

    # Positions désirées par actif (décalées d'un jour : exécution au lendemain du signal)
    desired = {}
    closes = {}
    for asset, df in histories.items():
        ps = position_series(df, short, long, rsi_entry_max, rsi_exit).shift(1).fillna(0)
        desired[asset] = ps
        closes[asset] = df["close"].astype(float)

    closes_df = pd.DataFrame(closes).sort_index().ffill()
    # Volatilité annualisée glissante (pour le dimensionnement par volatilité)
    vol_df = None
    if vol_target and vol_target > 0:
        vol_df = closes_df.pct_change().rolling(20).std() * (252 ** 0.5)
    # ffill (et non fillna 0) : un jour sans cotation conserve l'état précédent
    # — sinon les actions seraient "vendues" chaque week-end puis rachetées (churn + frais).
    desired_df = pd.DataFrame(desired).reindex(closes_df.index).ffill().fillna(0).astype(int)
    dates = closes_df.index

    cash = capital
    holdings: dict[str, float] = {}
    entry: dict[str, dict] = {}
    trades: list[dict] = []
    fees_total = 0.0
    equity_points = []

    sl = stop_loss_pct / 100.0 if stop_loss_pct else 0.0
    ts = trailing_stop_pct / 100.0 if trailing_stop_pct else 0.0
    ddp = max_dd_pause / 100.0 if max_dd_pause else 0.0
    peak = capital

    # Filtre de régime de marché (achats permis uniquement si le marché est porteur)
    regime = None
    if market_df is not None:
        from ..regime import regime_series
        regime = regime_series(market_df).reindex(closes_df.index).ffill().fillna(False)
    # Filtre de risque (VIX) : pas d'achat quand la peur dépasse un seuil
    vix = None
    if vix_df is not None and vix_max > 0:
        vix = vix_df["close"].astype(float).reindex(closes_df.index).ffill()

    for t in dates:
        # --- VENTES (stratégie OU stop-loss du risk manager) ---
        for asset in list(holdings):
            price = closes_df.at[t, asset]
            if pd.isna(price):
                continue
            entry[asset]["peak"] = max(entry[asset].get("peak", entry[asset]["price"]), price)
            stop_hit = sl > 0 and price <= entry[asset]["price"] * (1 - sl)
            trail_hit = ts > 0 and price <= entry[asset]["peak"] * (1 - ts)
            if desired_df.at[t, asset] == 0 or stop_hit or trail_hit:
                qty = holdings.pop(asset)
                gross = qty * price
                fee = courtage(gross, fee_pct, fee_min)
                cash += gross - fee
                fees_total += fee
                ep = entry.pop(asset)
                pnl = (price - ep["price"]) * qty - fee - ep["fee"]
                trades.append({"date": t, "asset": asset, "side": "VENTE", "qty": qty,
                               "price": price, "fee": fee, "pnl": pnl,
                               "motif": "stop-loss" if stop_hit else "signal"})

        # --- Coupe-circuit : si trop de pertes depuis le sommet, on cesse d'acheter ---
        equity_pre = cash + sum(holdings[a] * closes_df.at[t, a] for a in holdings)
        peak = max(peak, equity_pre)
        paused = ddp > 0 and equity_pre < peak * (1 - ddp)
        if regime is not None and not bool(regime.get(t, True)):
            paused = True  # marché baissier : on n'ouvre pas de nouvelle position
        if seasonal_filter and t.month not in (11, 12, 1, 2, 3, 4):
            paused = True  # période faible (« sell in May ») : pas de nouvel achat
        if vix is not None and vix.get(t, 0) > vix_max:
            paused = True  # peur extrême (VIX élevé) : on n'ouvre pas de position

        # --- ACHATS ---
        free = max_positions - len(holdings)
        if free > 0 and cash > fee_min + 10 and not paused:
            equity_now = cash + sum(holdings[a] * closes_df.at[t, a] for a in holdings)
            cands = [a for a in desired_df.columns
                     if desired_df.at[t, a] == 1 and a not in holdings and not pd.isna(closes_df.at[t, a])]
            for a in cands[:free]:
                base = equity_now * alloc_pct / 100.0
                if vol_df is not None:
                    v = vol_df.at[t, a]
                    if pd.notna(v) and v > 0:
                        base *= min(1.5, max(0.5, vol_target / v))  # moins sur les actifs volatils
                target = min(base, cash - fee_min)
                if target < 10:
                    continue
                price = closes_df.at[t, a]
                gross = target / (1 + fee_pct / 100.0)
                fee = courtage(gross, fee_pct, fee_min)
                if gross + fee > cash:
                    gross = cash - fee
                if gross < 10:
                    continue
                qty = gross / price
                cash -= gross + fee
                fees_total += fee
                holdings[a] = qty
                entry[a] = {"price": price, "fee": fee}
                trades.append({"date": t, "asset": a, "side": "ACHAT", "qty": qty,
                               "price": price, "fee": fee, "pnl": 0.0})

        equity = cash + sum(holdings[a] * closes_df.at[t, a] for a in holdings)
        equity_points.append(equity)

    equity_curve = pd.Series(equity_points, index=dates)
    drawdown = (equity_curve / equity_curve.cummax() - 1).min()
    sells = [tr for tr in trades if tr["side"] == "VENTE"]
    wins = sum(1 for tr in sells if tr["pnl"] > 0)
    win_rate = wins / len(sells) if sells else 0.0

    # --- Métriques pro ---
    rets = equity_curve.pct_change().dropna()
    std = rets.std()
    downside = rets[rets < 0].std()
    sharpe = float(rets.mean() / std * (252 ** 0.5)) if std > 0 else 0.0
    sortino = float(rets.mean() / downside * (252 ** 0.5)) if downside and downside > 0 else 0.0
    volatility = float(std * (252 ** 0.5)) if std > 0 else 0.0
    years = max((dates[-1] - dates[0]).days / 365.25, 1e-9)
    cagr = float((equity_curve.iloc[-1] / capital) ** (1 / years) - 1) if capital > 0 else 0.0
    calmar = float(cagr / abs(drawdown)) if drawdown < 0 else 0.0
    gains = sum(tr["pnl"] for tr in sells if tr["pnl"] > 0)
    losses = -sum(tr["pnl"] for tr in sells if tr["pnl"] < 0)
    profit_factor = float(gains / losses) if losses > 0 else (gains if gains else 0.0)
    pnls = [tr["pnl"] for tr in sells]
    best_trade = float(max(pnls)) if pnls else 0.0
    worst_trade = float(min(pnls)) if pnls else 0.0

    return SimResult(
        capital=capital,
        final_equity=float(equity_curve.iloc[-1]),
        equity_curve=equity_curve,
        trades=trades,
        fees_total=round(fees_total, 2),
        n_trades=len(trades),
        win_rate=win_rate,
        max_drawdown=float(drawdown),
        sharpe=round(sharpe, 2),
        cagr=cagr,
        sortino=round(sortino, 2),
        calmar=round(calmar, 2),
        volatility=volatility,
        profit_factor=round(profit_factor, 2),
        best_trade=round(best_trade, 2),
        worst_trade=round(worst_trade, 2),
        params={"short": short, "long": long, "rsi_entry_max": rsi_entry_max,
                "rsi_exit": rsi_exit, "max_positions": max_positions, "alloc_pct": alloc_pct},
    )
