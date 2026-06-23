"""Handlers du bot Telegram + boucle de surveillance (signaux proactifs)."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from ..config import CONFIG, get_secret
from ..formatting import analysis_full, quote_line, signal_card
from ..models import Direction
from ..service import MarketService
from ..storage import Storage
from ..symbols import Asset

log = logging.getLogger(__name__)

WELCOME = (
    "🦉 *Bienvenue sur OwlTrader !*\n\n"
    "Je surveille les marchés (actions, matières premières, devises, crypto) "
    "depuis plusieurs sources gratuites et je te dis quand *acheter*, *vendre* ou *conserver* — "
    "sans te noyer d'infos.\n\n"
    "*Commandes principales*\n"
    "• /prix `AAPL` — dernier cours\n"
    "• /analyse `AAPL` — fiche + signal\n"
    "• /watch `AAPL` — surveiller (alertes auto)\n"
    "• /unwatch `AAPL` · /liste\n"
    "• /ajouter `AAPL 10 180` — position (qté, prix d'achat)\n"
    "• /portefeuille · /perf\n"
    "• /aide\n\n"
    "_⚠️ Outil éducatif — aucune recommandation d'investissement._"
)


def _svc(context) -> MarketService:
    return context.application.bot_data["svc"]


def _db(context) -> Storage:
    return context.application.bot_data["db"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


async def prix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /prix AAPL")
    q = await asyncio.to_thread(_svc(context).quote, context.args[0])
    if q is None:
        return await update.message.reply_text("❌ Donnée indisponible pour cet actif.")
    await update.message.reply_text(quote_line(q), parse_mode=ParseMode.MARKDOWN)


async def analyse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /analyse AAPL")
    msg = await update.message.reply_text("⏳ Analyse en cours…")
    a = await asyncio.to_thread(_svc(context).analyze, context.args[0])
    await msg.edit_text(analysis_full(a), parse_mode=ParseMode.MARKDOWN)


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /watch AAPL")
    asset = Asset.parse(context.args[0])
    _db(context).add_watch(update.effective_chat.id, asset.raw)
    await update.message.reply_text(f"👁️ Je surveille désormais *{asset.raw}*.", parse_mode=ParseMode.MARKDOWN)


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /unwatch AAPL")
    asset = Asset.parse(context.args[0])
    _db(context).remove_watch(update.effective_chat.id, asset.raw)
    await update.message.reply_text(f"🚫 Je ne surveille plus {asset.raw}.")


async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = _db(context).get_watch(update.effective_chat.id)
    if not items:
        return await update.message.reply_text("Ta liste est vide. Ajoute avec /watch AAPL")
    await update.message.reply_text("👁️ *Surveillés :*\n" + "\n".join(f"• {i}" for i in items),
                                    parse_mode=ParseMode.MARKDOWN)


async def ajouter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        return await update.message.reply_text("Usage : /ajouter AAPL 10 180  (actif, quantité, prix d'achat)")
    try:
        asset = Asset.parse(context.args[0])
        qty = float(context.args[1].replace(",", "."))
        price = float(context.args[2].replace(",", "."))
    except ValueError:
        return await update.message.reply_text("Quantité/prix invalides. Ex : /ajouter AAPL 10 180")
    _db(context).add_position(update.effective_chat.id, asset.raw, qty, price)
    await update.message.reply_text(f"✅ Position ajoutée : {qty:g} × {asset.raw} @ {price:g}")


async def portefeuille(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pos = _db(context).get_positions(update.effective_chat.id)
    if not pos:
        return await update.message.reply_text("Portefeuille vide. Ajoute avec /ajouter AAPL 10 180")
    lines = ["💼 *Ton portefeuille*"]
    for p in pos:
        lines.append(f"• #{p['id']} — {p['quantity']:g} × {p['asset']} @ {p['buy_price']:g}")
    lines.append("\n/perf pour la performance · supprime via /perf")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def perf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pos = _db(context).get_positions(update.effective_chat.id)
    if not pos:
        return await update.message.reply_text("Portefeuille vide.")
    msg = await update.message.reply_text("⏳ Calcul…")
    svc = _svc(context)
    total_cost = total_val = 0.0
    lines = ["💼 *Performance*"]
    for p in pos:
        q = await asyncio.to_thread(svc.quote, p["asset"])
        cost = p["quantity"] * p["buy_price"]
        total_cost += cost
        if q is None:
            lines.append(f"• {p['asset']} : prix indisponible")
            continue
        val = p["quantity"] * q.price
        total_val += val
        pnl = val - cost
        pct = pnl / cost * 100 if cost else 0
        emoji = "🟢" if pnl >= 0 else "🔴"
        lines.append(f"{emoji} {p['asset']} : {pnl:+,.2f} ({pct:+.1f}%)".replace(",", " "))
    if total_cost:
        tot_pnl = total_val - total_cost
        tot_pct = tot_pnl / total_cost * 100
        lines.append(f"\n*Total : {tot_pnl:+,.2f} ({tot_pct:+.1f}%)*".replace(",", " "))
    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def surveiller_job(context: ContextTypes.DEFAULT_TYPE):
    """Boucle périodique : analyse les actifs surveillés et envoie les signaux nouveaux."""
    db: Storage = context.application.bot_data["db"]
    svc: MarketService = context.application.bot_data["svc"]
    min_hours = CONFIG.get("signaux", {}).get("anti_spam_heures", 4)
    for chat_id, asset in db.all_watched_pairs():
        try:
            a = await asyncio.to_thread(svc.analyze, asset)
            sig = a.signal
            if sig is None or sig.direction == Direction.HOLD:
                continue
            if not db.should_alert(chat_id, asset, sig.direction.value, min_hours):
                continue
            await context.bot.send_message(chat_id, signal_card(sig), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:  # noqa: BLE001
            log.warning("Surveillance %s/%s : %s", chat_id, asset, e)


def build_application() -> Application:
    token = get_secret("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "❌ TELEGRAM_BOT_TOKEN manquant. Copie .env.example en .env et renseigne ton token "
            "(obtenu auprès de @BotFather). Pour tester sans Telegram : python -m src.cli analyse AAPL"
        )
    app = Application.builder().token(token).build()
    app.bot_data["svc"] = MarketService()
    app.bot_data["db"] = Storage()

    app.add_handler(CommandHandler(["start", "aide", "help"], start))
    app.add_handler(CommandHandler("prix", prix))
    app.add_handler(CommandHandler("analyse", analyse))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("liste", liste))
    app.add_handler(CommandHandler("ajouter", ajouter))
    app.add_handler(CommandHandler("portefeuille", portefeuille))
    app.add_handler(CommandHandler("perf", perf))

    freq_min = CONFIG.get("frequences", {}).get("actions", 15)
    app.job_queue.run_repeating(surveiller_job, interval=freq_min * 60, first=30)
    return app
