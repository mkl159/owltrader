"""Mise en forme des messages — claire, courte, jamais surchargée."""

from __future__ import annotations

from .models import Quote, Signal
from .service import Analysis


def _fmt_price(p: float | None, cur: str | None = None) -> str:
    if p is None:
        return "—"
    s = f"{p:,.2f}".replace(",", " ")
    return f"{s} {cur}" if cur else s


def quote_line(q: Quote) -> str:
    if q is None:
        return "Donnée indisponible."
    arrow = ""
    if q.change_pct is not None:
        arrow = "▲" if q.change_pct >= 0 else "▼"
    pct = f" {arrow} {q.change_pct:+.2f}%" if q.change_pct is not None else ""
    return (
        f"💱 *{q.symbol}* : {_fmt_price(q.price, q.currency)}{pct}\n"
        f"_source : {q.source} · {q.timestamp:%d/%m %H:%M} UTC_"
    )


def signal_card(sig: Signal) -> str:
    """Carte de signal ultra-courte : Quoi · Pourquoi · Risque."""
    if sig is None:
        return "Pas assez de données pour un signal."
    lines = [
        f"{sig.emoji} *{sig.direction.value}* — {sig.symbol}  (force {sig.score:.0f}/100)",
        f"📌 {sig.reason}",
    ]
    if sig.stop_loss:
        rr = f" · R/R {sig.risk_reward:.1f}" if sig.risk_reward else ""
        lines.append(f"🛡️ stop ≈ {_fmt_price(sig.stop_loss)} · objectif ≈ {_fmt_price(sig.take_profit)}{rr}")
    return "\n".join(lines)


def analysis_full(a: Analysis) -> str:
    """Fiche détaillée (affichée seulement à la demande)."""
    parts = [quote_line(a.quote) if a.quote else f"*{a.asset.raw}*"]
    parts.append("")
    parts.append(signal_card(a.signal))
    ind = a.indicators or {}
    if ind:
        parts.append("")
        parts.append("📐 *Indicateurs*")
        rsi = ind.get("rsi")
        parts.append(f"• RSI : {rsi:.0f}" if rsi is not None else "• RSI : —")
        for label, key in (("SMA50", "sma50"), ("SMA200", "sma200")):
            v = ind.get(key)
            parts.append(f"• {label} : {_fmt_price(v)}")
        macd_h = ind.get("macd_hist")
        if macd_h is not None:
            parts.append(f"• MACD : {'haussier' if macd_h > 0 else 'baissier'}")
    parts.append("")
    parts.append("_⚠️ Outil éducatif — aucune reco d'investissement._")
    return "\n".join(parts)
