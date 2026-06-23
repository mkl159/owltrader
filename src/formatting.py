"""Mise en forme des messages — claire, courte, jamais surchargée."""

from __future__ import annotations

from .models import Direction, Quote, Signal
from .news.collector import NewsItem, aggregate_sentiment
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


def _esc(text: str) -> str:
    # échappe les caractères Markdown susceptibles de casser le rendu
    for ch in ("_", "*", "[", "]", "`"):
        text = text.replace(ch, " ")
    return text


def news_block(symbol: str, items: list[NewsItem]) -> str:
    """Liste courte d'actus avec humeur (sentiment) et lien."""
    if not items:
        return f"📰 Aucune actu récente pour *{symbol}*."
    avg = aggregate_sentiment(items)
    tone = "🟢 plutôt positif" if avg > 0.15 else "🔴 plutôt négatif" if avg < -0.15 else "⚪ neutre"
    lines = [f"📰 *Actus — {symbol}*  (ton global : {tone})", ""]
    for it in items:
        when = f"{it.published:%d/%m %H:%M}" if it.published else ""
        lines.append(f"{it.mood} [{_esc(it.title)}]({it.link})\n_{it.source} · {when}_")
    lines.append("\n_⚠️ Outil éducatif — vérifie toujours tes sources._")
    return "\n".join(lines)


def ideas_block(signals: list[Signal]) -> str:
    """Liste des meilleures pistes d'achat repérées par le scan du marché."""
    if not signals:
        return (
            "💡 *Pistes d'achat*\n\nAucune piste exploitable pour le moment "
            "(données indisponibles). Réessaie plus tard."
        )
    buys = [s for s in signals if s.direction == Direction.BUY]
    if buys:
        lines = ["💡 *Pistes d'achat repérées*  _(classées par force)_", ""]
        pool = buys
    else:
        lines = ["💡 *Pas de signal d'achat franc actuellement.*", "",
                 "À surveiller (les mieux notés) :", ""]
        pool = signals
    for i, s in enumerate(pool, 1):
        line = f"{i}. {s.emoji} *{s.symbol}* — force {s.score:.0f}/100\n   📌 {s.reason}"
        if s.stop_loss:
            rr = f" · R/R {s.risk_reward:.1f}" if s.risk_reward else ""
            line += f"\n   🛡️ stop ≈ {_fmt_price(s.stop_loss)} · objectif ≈ {_fmt_price(s.take_profit)}{rr}"
        lines.append(line)
    lines.append("\n_⚠️ Outil éducatif — aucune reco d'investissement. À toi de décider._")
    return "\n".join(lines)


def backtest_block(r) -> str:
    """Résultat de backtest, clair et synthétique."""
    if r is None:
        return "🧪 Backtest impossible (pas assez d'historique pour cet actif)."
    verdict = "✅ bat l'achat-conservation" if r.beats_buyhold() else "❌ sous l'achat-conservation"
    return (
        f"🧪 *Backtest — {r.symbol}*\n"
        f"_Stratégie croisement SMA{r.short}/SMA{r.long} · {r.start:%m/%Y}→{r.end:%m/%Y}_\n\n"
        f"• Rendement stratégie : *{r.strategy_return*100:+.1f}%*\n"
        f"• Achat-conservation : {r.buyhold_return*100:+.1f}%  ({verdict})\n"
        f"• Trades : {r.n_trades} · réussite : {r.win_rate*100:.0f}%\n"
        f"• Drawdown max : {r.max_drawdown*100:.1f}%\n"
        f"• Temps investi : {r.exposure*100:.0f}%\n\n"
        "_⚠️ Performances passées ≠ performances futures. Outil éducatif._"
    )


def movers_block(movers: list) -> str:
    """Top hausses et baisses du jour."""
    if not movers:
        return "🚀 Aucune donnée de variation disponible."
    gainers = movers[:3]
    losers = list(reversed(movers[-3:]))
    lines = ["🚀 *Plus fortes variations du jour*", "", "📈 *Hausses*"]
    for raw, q in gainers:
        lines.append(f"🟢 {raw} : {q.change_pct:+.2f}%  ({_fmt_price(q.price, q.currency)})")
    lines.append("\n📉 *Baisses*")
    for raw, q in losers:
        lines.append(f"🔴 {raw} : {q.change_pct:+.2f}%  ({_fmt_price(q.price, q.currency)})")
    return "\n".join(lines)


def digest_block(symbol: str, a: Analysis) -> str:
    """Une ligne synthétique par actif pour le résumé quotidien."""
    if a.quote is None:
        return f"• *{symbol}* : donnée indisponible"
    pct = f" {a.quote.change_pct:+.1f}%" if a.quote.change_pct is not None else ""
    sig = ""
    if a.signal:
        sig = f" — {a.signal.emoji} {a.signal.direction.value}"
    return f"• *{symbol}* : {_fmt_price(a.quote.price, a.quote.currency)}{pct}{sig}"
