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


def fmt_params(p: dict) -> str:
    """Décrit les réglages de stratégie sans caractères Markdown (pas de '_')."""
    if not p:
        return "réglages par défaut"
    return (
        f"MM {p.get('short', '?')}/{p.get('long', '?')} · "
        f"RSI entrée < {p.get('rsi_entry_max', '?')} · "
        f"{p.get('max_positions', '?')} positions · "
        f"{p.get('alloc_pct', '?')}%/position"
    )


def sim_block(r, devise: str = "EUR") -> str:
    """Résultat d'une simulation historique du mode autonome, avec métriques pro."""
    if r is None:
        return "🧪 Simulation impossible (données insuffisantes)."
    verdict = "✅ rentable" if r.profit > 0 else "❌ perdant"
    return (
        f"🧪 *Simulation du mode autonome* ({verdict})\n\n"
        f"💶 Départ : {r.capital:.0f} → 📊 *{r.final_equity:.2f} {devise}*\n"
        f"💰 Bénéfice : *{r.profit:+.2f} {devise}* ({r.total_return*100:+.1f}%)\n"
        f"📈 CAGR (annualisé) : {r.cagr*100:+.1f}%\n\n"
        "*📐 Métriques pro*\n"
        f"• Sharpe : {r.sharpe:.2f} · Sortino : {r.sortino:.2f} · Calmar : {r.calmar:.2f}\n"
        f"• Volatilité annuelle : {r.volatility*100:.1f}%\n"
        f"• Drawdown max : {r.max_drawdown*100:.1f}%\n"
        f"• Profit factor : {r.profit_factor:.2f}\n"
        f"• Trades : {r.n_trades} · réussite {r.win_rate*100:.0f}%\n"
        f"• Meilleur/pire trade : {r.best_trade:+.2f} / {r.worst_trade:+.2f} {devise}\n"
        f"• Frais payés : {r.fees_total:.2f} {devise}\n\n"
        f"⚙️ Réglages : {fmt_params(r.params)}\n"
        "_⚠️ Performances passées ≠ futures. Simulation fictive, éducative._"
    )


def trend_block(t) -> str:
    """Tendance agrégée d'un actif, avec le détail des sources."""
    if t is None:
        return "📊 Tendance indisponible (données insuffisantes)."
    src = {
        "SMA50": "Prix vs MM50", "SMA200": "Prix vs MM200", "alignement": "Alignement MM",
        "MACD": "MACD", "perf_1m": "Perf 1 mois", "perf_3m": "Perf 3 mois",
        "RSI": "RSI", "pente": "Pente EMA20", "actus": "Sentiment actus",
    }
    lines = [
        f"{t.emoji} *Tendance {t.symbol} : {t.label}*",
        f"Score agrégé : *{t.score:+.0f}/100*",
        "",
        "_Sources agrégées :_",
    ]
    for k, v in t.components.items():
        ic = "🟢" if v > 0 else "🔴" if v < 0 else "⚪"
        lines.append(f"{ic} {src.get(k, k)}")
    lines.append("\n_⚠️ Outil éducatif._")
    return "\n".join(lines)


def market_block(m) -> str:
    """Tendance générale du marché (agrégée sur tout l'univers)."""
    if m is None:
        return "🌍 Tendance de marché indisponible."
    barre = "🟢" * round(m.breadth / 10) + "⚪" * (10 - round(m.breadth / 10))
    lines = [
        f"{m.emoji} *Tendance générale du marché : {m.label}*",
        f"Score moyen : *{m.avg_score:+.0f}/100*",
        f"Largeur (breadth) : *{m.breadth:.0f}%* haussiers  {barre}",
        f"🟢 {m.bullish} haussiers · ⚪ {m.neutral} neutres · 🔴 {m.bearish} baissiers  (sur {m.n})",
        "",
        "📈 *Plus haussiers* : " + ", ".join(f"{s} ({sc:+.0f})" for s, sc in m.top),
        "📉 *Plus baissiers* : " + ", ".join(f"{s} ({sc:+.0f})" for s, sc in m.bottom),
        "\n_⚠️ Outil éducatif — vue d'ensemble, pas une reco._",
    ]
    return "\n".join(lines)


def autobilan_block(acc: dict, equity: float, holdings: list, trades_today: list) -> str:
    """Bilan du compte autonome : valeur, bénéfice, cash, total investi, positions, actions."""
    dev = acc.get("devise", "EUR")
    cap = acc["capital"]
    cash = acc["cash"]
    invested = sum(h["value"] for h in holdings)
    profit = equity - cap
    emoji = "🟢" if profit >= 0 else "🔴"
    inv_pct = invested / equity * 100 if equity else 0
    lines = [
        f"{emoji} *Bilan du portefeuille autonome*",
        "",
        f"📊 *Total : {equity:.2f} {dev}*  (départ {cap:.0f})",
        f"💰 Bénéfice : *{profit:+.2f} {dev}* ({profit/cap*100:+.1f}%)",
        "",
        f"💵 Cash dispo : *{cash:.2f} {dev}*",
        f"📦 Investi en actions : *{invested:.2f} {dev}* ({len(holdings)} position(s), {inv_pct:.0f}% du total)",
        "",
    ]
    if holdings:
        lines.append("*Détail des positions*")
        for h in holdings:
            pnl = h.get("pnl_pct")
            tag = f" ({pnl:+.1f}%)" if pnl is not None else ""
            lines.append(f"• {h['asset']} : {h['value']:.2f} {dev}{tag}")
    else:
        lines.append("📦 Aucune position — tout est en cash.")
    if trades_today:
        lines.append("\n📝 *Actions du jour*")
        for t in trades_today:
            ic = "🟢 ACHAT" if t["side"] == "ACHAT" else "🔴 VENTE"
            pnl = f" · résultat {t['pnl']:+.2f}" if t["side"] == "VENTE" else ""
            lines.append(f"{ic} {t['asset']} : {t['quantity']:.4g} @ {t['price']:.2f} (frais {t['fee']:.2f}){pnl}")
    else:
        lines.append("\n📝 Aucune action aujourd'hui — il surveille (positions stables).")
    lines.append("\n_⚠️ Trading fictif — aucune transaction réelle._")
    return "\n".join(lines)


def state_recap(cash: float, invested: float, n_positions: int, equity: float,
                capital: float, devise: str = "EUR") -> str:
    """Récap court de l'état du compte, envoyé après chaque action autonome."""
    profit = equity - capital
    emoji = "🟢" if profit >= 0 else "🔴"
    return (
        f"{emoji} *État du compte autonome*\n"
        f"💵 Cash : {cash:.2f} {devise}\n"
        f"📦 En actions : {invested:.2f} {devise} ({n_positions} position(s))\n"
        f"📊 Total : *{equity:.2f} {devise}* ({profit:+.2f} / {profit/capital*100:+.1f}%)"
    )


def trade_log(side: str, asset: str, qty: float, price: float, fee: float,
              pnl: float | None = None, devise: str = "EUR") -> str:
    """Message court loggué dans le chat à chaque achat/vente autonome."""
    if side == "ACHAT":
        return (f"🟢 *ACHAT* {asset}\n{qty:.4g} @ {price:.2f} {devise} "
                f"(frais {fee:.2f} {devise})")
    pnl_txt = f"\nRésultat : *{pnl:+.2f} {devise}*" if pnl is not None else ""
    return (f"🔴 *VENTE* {asset}\n{qty:.4g} @ {price:.2f} {devise} "
            f"(frais {fee:.2f} {devise}){pnl_txt}")


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
