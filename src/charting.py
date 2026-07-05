"""Génération de graphiques (image PNG) : cours + moyennes mobiles + RSI."""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sans interface graphique (serveur)
import matplotlib.pyplot as plt  # noqa: E402

from .indicators.technical import rsi, sma  # noqa: E402


def make_chart(symbol: str, df, lookback: int = 180) -> str | None:
    """Graphique complet : cours + SMA 20/50/200, volume et RSI. Renvoie le chemin PNG."""
    if df is None or "close" not in df.columns or len(df) < 30:
        return None
    # calcule la SMA200 sur tout l'historique AVANT de tronquer (sinon vide sur 180j)
    full_close = df["close"].astype(float)
    sma200_full = sma(full_close, 200)
    d = df.tail(lookback)
    close = d["close"].astype(float)
    has_volume = "volume" in d.columns and float(d["volume"].fillna(0).sum()) > 0

    rows = 3 if has_volume else 2
    ratios = [3, 0.8, 1] if has_volume else [3, 1]
    fig, axes = plt.subplots(rows, 1, figsize=(9, 6.5),
                             gridspec_kw={"height_ratios": ratios}, sharex=True)
    ax1 = axes[0]
    ax_rsi = axes[-1]

    ax1.plot(close.index, close, label="Cours", color="#1f77b4", linewidth=1.4)
    ax1.plot(close.index, sma(full_close, 20).tail(lookback), label="SMA20", color="#ff7f0e", linewidth=1)
    ax1.plot(close.index, sma(full_close, 50).tail(lookback), label="SMA50", color="#2ca02c", linewidth=1)
    s200 = sma200_full.tail(lookback)
    if s200.notna().any():
        ax1.plot(close.index, s200, label="SMA200", color="#d62728", linewidth=1, linestyle="--")
    ax1.set_title(f"{symbol} — cours, moyennes mobiles & volume", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.25)

    if has_volume:
        ax_vol = axes[1]
        vols = d["volume"].astype(float)
        colors = ["#2ca02c" if c >= o else "#d62728"
                  for c, o in zip(d["close"], d.get("open", d["close"]), strict=False)]
        ax_vol.bar(vols.index, vols, color=colors, alpha=0.5, width=1.0)
        ax_vol.set_ylabel("Vol.", fontsize=8)
        ax_vol.grid(alpha=0.2)

    r = rsi(close)
    ax_rsi.plot(r.index, r, color="#9467bd", linewidth=1)
    ax_rsi.axhline(70, color="red", linestyle="--", linewidth=0.7)
    ax_rsi.axhline(30, color="green", linestyle="--", linewidth=0.7)
    ax_rsi.fill_between(r.index, 30, 70, alpha=0.05, color="#9467bd")
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI", fontsize=8)
    ax_rsi.grid(alpha=0.25)

    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / f"owltrader_{symbol.replace(':', '_')}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return str(out)


def make_equity_chart(equity, capital: float, title: str = "Évolution du capital",
                      name: str = "equity") -> str | None:
    """Courbe d'évolution du capital (équity) vs capital de départ. equity: Series ou liste de (x,y)."""
    import pandas as pd

    if equity is None:
        return None
    if not isinstance(equity, pd.Series):
        if not equity:
            return None
        idx = [pd.to_datetime(x) for x, _ in equity]
        equity = pd.Series([y for _, y in equity], index=idx)
    if len(equity) < 2:
        return None

    fig, (ax, ax_dd) = plt.subplots(2, 1, figsize=(9, 5.5),
                                    gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    final = float(equity.iloc[-1])
    color = "#2ca02c" if final >= capital else "#d62728"
    ax.plot(equity.index, equity.values, color=color, linewidth=1.6, label="Capital")
    ax.axhline(capital, color="gray", linestyle="--", linewidth=0.9, label=f"Départ ({capital:.0f})")
    ax.fill_between(equity.index, capital, equity.values,
                    where=(equity.values >= capital), color="#2ca02c", alpha=0.12)
    ax.fill_between(equity.index, capital, equity.values,
                    where=(equity.values < capital), color="#d62728", alpha=0.12)
    profit = final - capital
    ax.set_title(f"{title} — {final:.0f} € ({profit:+.0f} €)", fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)

    # Sous-graphe : drawdown (perte depuis le sommet) — le "vécu" du risque
    dd = (equity / equity.cummax() - 1) * 100
    ax_dd.fill_between(dd.index, dd.values, 0, color="#d62728", alpha=0.35)
    ax_dd.set_ylabel("Perte depuis\nsommet (%)", fontsize=7)
    ax_dd.grid(alpha=0.25)
    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / f"owltrader_{name}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return str(out)
