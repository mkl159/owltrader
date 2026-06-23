"""Bot Telegram OwlTrader — interface complète (menus à boutons), actus, réglages, digest.

Tout se pilote depuis Telegram :
  • gérer sa watchlist et son portefeuille (boutons),
  • s'informer (cours, analyse, actualités + sentiment),
  • régler la sensibilité des alertes et le résumé quotidien,
  • recevoir des signaux et un digest automatiquement.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from ..config import CONFIG, get_secret
from ..formatting import (
    analysis_full,
    digest_block,
    ideas_block,
    news_block,
    quote_line,
    signal_card,
)
from ..models import Direction
from ..news import get_news
from ..service import MarketService
from ..storage import Storage
from ..symbols import Asset

log = logging.getLogger(__name__)

MD = ParseMode.MARKDOWN

# Sensibilité des alertes → (heures anti-spam, force minimale du signal)
SENSIBILITES = {
    "peu": (12, 70),
    "normale": (4, 0),
    "beaucoup": (1, 0),
}

WELCOME = (
    "🦉 *Bienvenue sur OwlTrader !*\n\n"
    "Je surveille les marchés (actions, matières premières, devises, crypto) depuis plusieurs "
    "sources gratuites et je te dis quand *acheter*, *vendre* ou *conserver* — sans te noyer d'infos.\n\n"
    "👉 Tout se gère ci-dessous, ou tape /aide pour la liste des commandes."
)

HELP = (
    "🦉 *OwlTrader — commandes*\n\n"
    "💡 *Pistes d'achat*\n"
    "• /idees — scan du marché, meilleures opportunités\n\n"
    "📊 *S'informer*\n"
    "• /prix `AAPL` — dernier cours\n"
    "• /analyse `AAPL` — fiche + signal\n"
    "• /actu `AAPL` — actualités + sentiment\n\n"
    "👁️ *Surveillance*\n"
    "• /watch `AAPL` · /unwatch `AAPL` · /liste\n\n"
    "💼 *Portefeuille*\n"
    "• /ajouter `AAPL 10 180` — qté, prix d'achat\n"
    "• /portefeuille · /perf\n\n"
    "⚙️ *Réglages* : /reglages · /digest · /menu\n\n"
    "_⚠️ Outil éducatif — aucune recommandation d'investissement._"
)


def _svc(context) -> MarketService:
    return context.application.bot_data["svc"]


def _db(context) -> Storage:
    return context.application.bot_data["db"]


# --------------------------------------------------------------------------- #
#  Claviers (menus à boutons)
# --------------------------------------------------------------------------- #
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💡 Idées d'achat", callback_data="idees")],
            [InlineKeyboardButton("👁️ Ma watchlist", callback_data="watchlist"),
             InlineKeyboardButton("💼 Portefeuille", callback_data="pf")],
            [InlineKeyboardButton("📈 Performance", callback_data="perf"),
             InlineKeyboardButton("📰 Actus", callback_data="news_menu")],
            [InlineKeyboardButton("⚙️ Réglages", callback_data="settings"),
             InlineKeyboardButton("❓ Aide", callback_data="help")],
        ]
    )


def ideas_keyboard(signals) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"👁️ Suivre {s.symbol}", callback_data=f"watchadd:{s.symbol}")]
            for s in signals[:5]]
    rows.append([InlineKeyboardButton("🔄 Rescanner", callback_data="idees"),
                 InlineKeyboardButton("⬅️ Retour", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def back_button(target: str = "menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data=target)]])


def watchlist_keyboard(assets: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"🔎 {a}", callback_data=f"asset:{a}")] for a in assets]
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def asset_keyboard(raw: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📰 Actus", callback_data=f"news:{raw}"),
             InlineKeyboardButton("🗑️ Retirer", callback_data=f"unwatch:{raw}")],
            [InlineKeyboardButton("⬅️ Watchlist", callback_data="watchlist")],
        ]
    )


def settings_keyboard(s: dict) -> InlineKeyboardMarkup:
    sens = s.get("sensibilite", "normale")
    digest_on = s.get("digest", 1)
    def mark(v):
        return "✅ " if v == sens else ""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{mark('peu')}Peu d'alertes", callback_data="set:sensibilite:peu")],
            [InlineKeyboardButton(f"{mark('normale')}Normale", callback_data="set:sensibilite:normale")],
            [InlineKeyboardButton(f"{mark('beaucoup')}Beaucoup", callback_data="set:sensibilite:beaucoup")],
            [InlineKeyboardButton(
                ("🔕 Digest quotidien : OFF" if not digest_on else "🔔 Digest quotidien : ON"),
                callback_data="set:digest:toggle")],
            [InlineKeyboardButton("⬅️ Retour", callback_data="menu")],
        ]
    )


# --------------------------------------------------------------------------- #
#  Commandes
# --------------------------------------------------------------------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _db(context).get_settings(update.effective_chat.id)  # crée l'entrée si besoin
    await update.message.reply_text(WELCOME, parse_mode=MD, reply_markup=main_menu())


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🦉 *Menu principal*", parse_mode=MD, reply_markup=main_menu())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP, parse_mode=MD)


async def prix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /prix AAPL")
    q = await asyncio.to_thread(_svc(context).quote, context.args[0])
    if q is None:
        return await update.message.reply_text("❌ Donnée indisponible pour cet actif.")
    await update.message.reply_text(quote_line(q), parse_mode=MD)


async def analyse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /analyse AAPL")
    msg = await update.message.reply_text("⏳ Analyse en cours…")
    a = await asyncio.to_thread(_svc(context).analyze, context.args[0])
    await msg.edit_text(analysis_full(a), parse_mode=MD,
                        reply_markup=asset_keyboard(a.asset.raw))


async def actu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /actu AAPL")
    raw = Asset.parse(context.args[0]).raw
    msg = await update.message.reply_text("⏳ Recherche d'actus…")
    items = await asyncio.to_thread(get_news, raw, 5)
    await msg.edit_text(news_block(raw, items), parse_mode=MD,
                        disable_web_page_preview=True)


async def idees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔎 Je scanne le marché à la recherche de pistes…")
    signals = await _scan(context)
    await msg.edit_text(ideas_block(signals), parse_mode=MD,
                        reply_markup=ideas_keyboard(signals))


async def _scan(context):
    universe = CONFIG.get("univers_scan", [])
    return await asyncio.to_thread(_svc(context).scan, universe, 5)


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /watch AAPL")
    asset = Asset.parse(context.args[0])
    _db(context).add_watch(update.effective_chat.id, asset.raw)
    await update.message.reply_text(f"👁️ Je surveille désormais *{asset.raw}*.", parse_mode=MD)


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
    await update.message.reply_text("👁️ *Surveillés :*", parse_mode=MD,
                                    reply_markup=watchlist_keyboard(items))


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
    await _send_portfolio(update.effective_chat.id, context, update.message.reply_text)


async def perf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_perf(update.effective_chat.id, context, update.message.reply_text)


async def reglages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = _db(context).get_settings(update.effective_chat.id)
    await update.message.reply_text(_settings_text(s), parse_mode=MD,
                                    reply_markup=settings_keyboard(s))


async def digest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_digest(update.effective_chat.id, context)


# --------------------------------------------------------------------------- #
#  Helpers d'affichage réutilisables (commandes + boutons)
# --------------------------------------------------------------------------- #
def _settings_text(s: dict) -> str:
    return (
        "⚙️ *Réglages*\n\n"
        f"Sensibilité des alertes : *{s.get('sensibilite', 'normale')}*\n"
        f"Résumé quotidien : *{'activé' if s.get('digest', 1) else 'désactivé'}*\n\n"
        "_Peu = seulement les signaux forts. Beaucoup = alertes plus fréquentes._"
    )


async def _send_portfolio(chat_id, context, sender):
    pos = _db(context).get_positions(chat_id)
    if not pos:
        return await sender("Portefeuille vide. Ajoute avec /ajouter AAPL 10 180")
    lines = ["💼 *Ton portefeuille*"]
    for p in pos:
        lines.append(f"• #{p['id']} — {p['quantity']:g} × {p['asset']} @ {p['buy_price']:g}")
    await sender("\n".join(lines), parse_mode=MD)


async def _send_perf(chat_id, context, sender):
    pos = _db(context).get_positions(chat_id)
    if not pos:
        return await sender("Portefeuille vide.")
    msg = await sender("⏳ Calcul…")
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
        lines.append(f"\n*Total : {tot_pnl:+,.2f} ({tot_pnl / total_cost * 100:+.1f}%)*".replace(",", " "))
    await msg.edit_text("\n".join(lines), parse_mode=MD)


async def _send_digest(chat_id, context):
    watched = _db(context).get_watch(chat_id)
    if not watched:
        return await context.bot.send_message(
            chat_id, "📅 Digest : ta watchlist est vide. Ajoute des actifs avec /watch AAPL")
    svc = _svc(context)
    lines = ["📅 *Résumé du jour*", ""]
    for raw in watched:
        a = await asyncio.to_thread(svc.analyze, raw)
        lines.append(digest_block(raw, a))
    lines.append("\n_⚠️ Outil éducatif — aucune reco d'investissement._")
    await context.bot.send_message(chat_id, "\n".join(lines), parse_mode=MD)


# --------------------------------------------------------------------------- #
#  Routage des boutons (CallbackQuery)
# --------------------------------------------------------------------------- #
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    chat_id = q.message.chat_id
    db = _db(context)

    # Ajout à la watchlist depuis une piste : réponse en pop-up (une seule answer)
    if data.startswith("watchadd:"):
        raw = data.split(":", 1)[1]
        db.add_watch(chat_id, Asset.parse(raw).raw)
        return await q.answer(f"👁️ {raw} ajouté à ta watchlist", show_alert=True)

    await q.answer()

    if data == "menu":
        return await q.edit_message_text("🦉 *Menu principal*", parse_mode=MD, reply_markup=main_menu())
    if data == "help":
        return await q.edit_message_text(HELP, parse_mode=MD, reply_markup=back_button())
    if data == "watchlist":
        items = db.get_watch(chat_id)
        if not items:
            return await q.edit_message_text("Ta watchlist est vide.\nAjoute avec /watch AAPL",
                                             reply_markup=back_button())
        return await q.edit_message_text("👁️ *Ta watchlist* — touche un actif :", parse_mode=MD,
                                         reply_markup=watchlist_keyboard(items))
    if data == "pf":
        return await _send_portfolio(chat_id, context, lambda *a, **k: q.edit_message_text(*a, reply_markup=back_button(), **k))
    if data == "perf":
        await q.edit_message_text("⏳ Calcul…")
        return await _send_perf(chat_id, context, lambda *a, **k: context.bot.send_message(chat_id, *a, **k))
    if data == "idees":
        await q.edit_message_text("🔎 Je scanne le marché à la recherche de pistes…")
        signals = await _scan(context)
        return await q.edit_message_text(ideas_block(signals), parse_mode=MD,
                                         reply_markup=ideas_keyboard(signals))
    if data == "settings":
        s = db.get_settings(chat_id)
        return await q.edit_message_text(_settings_text(s), parse_mode=MD, reply_markup=settings_keyboard(s))
    if data == "news_menu":
        items = db.get_watch(chat_id)
        if not items:
            return await q.edit_message_text("Ajoute des actifs (/watch AAPL) pour suivre leurs actus.",
                                             reply_markup=back_button())
        rows = [[InlineKeyboardButton(f"📰 {a}", callback_data=f"news:{a}")] for a in items]
        rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="menu")])
        return await q.edit_message_text("📰 *Actus* — choisis un actif :", parse_mode=MD,
                                         reply_markup=InlineKeyboardMarkup(rows))

    if data.startswith("asset:"):
        raw = data.split(":", 1)[1]
        await q.edit_message_text("⏳ Analyse…")
        a = await asyncio.to_thread(_svc(context).analyze, raw)
        return await q.edit_message_text(analysis_full(a), parse_mode=MD, reply_markup=asset_keyboard(raw))

    if data.startswith("news:"):
        raw = data.split(":", 1)[1]
        await q.edit_message_text("⏳ Actus…")
        items = await asyncio.to_thread(get_news, raw, 5)
        return await q.edit_message_text(news_block(raw, items), parse_mode=MD,
                                         disable_web_page_preview=True, reply_markup=back_button("watchlist"))

    if data.startswith("unwatch:"):
        raw = data.split(":", 1)[1]
        db.remove_watch(chat_id, raw)
        items = db.get_watch(chat_id)
        if not items:
            return await q.edit_message_text(f"🗑️ {raw} retiré. Watchlist vide.", reply_markup=back_button())
        return await q.edit_message_text(f"🗑️ {raw} retiré.", reply_markup=watchlist_keyboard(items))

    if data.startswith("set:sensibilite:"):
        val = data.split(":")[2]
        db.set_setting(chat_id, "sensibilite", val)
        s = db.get_settings(chat_id)
        return await q.edit_message_text(_settings_text(s), parse_mode=MD, reply_markup=settings_keyboard(s))
    if data == "set:digest:toggle":
        s = db.get_settings(chat_id)
        db.set_setting(chat_id, "digest", 0 if s.get("digest", 1) else 1)
        s = db.get_settings(chat_id)
        return await q.edit_message_text(_settings_text(s), parse_mode=MD, reply_markup=settings_keyboard(s))


# --------------------------------------------------------------------------- #
#  Tâches planifiées
# --------------------------------------------------------------------------- #
async def surveiller_job(context: ContextTypes.DEFAULT_TYPE):
    """Analyse périodiquement les actifs surveillés et envoie les signaux nouveaux."""
    db: Storage = context.application.bot_data["db"]
    svc: MarketService = context.application.bot_data["svc"]
    for chat_id, asset in db.all_watched_pairs():
        try:
            sens = db.get_settings(chat_id).get("sensibilite", "normale")
            min_hours, min_force = SENSIBILITES.get(sens, SENSIBILITES["normale"])
            a = await asyncio.to_thread(svc.analyze, asset)
            sig = a.signal
            if sig is None or sig.direction == Direction.HOLD:
                continue
            if sig.score < min_force and sig.score > (100 - min_force):
                # filtre "peu d'alertes" : ne garde que les signaux marqués
                continue
            if not db.should_alert(chat_id, asset, sig.direction.value, min_hours):
                continue
            await context.bot.send_message(chat_id, signal_card(sig), parse_mode=MD)
        except Exception as e:  # noqa: BLE001
            log.warning("Surveillance %s/%s : %s", chat_id, asset, e)


async def digest_job(context: ContextTypes.DEFAULT_TYPE):
    """Envoie le résumé quotidien aux utilisateurs qui l'ont activé."""
    db: Storage = context.application.bot_data["db"]
    for chat_id in db.chats_with_digest():
        try:
            await _send_digest(chat_id, context)
        except Exception as e:  # noqa: BLE001
            log.warning("Digest %s : %s", chat_id, e)


# --------------------------------------------------------------------------- #
#  Construction de l'application
# --------------------------------------------------------------------------- #
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

    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["aide", "help"], help_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("prix", prix))
    app.add_handler(CommandHandler("analyse", analyse))
    app.add_handler(CommandHandler(["idees", "idee"], idees))
    app.add_handler(CommandHandler("actu", actu))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("liste", liste))
    app.add_handler(CommandHandler("ajouter", ajouter))
    app.add_handler(CommandHandler("portefeuille", portefeuille))
    app.add_handler(CommandHandler("perf", perf))
    app.add_handler(CommandHandler("reglages", reglages))
    app.add_handler(CommandHandler("digest", digest_cmd))
    app.add_handler(CallbackQueryHandler(on_button))

    freq_min = CONFIG.get("frequences", {}).get("actions", 15)
    app.job_queue.run_repeating(surveiller_job, interval=freq_min * 60, first=30)
    # Digest quotidien à 8h (heure du serveur)
    from datetime import time as dtime
    app.job_queue.run_daily(digest_job, time=dtime(hour=8, minute=0))
    return app
