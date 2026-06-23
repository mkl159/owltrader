"""Génération de graphiques (image PNG) : cours + moyennes mobiles + RSI."""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sans interface graphique (serveur)
import matplotlib.pyplot as plt  # noqa: E402

from .indicators.technical import rsi, sma  # noqa: E402


def make_chart(symbol: str, df, lookback: int = 180) -> str | None:
    """Crée un graphique et renvoie le chemin du PNG (ou None si données insuffisantes)."""
    if df is None or "close" not in df.columns or len(df) < 30:
        return None
    d = df.tail(lookback)
    close = d["close"].astype(float)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 6), gridspec_kw={"height_ratios": [3, 1]}, sharex=True
    )
    ax1.plot(close.index, close, label="Cours", color="#1f77b4", linewidth=1.4)
    ax1.plot(close.index, sma(close, 20), label="SMA20", color="#ff7f0e", linewidth=1)
    ax1.plot(close.index, sma(close, 50), label="SMA50", color="#2ca02c", linewidth=1)
    ax1.set_title(f"{symbol} — cours & moyennes mobiles", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.25)

    r = rsi(close)
    ax2.plot(r.index, r, color="#9467bd", linewidth=1)
    ax2.axhline(70, color="red", linestyle="--", linewidth=0.7)
    ax2.axhline(30, color="green", linestyle="--", linewidth=0.7)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI", fontsize=8)
    ax2.grid(alpha=0.25)

    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / f"owltrader_{symbol.replace(':', '_')}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return str(out)
