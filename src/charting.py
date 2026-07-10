"""Génération de graphiques (image PNG) : cours + moyennes mobiles + RSI."""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sans interface graphique (serveur)
import matplotlib.pyplot as plt  # noqa: E402

from .indicators.technical import rsi, sma  # noqa: E402

# --- Thème sombre "pro" (façon TradingView / Maestro) --------------------------------
DARK_BG = "#131722"        # fond TradingView
PANEL_BG = "#131722"
FG = "#d1d4dc"             # texte gris clair
GRID = "#2a2e39"
GREEN = "#26a69a"          # vert sarcelle TradingView
RED = "#ef5350"
BLUE = "#2962ff"
ORANGE = "#ff9800"
PURPLE = "#ab47bc"

_DARK_RC = {
    "figure.facecolor": DARK_BG, "axes.facecolor": PANEL_BG,
    "savefig.facecolor": DARK_BG, "axes.edgecolor": GRID,
    "axes.labelcolor": FG, "text.color": FG,
    "xtick.color": FG, "ytick.color": FG,
    "grid.color": GRID, "grid.alpha": 0.6,
    "legend.facecolor": PANEL_BG, "legend.edgecolor": GRID,
    "font.size": 9,
}


def _watermark(fig):
    fig.text(0.99, 0.01, "OwlTrader", ha="right", va="bottom",
             fontsize=9, color=FG, alpha=0.35, fontweight="bold")


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
    with plt.rc_context(_DARK_RC):
        fig, axes = plt.subplots(rows, 1, figsize=(9, 6.5),
                                 gridspec_kw={"height_ratios": ratios}, sharex=True)
        ax1 = axes[0]
        ax_rsi = axes[-1]

        up = float(close.iloc[-1]) >= float(close.iloc[0])
        line_color = GREEN if up else RED
        ax1.plot(close.index, close, label="Cours", color=line_color, linewidth=1.6)
        # dégradé sous le cours (le "wow" TradingView)
        ax1.fill_between(close.index, close.min(), close, color=line_color, alpha=0.12)
        ax1.plot(close.index, sma(full_close, 20).tail(lookback), label="SMA20",
                 color=ORANGE, linewidth=1)
        ax1.plot(close.index, sma(full_close, 50).tail(lookback), label="SMA50",
                 color=BLUE, linewidth=1)
        s200 = sma200_full.tail(lookback)
        if s200.notna().any():
            ax1.plot(close.index, s200, label="SMA200", color=FG, linewidth=1,
                     linestyle="--", alpha=0.7)
        chg = (float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100
        ax1.set_title(f"{symbol}   {close.iloc[-1]:,.2f}   {chg:+.1f}%",
                      fontsize=13, fontweight="bold", color=line_color, loc="left")
        ax1.legend(loc="upper left", fontsize=8)
        ax1.grid(alpha=0.6, linewidth=0.5)

        if has_volume:
            ax_vol = axes[1]
            vols = d["volume"].astype(float)
            colors = [GREEN if c >= o else RED
                      for c, o in zip(d["close"], d.get("open", d["close"]), strict=False)]
            ax_vol.bar(vols.index, vols, color=colors, alpha=0.55, width=1.0)
            ax_vol.set_ylabel("Vol.", fontsize=8)
            ax_vol.grid(alpha=0.4, linewidth=0.5)

        r = rsi(close)
        ax_rsi.plot(r.index, r, color=PURPLE, linewidth=1.2)
        ax_rsi.axhline(70, color=RED, linestyle="--", linewidth=0.7)
        ax_rsi.axhline(30, color=GREEN, linestyle="--", linewidth=0.7)
        ax_rsi.fill_between(r.index, 30, 70, alpha=0.08, color=PURPLE)
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_ylabel("RSI", fontsize=8)
        ax_rsi.grid(alpha=0.6, linewidth=0.5)

        fig.tight_layout()
        _watermark(fig)
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

    with plt.rc_context(_DARK_RC):
        fig, (ax, ax_dd) = plt.subplots(2, 1, figsize=(9, 5.5),
                                        gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
        final = float(equity.iloc[-1])
        color = GREEN if final >= capital else RED
        ax.plot(equity.index, equity.values, color=color, linewidth=1.8, label="Capital")
        ax.axhline(capital, color=FG, linestyle="--", linewidth=0.9, alpha=0.6,
                   label=f"Départ ({capital:.0f})")
        ax.fill_between(equity.index, capital, equity.values,
                        where=(equity.values >= capital), color=GREEN, alpha=0.18)
        ax.fill_between(equity.index, capital, equity.values,
                        where=(equity.values < capital), color=RED, alpha=0.18)
        profit = final - capital
        pct = profit / capital * 100 if capital else 0
        ax.set_title(f"{title}   {final:,.0f}   {profit:+,.0f} ({pct:+.1f}%)",
                     fontsize=13, fontweight="bold", color=color, loc="left")
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(alpha=0.6, linewidth=0.5)

        # Sous-graphe : drawdown (perte depuis le sommet) — le "vécu" du risque
        dd = (equity / equity.cummax() - 1) * 100
        ax_dd.fill_between(dd.index, dd.values, 0, color=RED, alpha=0.45)
        ax_dd.set_ylabel("Perte depuis\nsommet (%)", fontsize=7)
        ax_dd.grid(alpha=0.6, linewidth=0.5)
        fig.tight_layout()
        _watermark(fig)
        out = Path(tempfile.gettempdir()) / f"owltrader_{name}.png"
        fig.savefig(out, dpi=110)
        plt.close(fig)
    return str(out)
