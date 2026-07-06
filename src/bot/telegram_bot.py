"""Bot Telegram OwlTrader — interface complète (menus à boutons), actus, réglages, digest.

Tout se pilote depuis Telegram :
  • gérer sa watchlist et son portefeuille (boutons),
  • s'informer (cours, analyse, actualités + sentiment),
  • régler la sensibilité des alertes et le résumé quotidien,
  • recevoir des signaux et un digest automatiquement.
"""

from __future__ import annotations

import asyncio
import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from ..config import CONFIG, get_secret
from ..charting import make_chart, make_equity_chart
from ..formatting import (
    analysis_full,
    autobilan_block,
    backtest_block,
    digest_block,
    fmt_params,
    ideas_block,
    movers_block,
    market_block,
    news_block,
    quote_line,
    sim_block,
    signal_card,
    state_recap,
    team_block,
    trade_log,
    trend_block,
)
from ..i18n import DEFAULT_LANG, normalize_lang, t
from ..models import Direction
from ..news import get_news
from ..paper import trader
from ..paper.profiles import AGRESSIVITES, profile
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
    "Ton assistant de marché — actions, crypto, devises, matières premières — qui te dit "
    "*acheter*, *vendre* ou *conserver*, sans jargon et sans te noyer d'infos.\n\n"
    "✨ *Pour bien démarrer :*\n"
    "1️⃣ 🧪 *Simuler* — vois la stratégie prouvée sur 10 ans\n"
    "2️⃣ 🤖 *Mode autonome* — confie-lui 1000 € fictifs, il trade tout seul\n"
    "3️⃣ 💡 *Idées d'achat* — les meilleures opportunités du moment\n\n"
    "_100 % gratuit · trading fictif · aucun risque. Touche un bouton 👇_"
)

HELP = (
    "🦉 *OwlTrader — commandes*\n\n"
    "🤖 *Mode autonome (fictif)*\n"
    "• /auto `1000` — gère 1000 € tout seul (achat/vente, frais inclus)\n"
    "• /bilan — où il en est + graphique\n"
    "• /simuler — backtest + métriques pro (Sharpe, Sortino, Calmar…)\n"
    "• /agressivite — prudent / normale / agressif\n"
    "• /autotune — ré-régler la stratégie · /reset · /stopauto\n"
    "• /alpaca — connexion à un vrai compte paper-trading (API)\n\n"
    "💡 *Pistes & marché*\n"
    "• /idees — meilleures opportunités (filtre : /idees crypto)\n"
    "• /equipe `AAPL` — le vote de l'équipe de stratégies\n"
    "• /maitres — les traders légendaires derrière le bot\n"
    "• /tendance `AAPL` — tendance agrégée (multi-sources)\n"
    "• /marche — tendance générale du marché\n"
    "• /macro — régime cross-actifs risk-on/risk-off\n"
    "• /saison — contexte saisonnier + jours fériés\n"
    "• /risque — climat macro/géopolitique (VIX + actus)\n"
    "• /movers — plus fortes hausses/baisses du jour\n\n"
    "📊 *S'informer*\n"
    "• /prix `AAPL` — dernier cours\n"
    "• /analyse `AAPL` — fiche + signal (avec sentiment des actus)\n"
    "• /graph `AAPL` — graphique cours + RSI\n"
    "• /backtest `AAPL` — test d'une stratégie sur l'historique\n"
    "• /actu `AAPL` — actualités + sentiment\n\n"
    "🔔 *Alertes & univers*\n"
    "• /alerte `AAPL 200` — m'alerter au franchissement d'un prix\n"
    "• /alertes — voir/supprimer mes alertes\n"
    "• /univers — voir/modifier les actifs tradés (add/remove)\n\n"
    "👁️ *Surveillance*\n"
    "• /watch `AAPL` · /unwatch `AAPL` · /liste\n\n"
    "💼 *Portefeuille*\n"
    "• /ajouter `AAPL 10 180` — qté, prix d'achat\n"
    "• /portefeuille · /perf\n\n"
    "🧠 *Conseiller IA (facultatif)*\n"
    "• /ia — avis OpenAI acheter/vendre (1 req/jour, activable/désactivable)\n\n"
    "🔌 *Connecteurs & sauvegarde*\n"
    "• /config — régler les clés API (chiffrées) · /set · /del\n"
    "• /securite — tableau de bord sécurité · /deconnexion\n"
    "• /traderepublic — lire ton compte TR réel (cash, positions) — lecture seule\n"
    "• /broker — connexion à un échange (Binance, Kraken… via ccxt)\n"
    "• /export — exporter la config · /sauvegarde — sauvegarder la base\n\n"
    "⚙️ *Réglages* : /reglages · /digest · /menu · /langue\n\n"
    "_⚠️ Outil éducatif — aucune recommandation d'investissement._"
)

HELP_EN = (
    "🦉 *OwlTrader — commands*\n\n"
    "🤖 *Autonomous mode (fictional)*\n"
    "• /auto `1000` — manages €1000 on its own (buy/sell, fees included)\n"
    "• /bilan — status + chart · /simuler — backtest + pro metrics\n"
    "• /agressivite — conservative / normal / aggressive\n"
    "• /autotune — re-tune · /reset · /stopauto · /alpaca\n\n"
    "📊 *Market & ideas*\n"
    "• /apercu — full market briefing (all-in-one)\n"
    "• /idees — best buy opportunities · /equipe `AAPL` — strategy team vote\n"
    "• /maitres — the legendary traders behind the bot\n"
    "• /tendance `AAPL` · /marche · /saison · /risque · /movers\n\n"
    "📈 *Research an asset*\n"
    "• /prix `AAPL` · /analyse `AAPL` · /graph `AAPL` · /backtest `AAPL` · /actu `AAPL`\n\n"
    "🔔 *Alerts & universe*\n"
    "• /alerte `AAPL 200` · /alertes · /univers · /sources\n\n"
    "👁️ *Watchlist* : /watch · /unwatch · /liste\n"
    "💼 *Portfolio* : /ajouter `AAPL 10 180` · /portefeuille · /perf\n\n"
    "🧠 *AI advisor (optional)*\n"
    "• /ia — OpenAI buy/sell advice (1 req/day, toggleable)\n\n"
    "🔌 *Connectors & backup*\n"
    "• /config — set API keys (encrypted) · /set · /del\n"
    "• /securite — security dashboard · /deconnexion (logout)\n"
    "• /broker — connect to an exchange (Binance, Kraken… via ccxt)\n"
    "• /export — export config · /sauvegarde — back up the database\n\n"
    "⚙️ *Settings* : /reglages · /digest · /menu · /langue\n\n"
    "_⚠️ Educational tool — not investment advice._"
)


def _svc(context) -> MarketService:
    return context.application.bot_data["svc"]


def _db(context) -> Storage:
    return context.application.bot_data["db"]


def _lang(context, chat_id: int) -> str:
    """Langue choisie par l'utilisateur (fr par défaut)."""
    try:
        return _db(context).get_settings(chat_id).get("langue", DEFAULT_LANG)
    except Exception:  # noqa: BLE001
        return DEFAULT_LANG


# --------------------------------------------------------------------------- #
#  Claviers (menus à boutons)
# --------------------------------------------------------------------------- #
def main_menu(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    b = lambda k: t(k, lang)  # noqa: E731
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(b("btn_briefing"), callback_data="apercu")],
            [InlineKeyboardButton(b("btn_auto"), callback_data="auto_menu"),
             InlineKeyboardButton(b("btn_simulate"), callback_data="simuler")],
            [InlineKeyboardButton(b("btn_ideas"), callback_data="idees"),
             InlineKeyboardButton(b("btn_movers"), callback_data="movers")],
            [InlineKeyboardButton(b("btn_market"), callback_data="marche"),
             InlineKeyboardButton(b("btn_ia"), callback_data="ia_panel")],
            [InlineKeyboardButton(b("btn_brokers"), callback_data="brokers_menu")],
            [InlineKeyboardButton(b("btn_watchlist"), callback_data="watchlist"),
             InlineKeyboardButton(b("btn_portfolio"), callback_data="pf")],
            [InlineKeyboardButton(b("btn_perf"), callback_data="perf"),
             InlineKeyboardButton(b("btn_news"), callback_data="news_menu")],
            [InlineKeyboardButton(b("btn_settings"), callback_data="settings"),
             InlineKeyboardButton(b("btn_help"), callback_data="help")],
        ]
    )


def auto_menu_keyboard(active: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("📊 Bilan + graphique", callback_data="auto_bilan")]] if active else []
    if active:
        rows += [
            [InlineKeyboardButton("🛠️ Auto-régler", callback_data="auto_tune"),
             InlineKeyboardButton("🎚️ Agressivité", callback_data="agr_menu")],
            [InlineKeyboardButton("♻️ Reset 1000€", callback_data="auto_reset"),
             InlineKeyboardButton("⏸️ Pause", callback_data="auto_stop")],
        ]
    else:
        rows += [[InlineKeyboardButton("🤖 Démarrer avec 1000 €", callback_data="auto_start")]]
    rows.append([InlineKeyboardButton("🧠 Conseiller IA (modes)", callback_data="ia_panel"),
                 InlineKeyboardButton("🧪 Simuler d'abord", callback_data="simuler")])
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def ideas_keyboard(signals) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"👁️ Suivre {s.symbol}", callback_data=f"watchadd:{s.symbol}")]
            for s in signals[:5]]
    rows.append([InlineKeyboardButton("🔄 Rescanner", callback_data="idees"),
                 InlineKeyboardButton("⬅️ Retour", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def back_button(target: str = "menu", lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back", lang), callback_data=target)]])


def watchlist_keyboard(assets: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"🔎 {a}", callback_data=f"asset:{a}")] for a in assets]
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def asset_keyboard(raw: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📈 Graphique", callback_data=f"graph:{raw}"),
             InlineKeyboardButton("🧪 Backtest", callback_data=f"bt:{raw}")],
            [InlineKeyboardButton("📰 Actus", callback_data=f"news:{raw}"),
             InlineKeyboardButton("🗑️ Retirer", callback_data=f"unwatch:{raw}")],
            [InlineKeyboardButton("⬅️ Watchlist", callback_data="watchlist")],
        ]
    )


def settings_keyboard(s: dict, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    sens = s.get("sensibilite", "normale")
    digest_on = s.get("digest", 1)
    def mark(v):
        return "✅ " if v == sens else ""
    sens_labels = {"peu": {"fr": "Peu d'alertes", "en": "Few alerts"},
                   "normale": {"fr": "Normale", "en": "Normal"},
                   "beaucoup": {"fr": "Beaucoup", "en": "Many"}}
    digest_lbl = (("🔔 " + t("settings_digest", lang) + " : " + t("on", lang)) if digest_on
                  else ("🔕 " + t("settings_digest", lang) + " : " + t("off", lang)))
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{mark('peu')}" + sens_labels['peu'][lang], callback_data="set:sensibilite:peu")],
            [InlineKeyboardButton(f"{mark('normale')}" + sens_labels['normale'][lang], callback_data="set:sensibilite:normale")],
            [InlineKeyboardButton(f"{mark('beaucoup')}" + sens_labels['beaucoup'][lang], callback_data="set:sensibilite:beaucoup")],
            [InlineKeyboardButton(digest_lbl, callback_data="set:digest:toggle")],
            [InlineKeyboardButton(t("btn_language", lang), callback_data="set:langue:toggle")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="menu")],
        ]
    )


# --------------------------------------------------------------------------- #
#  Commandes
# --------------------------------------------------------------------------- #
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 900  # 15 minutes


async def _alert_admins(context, update, reason: str):
    """Prévient tous les utilisateurs authentifiés d'un évènement de sécurité."""
    db = context.application.bot_data["db"]
    u = update.effective_user
    who = f"{getattr(u, 'full_name', '')} (@{getattr(u, 'username', None) or '—'}, id {getattr(u, 'id', '?')})"
    for admin_id in db.all_authorized():
        try:
            await context.bot.send_message(
                admin_id, f"🚨 *Sécurité · Security*\n{reason}\n👤 {who}", parse_mode=MD)
        except Exception:  # noqa: BLE001
            pass


async def auth_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Protection par mot de passe + anti-brute-force + alerte d'intrusion."""
    import time
    pwd = get_secret("ACCESS_PASSWORD")
    if not pwd:
        return  # aucune protection configurée -> bot ouvert
    chat = update.effective_chat
    if chat is None:
        return
    db = _db(context)
    if db.is_authorized(chat.id):
        return  # déjà autorisé -> laisse passer

    attempts = context.application.bot_data.setdefault("auth_attempts", {})
    rec = attempts.setdefault(chat.id, {"count": 0, "until": 0.0, "alerted": False})
    now = time.time()
    u = update.effective_user
    who = f"{getattr(u, 'full_name', '')} (@{getattr(u, 'username', None) or '—'}, id {chat.id})"

    # Verrouillage actif
    if rec["until"] > now:
        if update.message:
            mins = int((rec["until"] - now) / 60) + 1
            await update.message.reply_text(
                f"⛔ Trop de tentatives. Réessaie dans {mins} min · Too many attempts, retry in {mins} min.")
        raise ApplicationHandlerStop

    text = (update.message.text or "").strip() if update.message else ""

    # Confidentialité : on supprime tout de suite le message contenant le mot de passe tapé
    if text and update.message:
        try:
            await update.message.delete()
        except Exception:  # noqa: BLE001
            pass

    # Bon mot de passe
    if text and text == pwd:
        db.authorize(chat.id)
        db.log_event(chat.id, "auth_ok", who)
        attempts.pop(chat.id, None)
        await _alert_admins(context, update, "✅ Nouvel accès autorisé · New authorized access")
        await context.bot.send_message(
            chat.id, "✅ *Accès autorisé · Access granted.*\nTape /start · Type /start.", parse_mode=MD)
        raise ApplicationHandlerStop

    # Tentative échouée (texte non vide = vraie tentative)
    if text:
        rec["count"] += 1
        db.log_event(chat.id, "auth_fail", f"{who} (tentative {rec['count']})")
        if rec["count"] >= MAX_ATTEMPTS:
            rec["until"] = now + LOCKOUT_SECONDS
            db.log_event(chat.id, "lockout", who)
            await _alert_admins(context, update,
                                f"🔒 {rec['count']} échecs de mot de passe → verrouillé 15 min · locked")
            await context.bot.send_message(
                chat.id, "⛔ Trop de tentatives. Verrouillé 15 min · Locked 15 min.")
            raise ApplicationHandlerStop

    # Première interaction d'un inconnu : on alerte les admins une fois
    if not rec["alerted"]:
        rec["alerted"] = True
        await _alert_admins(context, update, "🔐 Tentative de connexion · Connection attempt")

    if update.message:
        await context.bot.send_message(
            chat.id, "🔒 *Bot protégé · Protected bot*\n\nEntre le mot de passe · Enter the password:",
            parse_mode=MD)
    elif update.callback_query:
        await update.callback_query.answer(
            "🔒 Entre le mot de passe d'abord · Enter the password first", show_alert=True)
    raise ApplicationHandlerStop


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = _db(context)
    # première rencontre : on déduit la langue depuis l'app Telegram de l'utilisateur
    if not db.has_settings(chat_id):
        lang = normalize_lang(getattr(update.effective_user, "language_code", None))
        db.set_setting(chat_id, "langue", lang)
    lang = _lang(context, chat_id)
    await update.message.reply_text(t("welcome", lang), parse_mode=MD, reply_markup=main_menu(lang))


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context, update.effective_chat.id)
    await update.message.reply_text(t("menu_title", lang), parse_mode=MD, reply_markup=main_menu(lang))


async def langue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Choisir la langue / choose the language."""
    chat_id = update.effective_chat.id
    if context.args and context.args[0].lower()[:2] in ("fr", "en"):
        newlang = context.args[0].lower()[:2]
    else:
        newlang = "en" if _lang(context, chat_id) == "fr" else "fr"
    _db(context).set_setting(chat_id, "langue", newlang)
    await update.message.reply_text(t("lang_changed", newlang), parse_mode=MD,
                                    reply_markup=main_menu(newlang))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context, update.effective_chat.id)
    await update.message.reply_text(HELP_EN if lang == "en" else HELP, parse_mode=MD)


async def prix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /prix AAPL")
    q = await asyncio.to_thread(_svc(context).quote, context.args[0])
    if q is None:
        return await update.message.reply_text("❌ Donnée indisponible pour cet actif.")
    await update.message.reply_text(quote_line(q), parse_mode=MD)


def _analysis_extras(svc, raw: str) -> str:
    """Tendance agrégée + consensus de l'équipe, en 2 lignes (grâce au cache, quasi gratuit)."""
    lines = []
    try:
        tr = svc.trend(raw, with_news=False)
        if tr:
            lines.append(f"{tr.emoji} Tendance agrégée : *{tr.label}* ({tr.score:+.0f}/100)")
    except Exception:  # noqa: BLE001
        pass
    try:
        votes = svc.team_votes(raw)
        if votes:
            pour = sum(1 for v in votes.values() if v)
            lines.append(f"👥 Équipe : *{pour}/{len(votes)}* achèteraient (/equipe {raw.split(':')[-1]})")
    except Exception:  # noqa: BLE001
        pass
    return ("\n" + "\n".join(lines)) if lines else ""


async def analyse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /analyse AAPL")
    msg = await update.message.reply_text("⏳ Analyse en cours…")
    svc = _svc(context)
    a = await asyncio.to_thread(svc.analyze, context.args[0])
    extras = await asyncio.to_thread(_analysis_extras, svc, a.asset.raw)
    await msg.edit_text(analysis_full(a) + extras, parse_mode=MD,
                        reply_markup=asset_keyboard(a.asset.raw))


async def actu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /actu AAPL")
    raw = Asset.parse(context.args[0]).raw
    msg = await update.message.reply_text("⏳ Recherche d'actus…")
    items = await asyncio.to_thread(get_news, raw, 5)
    await msg.edit_text(news_block(raw, items), parse_mode=MD,
                        disable_web_page_preview=True)


CLASSES = {"actions": "STOCK", "action": "STOCK", "crypto": "CRYPTO", "cryptos": "CRYPTO",
           "devises": "FX", "devise": "FX", "fx": "FX", "matieres": "COMMO",
           "matières": "COMMO", "commo": "COMMO", "indices": "INDEX", "indice": "INDEX"}


async def idees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    klass = CLASSES.get(context.args[0].lower()) if context.args else None
    msg = await update.message.reply_text("🔎 Je scanne le marché à la recherche de pistes…")
    signals = await _scan(context, klass)
    await msg.edit_text(ideas_block(signals), parse_mode=MD,
                        reply_markup=ideas_keyboard(signals))


async def _scan(context, klass: str | None = None):
    universe = _universe()
    if klass:
        universe = [u for u in universe if u.startswith(f"{klass}:")]
    return await asyncio.to_thread(_svc(context).scan, universe, 5)


async def backtest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /backtest AAPL")
    raw = Asset.parse(context.args[0]).raw
    msg = await update.message.reply_text("🧪 Backtest en cours…")
    r = await asyncio.to_thread(_svc(context).backtest, raw)
    await msg.edit_text(backtest_block(r), parse_mode=MD)


async def graph_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /graph AAPL")
    raw = Asset.parse(context.args[0]).raw
    await _send_chart(update.effective_chat.id, context, raw)


async def movers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🚀 Recherche des plus forts mouvements…")
    m = await asyncio.to_thread(_svc(context).movers, _universe())
    await msg.edit_text(movers_block(m), parse_mode=MD)


async def tendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /tendance AAPL")
    raw = Asset.parse(context.args[0]).raw
    msg = await update.message.reply_text("📊 Agrégation des sources…")
    t = await asyncio.to_thread(_svc(context).trend, raw)
    await msg.edit_text(trend_block(t), parse_mode=MD)


def _regime_line(svc) -> str:
    pc = CONFIG.get("paper", {})
    if not pc.get("regime_filter"):
        return ""
    from ..regime import market_ok_now
    mkt = svc.history(pc.get("regime_symbol", "INDEX:^GSPC"), period="1y")
    ok = market_ok_now(mkt) if mkt is not None else True
    return ("\n\n🟢 *Régime favorable* : le bot autonome peut acheter."
            if ok else
            "\n\n🔴 *Régime défavorable* : le bot autonome n'ouvre plus de position (S&P sous sa MM200).")


async def marche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🌍 Analyse de la tendance générale du marché…")
    svc = _svc(context)
    m = await asyncio.to_thread(svc.market_trend, _universe())
    line = await asyncio.to_thread(_regime_line, svc)
    await msg.edit_text(market_block(m) + line, parse_mode=MD)


async def alpaca_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vérifie la connexion au compte Alpaca (paper-trading réel via API)."""
    msg = await update.message.reply_text("🦙 Connexion à Alpaca…")

    def _fetch():
        from ..brokers import AlpacaBroker
        b = AlpacaBroker()
        return b.get_account(), b.get_positions()

    try:
        acc, pos = await asyncio.to_thread(_fetch)
    except Exception as e:  # noqa: BLE001
        from ..formatting import esc_md
        return await msg.edit_text(
            "❌ *Alpaca non connecté.*\n"
            f"_{esc_md(str(e)[:200])}_\n\n"
            "Pour l'activer : crée un compte gratuit sur *alpaca.markets*, génère des clés "
            "*paper trading*, et ajoute dans `.env` :\n"
            "`ALPACA_API_KEY_ID=...`\n`ALPACA_API_SECRET=...`",
            parse_mode=MD)
    lines = [f"🦙 *Alpaca* — compte {acc['status']}",
             f"💵 Cash : {acc['cash']:.2f} {acc['currency']}",
             f"📊 Équity : *{acc['equity']:.2f} {acc['currency']}*", ""]
    if pos:
        lines.append("*Positions*")
        for p in pos:
            lines.append(f"• {p['symbol']} : {p['qty']:g} ({p['unrealized_plpc']:+.1f}%)")
    else:
        lines.append("Aucune position ouverte.")
    await msg.edit_text("\n".join(lines), parse_mode=MD,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                            "🤖 Trading autonome sur Alpaca", callback_data="alpaca_panel")]]))


async def equipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /equipe AAPL")
    raw = Asset.parse(context.args[0]).raw
    msg = await update.message.reply_text("👥 Consultation de l'équipe…")
    votes = await asyncio.to_thread(_svc(context).team_votes, raw)
    await msg.edit_text(team_block(raw, votes), parse_mode=MD)


async def maitres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from ..formatting import masters_block
    await update.message.reply_text(masters_block(), parse_mode=MD)


async def apercu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Briefing complet du marché en un coup d'œil."""
    from ..formatting import briefing_block
    msg = await update.message.reply_text("📊 Je prépare ton briefing complet…")
    svc = _svc(context)
    brief = await asyncio.to_thread(svc.briefing, _universe())
    rc = await asyncio.to_thread(svc.risk_climate)
    season, _, _ = await asyncio.to_thread(svc.season)
    await msg.edit_text(briefing_block(brief, rc, season), parse_mode=MD)


# Clés réglables depuis Telegram : nom -> (libellé, est_secret)
CONFIG_KEYS = {
    "ACCESS_PASSWORD": ("Mot de passe du bot · Bot password", True),
    "ALPACA_API_KEY_ID": ("Alpaca key id", True),
    "ALPACA_API_SECRET": ("Alpaca secret", True),
    "EXCHANGE_NAME": ("Échange · Exchange (ex: binance)", False),
    "EXCHANGE_API_KEY": ("Exchange API key", True),
    "EXCHANGE_API_SECRET": ("Exchange API secret", True),
    "ANTHROPIC_API_KEY": ("Anthropic key (IA actus)", True),
    "OPENAI_API_KEY": ("OpenAI key (conseiller IA)", True),
    "OPENAI_MODEL": ("Modèle OpenAI (ex: gpt-5.4-mini)", False),
    "AI_MAX_TOKENS": ("Plafond tokens sortie IA", False),
    "TR_PHONE": ("Trade Republic — téléphone (+33…)", True),
    "TR_PIN": ("Trade Republic — code PIN", True),
}


async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Voir et régler la configuration (clés API…) directement depuis Telegram."""
    db = _db(context)
    cfg = db.all_config()
    lines = ["🔧 *Configuration*  (réglable ici · set from here)", ""]
    for key, (label, secret) in CONFIG_KEYS.items():
        val = cfg.get(key)
        if val:
            shown = "•••• défini · set" if secret else f"`{val}`"
        else:
            shown = "_(vide · not set)_"
        lines.append(f"• *{label}*\n  `{key}` → {shown}")
    lines.append(
        "\n📝 *Régler · Set* : `/set CLE valeur`\n"
        "Ex : `/set EXCHANGE_NAME binance`\n"
        "🗑️ *Effacer · Clear* : `/del CLE`\n\n"
        "_🔒 Pour les secrets, ton message est supprimé automatiquement. "
        "Secrets are auto-deleted from the chat._")
    await update.message.reply_text("\n".join(lines), parse_mode=MD)


async def set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage : /set CLE valeur · /set KEY value")
    key = context.args[0].upper()
    value = " ".join(context.args[1:])
    if key not in CONFIG_KEYS:
        keys = ", ".join(CONFIG_KEYS)
        return await update.message.reply_text(f"Clé inconnue · Unknown key.\nClés · keys : {keys}")
    _db(context).set_config(key, value)
    label, secret = CONFIG_KEYS[key]
    if secret:
        try:
            await update.message.delete()  # retire le secret du chat
        except Exception:  # noqa: BLE001
            pass
        await context.bot.send_message(update.effective_chat.id,
                                       f"✅ *{label}* enregistré (et message supprimé) · saved.",
                                       parse_mode=MD)
    else:
        await update.message.reply_text(f"✅ *{label}* = `{value}`", parse_mode=MD)


async def del_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage : /del CLE · /del KEY")
    key = context.args[0].upper()
    if key not in CONFIG_KEYS:
        return await update.message.reply_text("Clé inconnue · Unknown key.")
    _db(context).del_config(key)
    await update.message.reply_text(f"🗑️ `{key}` effacé · cleared.", parse_mode=MD)


# --------------------------------------------------------------------------- #
#  Conseiller IA (OpenAI) — facultatif, 1 requête/jour max
# --------------------------------------------------------------------------- #
def _ia_mode_live(db) -> str:
    """Mode trading : 'ia' si le conseiller participe, sinon 'solo'."""
    return "ia" if db.get_config("AI_ENABLED") == "1" else "solo"


def _ia_mode_sim(db) -> str:
    return "ia" if db.get_config("AI_SIM_ENABLED") == "1" else "solo"


def _ia_keyboard(db) -> InlineKeyboardMarkup:
    live = _ia_mode_live(db)
    simm = _ia_mode_sim(db)
    def mark(cur, val, label):
        return ("✅ " if cur == val else "") + label
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(mark(live, "solo", "⚙️ Autonome seul"), callback_data="ia:live:solo"),
         InlineKeyboardButton(mark(live, "ia", "🧠 Autonome + IA"), callback_data="ia:live:ia")],
        [InlineKeyboardButton(mark(simm, "solo", "⚙️ Simulation seule"), callback_data="ia:sim:solo"),
         InlineKeyboardButton(mark(simm, "ia", "🧠 Simulation + IA"), callback_data="ia:sim:ia")],
        [InlineKeyboardButton("💬 Demander un avis maintenant", callback_data="ia:ask")],
        [InlineKeyboardButton("⬅️ Retour", callback_data="menu")],
    ])


def _ia_status_text(db) -> str:
    from .. import ai_advisor as ai
    ok = ai.is_configured()
    quota = "✅ disponible aujourd'hui" if ai.can_call(db) else "⏳ déjà utilisée aujourd'hui (1/jour)"
    model = (db.get_config("OPENAI_MODEL") or ai.DEFAULT_MODEL)
    live = _ia_mode_live(db)
    simm = _ia_mode_sim(db)
    live_txt = ("🧠 *Autonome + IA* — le bot trade sa stratégie ET applique chaque jour les "
                "ordres du conseiller IA (12h45 New York, en pleine séance)"
                if live == "ia" else
                "⚙️ *Autonome seul* — stratégie du bot uniquement, AUCUN appel à OpenAI")
    sim_txt = ("🧠 *Simulation + IA* — /simuler ajoute l'avis du conseiller sur les résultats"
               if simm == "ia" else
               "⚙️ *Simulation seule* — /simuler sans appel à OpenAI")
    return (
        "🧠 *Conseiller IA (OpenAI)* — facultatif\n\n"
        f"Clé : {'✅' if ok else '❌ (/set OPENAI_API_KEY ta-clé)'} · Modèle : `{model}`\n"
        f"Requête du jour : {quota}\n\n"
        f"🤖 Mode trading : {live_txt}\n\n"
        f"🧪 Mode simulateur : {sim_txt}\n\n"
        "Limites : 1 requête/jour · pas d'appel sans position ni bourse fermée.\n"
        "_⚠️ Avis d'IA, pas un conseil financier. Trading 100% fictif._"
    )


async def ia_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db(context)
    await update.message.reply_text(_ia_status_text(db), parse_mode=MD,
                                    reply_markup=_ia_keyboard(db))


async def _ia_ask_and_send(chat_id, context, source: str = "live"):
    """Construit le contexte, appelle OpenAI (si quota/positions OK) et envoie l'avis."""
    from .. import ai_advisor as ai
    from ..formatting import esc_md
    db = _db(context)
    svc = _svc(context)
    if not ai.is_configured():
        return await context.bot.send_message(
            chat_id, "❌ Clé OpenAI absente. Configure-la : `/set OPENAI_API_KEY ta-clé`", parse_mode=MD)
    if not ai.can_call(db):
        return await context.bot.send_message(
            chat_id, "⏳ La requête IA du jour a déjà été utilisée (limite : 1/jour).")
    positions = db.paper_positions(chat_id)
    if source == "live" and not positions:
        return await context.bot.send_message(
            chat_id, "📭 Aucune position en cours → pas de requête envoyée (économie du quota).")
    msg = await context.bot.send_message(chat_id, "🧠 J'agrège le contexte et j'interroge l'IA…")
    try:
        ctx_text = await asyncio.to_thread(ai.build_context, svc, db, chat_id, _universe())
        raw_advice = await asyncio.to_thread(ai.ask, ctx_text)
        ai.record_call(db)
        db.log_event(chat_id, "ai_call", f"source={source}")
        advice, orders = ai.parse_orders(raw_advice)
        await msg.edit_text(f"🧠 *Avis du conseiller IA*\n\n{esc_md(advice)[:3700]}", parse_mode=MD)

        # 🤖 Exécution automatique des ordres IA (si activée). Cible = Alpaca si branché,
        # sinon le compte fictif interne.
        if orders and db.get_config("AI_EXEC_ENABLED") == "1":
            alpaca_mode = db.get_config("ALPACA_AUTO")
            dev = _paper_cfg().get("devise", "EUR")
            if alpaca_mode in ("paper", "live"):
                # --- Exécution sur Alpaca (paper/réel) ---
                def _exec_alpaca():
                    from ..brokers.alpaca import AlpacaBroker
                    b = AlpacaBroker(mode=alpaca_mode)
                    return trader.execute_orders_alpaca(b, svc, orders, _paper_cfg())
                try:
                    executed = await asyncio.to_thread(_exec_alpaca)
                except Exception as e:  # noqa: BLE001
                    return await context.bot.send_message(
                        chat_id, f"❌ Exécution Alpaca impossible : {esc_md(str(e)[:150])}")
                tag_env = "PAPER" if alpaca_mode == "paper" else "RÉEL 💸"
                if executed:
                    for tr in executed:
                        ic = "🟢 ACHAT" if tr["side"] == "ACHAT" else "🔴 VENTE"
                        await context.bot.send_message(
                            chat_id, f"🦙 *Alpaca {tag_env}* — {ic} {tr['asset']} × {tr['quantity']:g}\n"
                                     "🧠 _ordre du conseiller IA_", parse_mode=MD)
                        db.log_event(chat_id, "ai_exec", f"alpaca-{alpaca_mode}: {tr['side']} {tr['asset']}")
                else:
                    await context.bot.send_message(
                        chat_id, "🤖 Ordres IA reçus mais rien d'exécutable sur Alpaca "
                                 "(actifs non-US, déjà détenus, ou ordres en attente).")
            else:
                # --- Exécution sur le compte fictif interne ---
                executed = await asyncio.to_thread(
                    trader.execute_orders, db, svc, chat_id, orders, _paper_cfg(), _universe())
                if executed:
                    for tr in executed:
                        tag = ("\n🔍 _découverte IA via les actus — ajoutée à ton univers de suivi_"
                               if "découverte" in tr.get("motif", "")
                               else "\n🧠 _ordre du conseiller IA_")
                        await context.bot.send_message(
                            chat_id,
                            trade_log(tr["side"], tr["asset"], tr["quantity"], tr["price"], tr["fee"],
                                      tr.get("pnl") if tr["side"] == "VENTE" else None, dev) + tag,
                            parse_mode=MD)
                        db.log_event(chat_id, "ai_exec", f"{tr['side']} {tr['asset']} ({tr.get('motif','')})")
                    acc2, equity, holdings = await asyncio.to_thread(trader.account_state, db, svc, chat_id)
                    invested = sum(h["value"] for h in holdings)
                    await context.bot.send_message(
                        chat_id, state_recap(acc2["cash"], invested, len(holdings), equity,
                                             acc2["capital"], dev), parse_mode=MD)
                else:
                    await context.bot.send_message(
                        chat_id, "🤖 Ordres IA reçus mais non exécutables (actif inconnu, cash ou "
                                 "limites) — aucun trade passé.")
        elif orders:
            noms = ", ".join(f"{o['action']} {o['asset']}" for o in orders)
            await context.bot.send_message(
                chat_id, f"💡 Ordres suggérés (exécution auto désactivée) : {noms}\n"
                         "_Active-la dans /ia pour que je les applique automatiquement._",
                parse_mode=MD)
    except Exception as e:  # noqa: BLE001
        await msg.edit_text(f"❌ Échec de l'appel IA : {esc_md(str(e)[:200])}")


async def ia_daily_job(context: ContextTypes.DEFAULT_TYPE):
    """Conseil IA quotidien automatique (si activé, configuré, quota dispo et positions).

    Économie de tokens : pas d'appel les jours de bourse fermée (week-end + fériés US).
    """
    from datetime import datetime as _dt
    from .. import ai_advisor as ai
    from ..seasonality import is_market_holiday
    db: Storage = context.application.bot_data["db"]
    if db.get_config("AI_ENABLED") != "1" or not ai.is_configured() or not ai.can_call(db):
        return
    today = _dt.now()
    if today.weekday() >= 5 or is_market_holiday():
        log.info("IA quotidienne : bourse fermée (week-end/férié), pas d'appel.")
        return
    for chat_id in db.paper_active_chats():
        if db.paper_positions(chat_id):
            await _ia_ask_and_send(chat_id, context, source="daily")
            break  # 1 requête/jour au total


async def securite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tableau de bord sécurité : accès autorisés + journal d'audit."""
    db = _db(context)
    protected = bool(get_secret("ACCESS_PASSWORD"))
    auth = db.all_authorized()
    lines = [
        "🛡️ *Sécurité · Security*", "",
        f"🔒 Protection mot de passe : {'✅ active' if protected else '❌ inactive'}",
        "🔐 Secrets chiffrés en base : ✅ (AES/Fernet)",
        f"👥 Accès autorisés · authorized : *{len(auth)}*", "",
        "📜 *Journal récent · Recent log*",
    ]
    icons = {"auth_ok": "✅", "auth_fail": "⚠️", "lockout": "🔒", "attempt": "🔐"}
    events = db.recent_audit(10)
    if events:
        for e in events:
            ts = e["ts"][5:16].replace("T", " ")
            lines.append(f"{icons.get(e['event'], '•')} {ts} — {e['detail'][:60]}")
    else:
        lines.append("_(aucun évènement · no events)_")
    lines.append("\n_/deconnexion pour révoquer ton accès · revoke your access._")
    await update.message.reply_text("\n".join(lines), parse_mode=MD)


async def deconnexion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Révoque l'accès de l'utilisateur (mot de passe redemandé ensuite)."""
    chat_id = update.effective_chat.id
    db = _db(context)
    db.deauthorize(chat_id)
    db.log_event(chat_id, "logout", "déconnexion volontaire")
    await update.message.reply_text(
        "🔓 *Déconnecté · Logged out.*\nLe mot de passe sera redemandé · Password will be required again.",
        parse_mode=MD)


async def traderepublic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lit le compte Trade Republic réel (cash, positions, valeur). Lecture seule."""
    from ..formatting import esc_md
    chat_id = update.effective_chat.id
    phone = get_secret("TR_PHONE")
    pin = get_secret("TR_PIN")
    if not phone or not pin:
        return await update.message.reply_text(
            "🏦 *Trade Republic* (lecture seule · argent réel)\n\n"
            "Configure d'abord tes accès (stockés chiffrés) :\n"
            "`/set TR_PHONE +33...`\n`/set TR_PIN ****`\n"
            "Puis relance /traderepublic — je t'enverrai un code 2FA à confirmer.\n\n"
            "_Le bot LIT ton compte et te conseille ; il ne passe jamais d'ordre "
            "(tu valides dans l'app TR)._", parse_mode=MD)
    msg = await update.message.reply_text("🏦 Connexion à Trade Republic…")

    def _connect_or_2fa():
        from ..brokers.traderepublic import TradeRepublicBroker
        b = TradeRepublicBroker()
        if b.resume():                      # session déjà valide (cookies)
            return ("ok", b)
        api, countdown = TradeRepublicBroker.begin_login(phone, pin)  # envoie le 2FA
        return ("2fa", api, countdown)

    try:
        res = await asyncio.to_thread(_connect_or_2fa)
    except Exception as e:  # noqa: BLE001
        return await msg.edit_text(f"❌ Connexion TR impossible : {esc_md(str(e)[:200])}")

    if res[0] == "2fa":
        context.application.bot_data.setdefault("tr_pending", {})[chat_id] = (res[1], res[2])
        return await msg.edit_text(
            "🔐 Trade Republic t'a envoyé un *code 2FA* (dans l'app / par SMS).\n"
            "Renvoie-le-moi : `/tr_code 1234`", parse_mode=MD)
    await _tr_show_account(msg, res[1])


async def tr_code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from ..formatting import esc_md
    chat_id = update.effective_chat.id
    pending = context.application.bot_data.get("tr_pending", {}).get(chat_id)
    if not pending or not context.args:
        return await update.message.reply_text("Usage : /tr_code 1234 (après /traderepublic)")
    api, countdown = pending
    code = context.args[0].strip()
    try:
        await update.message.delete()       # le code 2FA ne reste pas dans le chat
    except Exception:  # noqa: BLE001
        pass
    msg = await context.bot.send_message(chat_id, "🔐 Validation du code…")

    def _finish():
        from ..brokers.traderepublic import TradeRepublicBroker
        return TradeRepublicBroker.finish_login(api, countdown, code)

    try:
        b = await asyncio.to_thread(_finish)
    except Exception as e:  # noqa: BLE001
        return await msg.edit_text(f"❌ Code refusé / erreur : {esc_md(str(e)[:200])}")
    context.application.bot_data.get("tr_pending", {}).pop(chat_id, None)
    await _tr_show_account(msg, b)


async def _tr_show_account(msg, broker):
    from ..formatting import esc_md
    try:
        acc = await asyncio.to_thread(broker.get_account)
        pos = await asyncio.to_thread(broker.get_positions)
    except Exception as e:  # noqa: BLE001
        return await msg.edit_text(f"❌ Lecture du compte échouée : {esc_md(str(e)[:200])}")
    lines = [f"🏦 *{acc['status']}*",
             f"💵 Cash : *{acc['cash']:.2f} {acc['currency']}*",
             f"📦 Investi : {acc.get('invested', 0):.2f} {acc['currency']}",
             f"📊 Total : *{acc['equity']:.2f} {acc['currency']}*"]
    if pos:
        lines.append("\n*Positions (ISIN · quantité · prix de revient)*")
        for p in pos:
            lines.append(f"• `{p['symbol']}` — {p['qty']:g} @ {p['avg_entry_price']:.2f}")
    else:
        lines.append("\nAucune position lue (ou compte vide).")
    lines.append("\n_Lecture seule — tu passes les ordres dans l'app TR._")
    await msg.edit_text("\n".join(lines), parse_mode=MD)


def _brokers_hub_text(db) -> str:
    alp_ok = bool(get_secret("ALPACA_API_KEY_ID"))
    alp_mode = db.get_config("ALPACA_AUTO") or "off"
    tr_ok = bool(get_secret("TR_PHONE"))
    ex_name = get_secret("EXCHANGE_NAME")
    def st(ok):
        return "✅ configuré" if ok else "❌ non configuré"
    alp_line = st(alp_ok)
    if alp_ok and alp_mode in ("paper", "live"):
        alp_line += f" · auto *{ 'PAPER' if alp_mode=='paper' else 'RÉEL' }*"
    return (
        "🔌 *Brokers* — connecte le bot à un courtier\n\n"
        f"🦙 *Alpaca* (actions US + crypto) : {alp_line}\n"
        f"🏦 *Trade Republic* (lecture seule) : {st(tr_ok)}\n"
        f"💱 *Échange crypto* (ccxt) : {('✅ ' + ex_name) if ex_name else '❌ non configuré'}\n\n"
        "_🦙 Alpaca = trading autonome réel (paper gratuit). 🏦 TR = lecture seule "
        "(2FA par ordre). 💱 Échanges crypto = auto possible (clés API)._"
    )


def _brokers_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🦙 Alpaca (auto + bilan)", callback_data="alpaca_panel")],
        [InlineKeyboardButton("🏦 Trade Republic (lecture)", callback_data="brk:tr")],
        [InlineKeyboardButton("💱 Échange crypto (Binance…)", callback_data="brk:ccxt")],
        [InlineKeyboardButton("⬅️ Retour", callback_data="menu")],
    ])


async def brokers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(_brokers_hub_text(_db(context)), parse_mode=MD,
                                    reply_markup=_brokers_hub_keyboard())


def _alpaca_auto_keyboard(db) -> InlineKeyboardMarkup:
    mode = db.get_config("ALPACA_AUTO") or "off"
    def mk(v, label):
        return ("✅ " if mode == v else "") + label
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Mon bilan Alpaca (gains + graphique)", callback_data="alp:bilan")],
        [InlineKeyboardButton(mk("off", "⚪ Désactivé"), callback_data="alp:off")],
        [InlineKeyboardButton(mk("paper", "🧪 Auto sur Alpaca PAPER (gratuit, sans risque)"),
                              callback_data="alp:paper")],
        [InlineKeyboardButton(mk("live", "💸 Auto sur Alpaca RÉEL (vrai argent)"),
                              callback_data="alp:live")],
        [InlineKeyboardButton("🔌 Tester la connexion", callback_data="alp:test")],
        [InlineKeyboardButton("⬅️ Brokers", callback_data="brokers_menu")],
    ])


async def _alpaca_bilan(chat_id, context):
    """Bilan du compte Alpaca : cash, positions, gains + courbe d'équity (comme le simulateur)."""
    import pandas as pd

    from ..formatting import esc_md
    db = _db(context)
    mode = db.get_config("ALPACA_AUTO") or "paper"

    def _fetch():
        from ..brokers.alpaca import AlpacaBroker
        b = AlpacaBroker(mode=mode if mode in ("paper", "live") else "paper")
        return b.get_account(), b.get_positions(), b.portfolio_history()

    try:
        acc, pos, ph = await asyncio.to_thread(_fetch)
    except Exception as e:  # noqa: BLE001
        return await context.bot.send_message(
            chat_id, f"❌ Alpaca non connecté : {esc_md(str(e)[:150])}\n"
                     "Configure `/set ALPACA_API_KEY_ID …` et `/set ALPACA_API_SECRET …`.",
            parse_mode=MD)
    cur = acc.get("currency", "USD")
    ts = ph.get("timestamp", []) or []
    eq = ph.get("equity", []) or []
    pairs = [(t, e) for t, e in zip(ts, eq, strict=False) if e]
    base = ph.get("base_value") or (pairs[0][1] if pairs else acc["equity"])
    pnl = acc["equity"] - base
    pct = (pnl / base * 100) if base else 0
    emoji = "🟢" if pnl >= 0 else "🔴"
    env = "PAPER (fictif)" if mode != "live" else "RÉEL"
    lines = [f"{emoji} *Bilan Alpaca {env}*",
             f"📊 Valeur : *{acc['equity']:.2f} {cur}*  (départ {base:.0f})",
             f"💰 Gain/perte : *{pnl:+.2f} {cur}* ({pct:+.1f}%)",
             f"💵 Cash : {acc['cash']:.2f} {cur}"]
    if pos:
        lines.append("\n📦 *Positions*")
        for p in pos:
            lines.append(f"• {p['symbol']} : {p['qty']:g} ({p['unrealized_plpc']:+.1f}%)")
    else:
        lines.append("\n📦 Aucune position (ordres en attente si marché fermé).")
    await context.bot.send_message(chat_id, "\n".join(lines), parse_mode=MD)

    # Graphique d'équity (même rendu que le simulateur)
    if len(pairs) >= 2:
        series = pd.Series([e for _, e in pairs],
                           index=pd.to_datetime([t for t, _ in pairs], unit="s"))
        path = await asyncio.to_thread(make_equity_chart, series, base,
                                       f"Mon compte Alpaca ({env})", f"alpaca_{chat_id}")
        if path:
            with open(path, "rb") as f:
                await context.bot.send_photo(chat_id, photo=f,
                                             caption="📈 Évolution de ton capital Alpaca")


def _alpaca_auto_text(db) -> str:
    mode = db.get_config("ALPACA_AUTO") or "off"
    from .. import ai_advisor  # noqa: F401 (garde l'ordre d'import cohérent)
    etat = {"off": "⚪ désactivé", "paper": "🧪 PAPER (faux argent, gratuit)",
            "live": "💸 RÉEL (vrai argent)"}[mode]
    return (
        "🦙 *Trading autonome sur Alpaca*\n\n"
        f"État actuel : *{etat}*\n\n"
        "Le bot applique sa stratégie *directement sur ton compte Alpaca* (il passe les "
        "ordres seul, sans 2FA par ordre) toutes les heures.\n\n"
        "1️⃣ Crée un compte gratuit sur *alpaca.markets*\n"
        "2️⃣ Clés : `/set ALPACA_API_KEY_ID …` et `/set ALPACA_API_SECRET …`\n"
        "3️⃣ Choisis *PAPER* d'abord (faux argent) pour valider sans risque.\n\n"
        "_💸 Le mode RÉEL engage du vrai argent — la stratégie n'est validée qu'en backtest. "
        "À n'activer qu'en pleine connaissance de cause._"
    )


async def alpaca_auto_job(context: ContextTypes.DEFAULT_TYPE):
    """Cycle de trading autonome sur Alpaca (si activé paper/live)."""
    import json as _json
    db: Storage = context.application.bot_data["db"]
    svc: MarketService = context.application.bot_data["svc"]
    mode = db.get_config("ALPACA_AUTO")
    if mode not in ("paper", "live"):
        return
    try:
        from ..brokers.alpaca import AlpacaBroker
        broker = AlpacaBroker(mode=mode)
    except Exception as e:  # noqa: BLE001
        log.warning("Alpaca auto : connexion impossible (%s)", e)
        return
    # paramètres stratégie (auto-tunés) du 1er compte, sinon défauts
    params = {}
    for cid in db.paper_active_chats():
        acc = db.paper_get(cid)
        if acc and acc.get("params"):
            params = _json.loads(acc["params"])
            break
    try:
        executed = await asyncio.to_thread(
            trader.run_broker_cycle, broker, svc, _universe(), _paper_cfg(), params)
    except Exception as e:  # noqa: BLE001
        log.warning("Alpaca auto cycle : %s", e)
        return
    if not executed:
        return
    tag = "PAPER" if mode == "paper" else "RÉEL 💸"
    for cid in db.all_authorized() or db.paper_active_chats():
        for tr in executed:
            ic = "🟢 ACHAT" if tr["side"] == "ACHAT" else "🔴 VENTE"
            try:
                await context.bot.send_message(
                    cid, f"🦙 *Alpaca {tag}* — {ic} {tr['asset']} × {tr['quantity']:g}",
                    parse_mode=MD)
            except Exception:  # noqa: BLE001
                pass
        db.log_event(cid, "alpaca_exec", f"{mode}: {len(executed)} ordres")
        break  # une seule notification (compte unique)


async def broker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vérifie la connexion à un échange crypto (Binance, Kraken… via ccxt)."""
    msg = await update.message.reply_text("🔌 Connexion à l'échange · Connecting to exchange…")

    def _fetch():
        from ..brokers import CCXTBroker
        b = CCXTBroker()
        return b.get_account(), b.get_positions()

    try:
        acc, pos = await asyncio.to_thread(_fetch)
    except Exception as e:  # noqa: BLE001
        from ..formatting import esc_md
        return await msg.edit_text(
            "❌ *Échange non connecté · Exchange not connected.*\n"
            f"_{esc_md(str(e)[:200])}_\n\n"
            "Configure dans `.env` · Set in `.env`:\n"
            "`EXCHANGE_NAME=binance`\n`EXCHANGE_API_KEY=...`\n`EXCHANGE_API_SECRET=...`\n\n"
            "_Astuce : utilise le testnet de l'échange pour t'entraîner sans risque._",
            parse_mode=MD)
    lines = [f"🔌 *{acc['status']}*", f"💵 Cash : {acc['cash']:.2f} {acc['currency']}"]
    if pos:
        lines.append("\n*Avoirs · Holdings*")
        for p in pos:
            lines.append(f"• {p['symbol']} : {p['qty']:g}")
    else:
        lines.append("Aucun avoir · No holdings.")
    await msg.edit_text("\n".join(lines), parse_mode=MD)


async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envoie le fichier de configuration (sauvegarde / partage)."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent
    path = root / "config.yaml"
    if not path.exists():
        path = root / "config.example.yaml"
    with open(path, "rb") as f:
        await context.bot.send_document(
            update.effective_chat.id, document=f, filename="owltrader-config.yaml",
            caption="📤 Ta configuration · Your configuration.\n"
                    "Renvoie-moi ce fichier (modifié) pour l'importer · Send it back to import it.")


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Import d'un fichier de configuration envoyé dans le chat."""
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith((".yaml", ".yml")):
        return
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent
    try:
        f = await doc.get_file()
        await f.download_to_drive(str(root / "config.yaml"))
        await update.message.reply_text(
            "✅ *Configuration importée · Configuration imported.*\n"
            "Elle sera appliquée au prochain redémarrage · Applied on next restart.",
            parse_mode=MD)
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(f"❌ Import échoué · Import failed: {str(e)[:120]}")


async def sauvegarde_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Déclenche une sauvegarde locale de la base et confirme."""
    dest = await asyncio.to_thread(_db(context).backup)
    await update.message.reply_text(
        f"💾 *Sauvegarde effectuée · Backup done*\n`{dest}`\n"
        "_(rotation : 7 dernières · keeps last 7)_", parse_mode=MD)


async def sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Transparence : quelles sources de données alimentent le bot."""
    router = _svc(context).router
    noms = ", ".join(p.name for p in router.providers)
    await update.message.reply_text(
        "📡 *Sources de données (toutes gratuites)*\n\n"
        f"Actives : *{noms}*\n\n"
        "• *yfinance* (Yahoo) — actions, indices, matières, devises, crypto\n"
        "• *CoinGecko* — crypto, cours très frais 24/7\n"
        "• *Stooq* — repli\n\n"
        "🔄 Pour chaque cours, je récupère *toutes* les sources en parallèle et je garde "
        "*la plus fraîche*. Si l'une tombe, les autres prennent le relais — jamais de trou.",
        parse_mode=MD)


async def macro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Régime macro cross-actifs (risk-on / risk-off) via les rapports d'ETF."""
    from ..macro import macro_regime
    msg = await update.message.reply_text("📐 Analyse cross-actifs (risk-on/off)…")
    m = await asyncio.to_thread(macro_regime, _svc(context))
    if m is None:
        return await msg.edit_text("📐 Régime macro indisponible.")
    lines = [f"{m.emoji} *Régime macro : {m.label}*", f"Score risk-on/off : *{m.score:+.0f}/100*", ""]
    for label, sens, chg in m.components:
        lines.append(f"{'🟢' if sens == 'risk-on' else '🔴'} {label} : *{sens}* ({chg:+.1f}%)")
    lines.append("\n_Rapports d'ETF (small vs large, crédit, cyclique/défensif…) — "
                 "révèlent l'appétit pour le risque. ⚠️ Info de contexte, pas un signal._")
    await msg.edit_text("\n".join(lines), parse_mode=MD)


async def saison(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from ..formatting import season_block
    s, upcoming, nh = await asyncio.to_thread(_svc(context).season)
    await update.message.reply_text(season_block(s, upcoming, nh), parse_mode=MD)


async def risque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🌐 Évaluation du climat de risque (VIX + actus)…")
    rc = await asyncio.to_thread(_svc(context).risk_climate)
    lines = ["🌐 *Climat de risque macro / géopolitique*",
             f"Verdict : *{rc.label}*  (biais {rc.bias:+.2f})", "",
             f"📉 {rc.vix_note}",
             f"📰 Tension géopolitique dans l'actu : {rc.geo_score*100:.0f}%"]
    if rc.hot_headlines:
        lines.append("\n*Titres sensibles*")
        for h in rc.hot_headlines:
            safe = h.replace("*", " ").replace("_", " ").replace("[", " ")
            lines.append(f"• {safe}")
    lines.append("\n_ℹ️ Info de contexte. Le mode autonome gère déjà ce risque via le filtre de régime (S&P)._")
    await msg.edit_text("\n".join(lines), parse_mode=MD, disable_web_page_preview=True)


async def univers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Voir / modifier l'univers d'actifs scannés et tradés."""
    db = _db(context)
    db.seed_universe(CONFIG.get("univers_scan", []))
    args = context.args
    if args and args[0].lower() in ("add", "ajouter", "+"):
        if len(args) < 2:
            return await update.message.reply_text("Usage : /univers add BTC")
        a = Asset.parse(args[1])
        db.add_to_universe(a.raw)
        return await update.message.reply_text(f"✅ {a.raw} ajouté à l'univers.")
    if args and args[0].lower() in ("remove", "retirer", "-", "del"):
        if len(args) < 2:
            return await update.message.reply_text("Usage : /univers remove TSLA")
        a = Asset.parse(args[1])
        db.remove_from_universe(a.raw)
        return await update.message.reply_text(f"🗑️ {a.raw} retiré de l'univers.")
    u = db.get_universe()
    txt = (f"🌐 *Univers de trading* ({len(u)} actifs)\n" +
           "\n".join(f"• {x}" for x in u) +
           "\n\n_Ajouter : /univers add BTC_\n_Retirer : /univers remove TSLA_")
    await update.message.reply_text(txt, parse_mode=MD)


async def alerte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crée une alerte de prix : /alerte AAPL 200"""
    if len(context.args) < 2:
        return await update.message.reply_text("Usage : /alerte AAPL 200  (m'alerter quand AAPL franchit 200)")
    a = Asset.parse(context.args[0])
    try:
        target = float(context.args[1].replace(",", "."))
    except ValueError:
        return await update.message.reply_text("Prix invalide. Ex : /alerte AAPL 200")
    q = await asyncio.to_thread(_svc(context).quote, a.raw)
    if q is None:
        return await update.message.reply_text("❌ Prix actuel indisponible pour cet actif.")
    direction = "above" if target >= q.price else "below"
    _db(context).add_price_alert(update.effective_chat.id, a.raw, target, direction)
    arrow = "≥" if direction == "above" else "≤"
    await update.message.reply_text(
        f"🔔 Alerte créée : *{a.raw} {arrow} {target:g}*\n_(cours actuel : {q.price:g})_", parse_mode=MD)


async def alertes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    al = _db(context).get_price_alerts(update.effective_chat.id)
    if not al:
        return await update.message.reply_text("Aucune alerte de prix. Crée-en une : /alerte AAPL 200")
    rows = []
    lines = ["🔔 *Tes alertes de prix*"]
    for a in al:
        arrow = "≥" if a["direction"] == "above" else "≤"
        lines.append(f"• #{a['id']} {a['asset']} {arrow} {a['target']:g}")
        rows.append([InlineKeyboardButton(f"🗑️ Supprimer #{a['id']}", callback_data=f"delalert:{a['id']}")])
    await update.message.reply_text("\n".join(lines), parse_mode=MD,
                                    reply_markup=InlineKeyboardMarkup(rows))


async def agressivite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not _db(context).paper_get(chat_id):
        return await update.message.reply_text("Lance d'abord le mode autonome : /auto 1000")
    if context.args:
        name = context.args[0].lower()
        if name not in AGRESSIVITES:
            return await update.message.reply_text("Choix : prudent · normale · agressif")
        _db(context).paper_set_params(chat_id, json.dumps(profile(name)))
        return await update.message.reply_text(
            f"🎚️ Agressivité réglée sur *{name}*.\n⚙️ {fmt_params(profile(name))}", parse_mode=MD)
    await update.message.reply_text(
        "🎚️ *Agressivité* — choisis :", parse_mode=MD,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛡️ Prudent", callback_data="agr:prudent"),
             InlineKeyboardButton("⚖️ Normale", callback_data="agr:normale"),
             InlineKeyboardButton("🔥 Agressif", callback_data="agr:agressif")]]))


async def _send_chart(chat_id, context, raw: str):
    df = await asyncio.to_thread(_svc(context).history, raw)
    path = await asyncio.to_thread(make_chart, raw, df)
    if not path:
        return await context.bot.send_message(chat_id, "📈 Pas assez de données pour un graphique.")
    with open(path, "rb") as f:
        await context.bot.send_photo(chat_id, photo=f, caption=f"📈 {raw}")


# --------------------------------------------------------------------------- #
#  Mode autonome (paper-trading fictif)
# --------------------------------------------------------------------------- #
def _paper_cfg() -> dict:
    return CONFIG.get("paper", {})


_DB_REF = None  # référence partagée vers le stockage (pour _universe sans contexte)


def _universe() -> list[str]:
    """Univers de scan/trading : DB si personnalisé, sinon défaut config."""
    if _DB_REF is not None:
        u = _DB_REF.get_universe()
        if u:
            return u
    return _universe()


async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/auto [montant] — démarre (ou redémarre) la gestion autonome avec un capital fictif."""
    cfg = _paper_cfg()
    capital = cfg.get("capital", 1000)
    if context.args:
        try:
            capital = float(context.args[0].replace(",", "."))
        except ValueError:
            return await update.message.reply_text("Montant invalide. Ex : /auto 1000")
    chat_id = update.effective_chat.id
    _db(context).paper_open(chat_id, capital, cfg.get("devise", "EUR"))
    await update.message.reply_text(
        f"🤖 *Mode autonome activé* avec *{capital:.0f} {cfg.get('devise','EUR')}* fictifs.\n\n"
        "Je vais acheter/vendre tout seul selon ma stratégie (auto-ajustée), "
        "frais de courtage inclus, et te *logguer chaque action* ici.\n"
        "• /bilan — voir où j'en suis (+ graphique)\n"
        "• /reset — remettre les mises à zéro\n"
        "• /stopauto — mettre en pause\n\n"
        "_⏳ Premier tour de marché en cours…_",
        parse_mode=MD,
    )
    await _run_auto_cycle(chat_id, context, announce=True)
    await _send_bilan(chat_id, context)


async def reset_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reset [montant] — réinitialise les mises et efface toutes les actions."""
    cfg = _paper_cfg()
    acc = _db(context).paper_get(update.effective_chat.id)
    capital = acc["capital"] if acc else cfg.get("capital", 1000)
    if context.args:
        try:
            capital = float(context.args[0].replace(",", "."))
        except ValueError:
            return await update.message.reply_text("Montant invalide. Ex : /reset 1000")
    _db(context).paper_open(update.effective_chat.id, capital, cfg.get("devise", "EUR"))
    await update.message.reply_text(
        f"♻️ *Réinitialisé.* Capital remis à *{capital:.0f} {cfg.get('devise','EUR')}*, "
        "positions et historique effacés.", parse_mode=MD)


async def stop_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    acc = _db(context).paper_get(update.effective_chat.id)
    if not acc:
        return await update.message.reply_text("Aucun compte autonome. Lance /auto 1000")
    _db(context).paper_set_active(update.effective_chat.id, 0)
    await update.message.reply_text("⏸️ Mode autonome en pause. /auto pour relancer.")


async def bilan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_bilan(update.effective_chat.id, context)


async def simuler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = _paper_cfg()
    msg = await update.message.reply_text("🧪 Simulation historique en cours (2 ans)…")
    r = await asyncio.to_thread(
        _svc(context).simulate_portfolio, _universe(), cfg.get("capital", 1000),
        fee_pct=cfg.get("frais_pct", 0.2), fee_min=cfg.get("frais_min", 1.0),
        max_positions=cfg.get("max_positions", 5), alloc_pct=cfg.get("alloc_pct", 20),
        stop_loss_pct=cfg.get("stop_loss_pct", 0), max_dd_pause=cfg.get("max_dd_pause", 0),
        vol_target=cfg.get("vol_target", 0), rank_lookback=cfg.get("rank_lookback", 0),
        abs_mom_lookback=cfg.get("abs_mom_lookback", 0), abs_mom_min=cfg.get("abs_mom_min", 0),
    )
    await msg.edit_text(sim_block(r, cfg.get("devise", "EUR")), parse_mode=MD)
    if r is not None:
        path = await asyncio.to_thread(
            make_equity_chart, r.equity_curve, r.capital, "Simulation du mode autonome", "sim")
        if path:
            with open(path, "rb") as f:
                await context.bot.send_photo(update.effective_chat.id, photo=f,
                                             caption="📈 Évolution simulée du capital")
        await _ia_sim_comment(update.effective_chat.id, context, r)


async def _ia_sim_comment(chat_id, context, r):
    """Avis IA sur les résultats de simulation (si activé) — mêmes limites (1/jour)."""
    from .. import ai_advisor as ai
    from ..formatting import esc_md
    db = _db(context)
    if db.get_config("AI_SIM_ENABLED") != "1" or not ai.is_configured():
        return
    if not ai.can_call(db):
        return await context.bot.send_message(
            chat_id, "🧠 Avis IA sur la simulation : quota du jour déjà utilisé (1/jour).")
    try:
        cfgp = _paper_cfg()
        ctx = (f"MODE: SIMULATEUR (backtest paper-trading). "
               f"COÛTS: {cfgp.get('frais_pct', 0.2)}% par ordre (min {cfgp.get('frais_min', 1.0):.2f}), "
               f"achat ET vente.\n"
               f"RÉSULTATS DE SIMULATION (backtest {r.equity_curve.index[0].date()} → "
               f"{r.equity_curve.index[-1].date()}), capital {r.capital:.0f} → {r.final_equity:.2f} : "
               f"rendement {r.total_return*100:+.1f}%, CAGR {r.cagr*100:+.1f}%, Sharpe {r.sharpe}, "
               f"Sortino {r.sortino}, drawdown max {r.max_drawdown*100:.1f}%, "
               f"{r.n_trades} trades, réussite {r.win_rate*100:.0f}%, "
               f"profit factor {r.profit_factor}, frais totaux payés {r.fees_total:.0f}.")
        advice = await asyncio.to_thread(
            ai.ask, ctx, "Analyse ces résultats de backtest : forces, faiblesses, et 2-3 pistes "
                         "concrètes pour améliorer le rendement (profil agressif).")
        ai.record_call(db)
        db.log_event(chat_id, "ai_call", "source=simulation")
        await context.bot.send_message(
            chat_id, f"🧠 *Avis IA sur la simulation*\n\n{esc_md(advice)[:3800]}", parse_mode=MD)
    except Exception as e:  # noqa: BLE001
        await context.bot.send_message(chat_id, f"❌ Avis IA indisponible : {esc_md(str(e)[:150])}")


async def autotune(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🛠️ Auto-réglage des paramètres sur l'historique…")
    res = await _autotune_universe(context)
    if res is None:
        return await msg.edit_text("Auto-réglage impossible (données insuffisantes).")
    params, r = res
    # applique au compte de l'utilisateur s'il en a un
    if _db(context).paper_get(update.effective_chat.id):
        _db(context).paper_set_params(update.effective_chat.id, json.dumps(params))
    await msg.edit_text(
        f"🛠️ *Paramètres auto-réglés*\n⚙️ {fmt_params(params)}\n"
        f"Sur 2 ans : *{r.total_return*100:+.1f}%* (DD {r.max_drawdown*100:.1f}%).\n"
        "_Appliqués au mode autonome._", parse_mode=MD)


async def _autotune_universe(context):
    cfg = _paper_cfg()
    return await asyncio.to_thread(
        _svc(context).optimize_strategy, _universe(), cfg.get("capital", 1000),
        fee_pct=cfg.get("frais_pct", 0.2), fee_min=cfg.get("frais_min", 1.0),
        max_positions=cfg.get("max_positions", 5), alloc_pct=cfg.get("alloc_pct", 20),
        stop_loss_pct=cfg.get("stop_loss_pct", 0), max_dd_pause=cfg.get("max_dd_pause", 0),
        vol_target=cfg.get("vol_target", 0), rank_lookback=cfg.get("rank_lookback", 0),
        abs_mom_lookback=cfg.get("abs_mom_lookback", 0), abs_mom_min=cfg.get("abs_mom_min", 0),
    )


async def _run_auto_cycle(chat_id, context, announce: bool = False):
    """Exécute un cycle autonome pour un chat et logge les actions dans la conversation."""
    db = _db(context)
    svc = _svc(context)
    executed = await asyncio.to_thread(trader.run_cycle, db, svc, chat_id, _universe(), _paper_cfg())
    dev = _paper_cfg().get("devise", "EUR")
    for tr in executed:
        await context.bot.send_message(
            chat_id,
            trade_log(tr["side"], tr["asset"], tr["quantity"], tr["price"], tr["fee"],
                      tr.get("pnl") if tr["side"] == "VENTE" else None, dev,
                      motif=tr.get("motif")),
            parse_mode=MD,
        )
    # état + point d'équity
    acc, equity, holdings = await asyncio.to_thread(trader.account_state, db, svc, chat_id)
    db.paper_record_equity(chat_id, equity)
    invested = sum(h["value"] for h in holdings)
    # Dès qu'il agit, il dit où en est le cash et le total
    if executed:
        await context.bot.send_message(
            chat_id,
            state_recap(acc["cash"], invested, len(holdings), equity, acc["capital"], dev),
            parse_mode=MD)
    elif announce:
        await context.bot.send_message(
            chat_id,
            "👁️ Aucun mouvement ce tour-ci (positions stables).\n"
            + state_recap(acc["cash"], invested, len(holdings), equity, acc["capital"], dev),
            parse_mode=MD)


async def _send_bilan(chat_id, context):
    db = _db(context)
    svc = _svc(context)
    acc = db.paper_get(chat_id)
    if not acc:
        return await context.bot.send_message(chat_id, "Aucun compte autonome. Lance /auto 1000")
    acc, equity, holdings = await asyncio.to_thread(trader.account_state, db, svc, chat_id)
    from datetime import datetime, timezone
    since = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    trades_today = db.paper_trades_since(chat_id, since)
    db.paper_record_equity(chat_id, equity)
    await context.bot.send_message(chat_id, autobilan_block(acc, equity, holdings, trades_today),
                                   parse_mode=MD)
    curve = db.paper_equity_curve(chat_id)
    path = await asyncio.to_thread(make_equity_chart, curve, acc["capital"],
                                   "Mon portefeuille autonome", f"bilan_{chat_id}")
    if path:
        with open(path, "rb") as f:
            await context.bot.send_photo(chat_id, photo=f, caption="📈 Évolution de ton capital")


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
    chat_id = update.effective_chat.id
    s = _db(context).get_settings(chat_id)
    lang = _lang(context, chat_id)
    await update.message.reply_text(_settings_text(s, lang), parse_mode=MD,
                                    reply_markup=settings_keyboard(s, lang))


async def digest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_digest(update.effective_chat.id, context)


# --------------------------------------------------------------------------- #
#  Helpers d'affichage réutilisables (commandes + boutons)
# --------------------------------------------------------------------------- #
def _settings_text(s: dict, lang: str = DEFAULT_LANG) -> str:
    on_off = t("on", lang) if s.get("digest", 1) else t("off", lang)
    langue_aff = "Français" if s.get("langue", "fr") == "fr" else "English"
    if lang == "en":
        return (
            "⚙️ *Settings*\n\n"
            f"Alert sensitivity: *{s.get('sensibilite', 'normale')}*\n"
            f"Daily digest: *{on_off}*\n"
            f"Language: *{langue_aff}*\n\n"
            "_Few = only strong signals. Many = more frequent alerts._"
        )
    return (
        "⚙️ *Réglages*\n\n"
        f"Sensibilité des alertes : *{s.get('sensibilite', 'normale')}*\n"
        f"Résumé quotidien : *{on_off}*\n"
        f"Langue : *{langue_aff}*\n\n"
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

    lang = _lang(context, chat_id)
    if data == "menu":
        return await q.edit_message_text(t("menu_title", lang), parse_mode=MD, reply_markup=main_menu(lang))
    if data == "help":
        return await q.edit_message_text(HELP_EN if lang == "en" else HELP, parse_mode=MD,
                                         reply_markup=back_button(lang=lang))
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
    if data == "movers":
        await q.edit_message_text("🚀 Recherche des plus forts mouvements…")
        m = await asyncio.to_thread(_svc(context).movers, _universe())
        return await q.edit_message_text(movers_block(m), parse_mode=MD, reply_markup=back_button())
    if data == "apercu":
        from ..formatting import briefing_block
        await q.edit_message_text("📊 Je prépare ton briefing complet…")
        svc = _svc(context)
        brief = await asyncio.to_thread(svc.briefing, _universe())
        rc = await asyncio.to_thread(svc.risk_climate)
        season, _, _ = await asyncio.to_thread(svc.season)
        return await q.edit_message_text(briefing_block(brief, rc, season), parse_mode=MD,
                                         reply_markup=back_button())
    if data == "marche":
        await q.edit_message_text("🌍 Analyse de la tendance générale du marché…")
        m = await asyncio.to_thread(_svc(context).market_trend, _universe())
        line = await asyncio.to_thread(_regime_line, _svc(context))
        return await q.edit_message_text(market_block(m) + line, parse_mode=MD, reply_markup=back_button())
    if data == "agr_menu":
        return await q.edit_message_text(
            "🎚️ *Niveau d'agressivité*\n🛡️ Prudent · ⚖️ Normale · 🔥 Agressif\n"
            "_Règle le nombre de positions, la part investie et la réactivité._", parse_mode=MD,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛡️ Prudent", callback_data="agr:prudent"),
                 InlineKeyboardButton("⚖️ Normale", callback_data="agr:normale"),
                 InlineKeyboardButton("🔥 Agressif", callback_data="agr:agressif")],
                [InlineKeyboardButton("⬅️ Retour", callback_data="auto_menu")]]))
    if data.startswith("agr:"):
        name = data.split(":", 1)[1]
        if db.paper_get(chat_id):
            db.paper_set_params(chat_id, json.dumps(profile(name)))
        return await q.edit_message_text(
            f"🎚️ Agressivité réglée sur *{name}*.", parse_mode=MD,
            reply_markup=back_button("auto_menu"))
    if data == "ia_panel":
        return await q.edit_message_text(_ia_status_text(db), parse_mode=MD,
                                         reply_markup=_ia_keyboard(db))
    if data == "brokers_menu":
        return await q.edit_message_text(_brokers_hub_text(db), parse_mode=MD,
                                         reply_markup=_brokers_hub_keyboard())
    if data == "brk:tr":
        if not get_secret("TR_PHONE"):
            return await q.edit_message_text(
                "🏦 *Trade Republic* (lecture seule)\n\nConfigure d'abord :\n"
                "`/set TR_PHONE +33...`\n`/set TR_PIN ****`\nPuis tape /traderepublic.",
                parse_mode=MD, reply_markup=back_button("brokers_menu"))
        await q.edit_message_text("🏦 Lecture du compte Trade Republic… (tape /traderepublic "
                                  "si un code 2FA est demandé)")
        def _read_tr():
            from ..brokers.traderepublic import TradeRepublicBroker
            b = TradeRepublicBroker()
            if not b.resume():
                return None
            return b.get_account(), b.get_positions()
        try:
            res = await asyncio.to_thread(_read_tr)
        except Exception as e:  # noqa: BLE001
            from ..formatting import esc_md
            return await q.edit_message_text(f"❌ {esc_md(str(e)[:150])}",
                                             reply_markup=back_button("brokers_menu"))
        if res is None:
            return await q.edit_message_text(
                "🔐 Session TR expirée. Tape /traderepublic pour te reconnecter (2FA).",
                reply_markup=back_button("brokers_menu"))
        acc, pos = res
        lines = [f"🏦 *{acc['status']}*", f"💵 Cash : {acc['cash']:.2f} {acc['currency']}",
                 f"📊 Total : *{acc['equity']:.2f} {acc['currency']}*"]
        for p in pos[:15]:
            lines.append(f"• `{p['symbol']}` {p['qty']:g} @ {p['avg_entry_price']:.2f}")
        return await q.edit_message_text("\n".join(lines), parse_mode=MD,
                                         reply_markup=back_button("brokers_menu"))
    if data == "brk:ccxt":
        if not get_secret("EXCHANGE_NAME"):
            return await q.edit_message_text(
                "💱 *Échange crypto* (Binance, Kraken…)\n\nConfigure :\n"
                "`/set EXCHANGE_NAME binance`\n`/set EXCHANGE_API_KEY …`\n`/set EXCHANGE_API_SECRET …`",
                parse_mode=MD, reply_markup=back_button("brokers_menu"))
        await q.edit_message_text("💱 Connexion à l'échange…")
        def _ccxt():
            from ..brokers import CCXTBroker
            b = CCXTBroker()
            return b.get_account(), b.get_positions()
        try:
            acc, pos = await asyncio.to_thread(_ccxt)
        except Exception as e:  # noqa: BLE001
            from ..formatting import esc_md
            return await q.edit_message_text(f"❌ {esc_md(str(e)[:150])}",
                                             reply_markup=back_button("brokers_menu"))
        lines = [f"💱 *{acc['status']}*", f"💵 {acc['cash']:.2f} {acc['currency']}"]
        for p in pos[:15]:
            lines.append(f"• {p['symbol']} : {p['qty']:g}")
        return await q.edit_message_text("\n".join(lines), parse_mode=MD,
                                         reply_markup=back_button("brokers_menu"))
    if data == "alpaca_panel":
        return await q.edit_message_text(_alpaca_auto_text(db), parse_mode=MD,
                                         reply_markup=_alpaca_auto_keyboard(db))
    if data.startswith("alp:"):
        sub = data.split(":", 1)[1]
        if sub == "bilan":
            await q.answer("📊 Je récupère ton compte Alpaca…")
            return await _alpaca_bilan(chat_id, context)
        if sub in ("off", "paper", "live"):
            db.set_config("ALPACA_AUTO", sub)
            if sub == "live":
                await q.answer("⚠️ Mode RÉEL activé — vrai argent !", show_alert=True)
        elif sub == "test":
            await q.edit_message_text("🔌 Test de connexion Alpaca…")
            def _t():
                from ..brokers.alpaca import AlpacaBroker
                b = AlpacaBroker(mode=db.get_config("ALPACA_AUTO") or "paper")
                return b.get_account()
            try:
                acc = await asyncio.to_thread(_t)
                await q.edit_message_text(
                    f"✅ Connecté — compte {acc['status']}, équity {acc['equity']:.2f} "
                    f"{acc['currency']}", reply_markup=_alpaca_auto_keyboard(db))
            except Exception as e:  # noqa: BLE001
                from ..formatting import esc_md
                await q.edit_message_text(f"❌ {esc_md(str(e)[:200])}",
                                          reply_markup=_alpaca_auto_keyboard(db))
            return
        return await q.edit_message_text(_alpaca_auto_text(db), parse_mode=MD,
                                         reply_markup=_alpaca_auto_keyboard(db))
    if data.startswith("ia:"):
        parts_cb = data.split(":")
        action = parts_cb[1]
        if action == "live":
            # Mode trading : "solo" = autonome seul (zéro appel IA) ; "ia" = autonome + IA
            # (conseil quotidien ET exécution des ordres, d'un seul geste)
            on = parts_cb[2] == "ia"
            db.set_config("AI_ENABLED", "1" if on else "0")
            db.set_config("AI_EXEC_ENABLED", "1" if on else "0")
        elif action == "sim":
            db.set_config("AI_SIM_ENABLED", "1" if parts_cb[2] == "ia" else "0")
        elif action in ("toggle_live", "toggle_exec", "toggle_sim"):
            # rétro-compat : anciens boutons encore affichés dans de vieux messages
            key = {"toggle_live": "AI_ENABLED", "toggle_exec": "AI_EXEC_ENABLED",
                   "toggle_sim": "AI_SIM_ENABLED"}[action]
            db.set_config(key, "0" if db.get_config(key) == "1" else "1")
        elif action == "ask":
            await q.edit_message_text("🧠 Demande en cours…")
            return await _ia_ask_and_send(chat_id, context, source="manuel")
        return await q.edit_message_text(_ia_status_text(db), parse_mode=MD,
                                         reply_markup=_ia_keyboard(db))
    if data.startswith("delalert:"):
        db.remove_price_alert(int(data.split(":", 1)[1]), chat_id)
        al = db.get_price_alerts(chat_id)
        if not al:
            return await q.edit_message_text("🔔 Alerte supprimée. Plus aucune alerte.")
        rows, lines = [], ["🔔 *Tes alertes de prix*"]
        for a in al:
            arrow = "≥" if a["direction"] == "above" else "≤"
            lines.append(f"• #{a['id']} {a['asset']} {arrow} {a['target']:g}")
            rows.append([InlineKeyboardButton(f"🗑️ Supprimer #{a['id']}", callback_data=f"delalert:{a['id']}")])
        return await q.edit_message_text("\n".join(lines), parse_mode=MD,
                                         reply_markup=InlineKeyboardMarkup(rows))
    if data == "auto_menu":
        acc = db.paper_get(chat_id)
        active = bool(acc and acc.get("active"))
        txt = ("🤖 *Mode autonome* — actif.\nJe trade tout seul un capital fictif, frais inclus."
               if active else
               "🤖 *Mode autonome*\nJe gère un capital *fictif* tout seul (achat/vente, frais de "
               "courtage, auto-réglage) et je te logue chaque action.\n\n_Conseil : lance d'abord une simulation._")
        return await q.edit_message_text(txt, parse_mode=MD, reply_markup=auto_menu_keyboard(active))
    if data == "auto_start":
        cfg = _paper_cfg()
        db.paper_open(chat_id, cfg.get("capital", 1000), cfg.get("devise", "EUR"))
        await q.edit_message_text("🤖 *Mode autonome activé* (1000 € fictifs). Premier tour…", parse_mode=MD)
        await _run_auto_cycle(chat_id, context, announce=True)
        return await _send_bilan(chat_id, context)
    if data == "auto_bilan":
        await q.edit_message_text("📊 Préparation du bilan…")
        return await _send_bilan(chat_id, context)
    if data == "auto_reset":
        cfg = _paper_cfg()
        db.paper_open(chat_id, cfg.get("capital", 1000), cfg.get("devise", "EUR"))
        return await q.edit_message_text("♻️ Réinitialisé à 1000 €, positions et historique effacés.",
                                         reply_markup=back_button("auto_menu"))
    if data == "auto_stop":
        db.paper_set_active(chat_id, 0)
        return await q.edit_message_text("⏸️ Mode autonome en pause.", reply_markup=back_button("auto_menu"))
    if data == "auto_tune":
        await q.edit_message_text("🛠️ Auto-réglage en cours…")
        res = await _autotune_universe(context)
        if res is None:
            return await q.edit_message_text("Auto-réglage impossible.", reply_markup=back_button("auto_menu"))
        params, r = res
        if db.paper_get(chat_id):
            db.paper_set_params(chat_id, json.dumps(params))
        return await q.edit_message_text(
            f"🛠️ *Réglé*\n⚙️ {fmt_params(params)}\n"
            f"Backtest 2 ans : {r.total_return*100:+.1f}% (DD {r.max_drawdown*100:.1f}%).",
            parse_mode=MD, reply_markup=back_button("auto_menu"))
    if data == "simuler":
        await q.edit_message_text("🧪 Simulation historique (2 ans)…")
        cfg = _paper_cfg()
        r = await asyncio.to_thread(
            _svc(context).simulate_portfolio, _universe(), cfg.get("capital", 1000),
            fee_pct=cfg.get("frais_pct", 0.2), fee_min=cfg.get("frais_min", 1.0),
            max_positions=cfg.get("max_positions", 5), alloc_pct=cfg.get("alloc_pct", 20),
            stop_loss_pct=cfg.get("stop_loss_pct", 0), max_dd_pause=cfg.get("max_dd_pause", 0),
            vol_target=cfg.get("vol_target", 0), rank_lookback=cfg.get("rank_lookback", 0),
            abs_mom_lookback=cfg.get("abs_mom_lookback", 0), abs_mom_min=cfg.get("abs_mom_min", 0))
        await q.edit_message_text(sim_block(r, cfg.get("devise", "EUR")), parse_mode=MD,
                                  reply_markup=back_button("auto_menu"))
        if r is not None:
            path = await asyncio.to_thread(make_equity_chart, r.equity_curve, r.capital,
                                           "Simulation du mode autonome", "sim")
            if path:
                with open(path, "rb") as f:
                    await context.bot.send_photo(chat_id, photo=f, caption="📈 Évolution simulée")
        return
    if data.startswith("graph:"):
        raw = data.split(":", 1)[1]
        return await _send_chart(chat_id, context, raw)
    if data.startswith("bt:"):
        raw = data.split(":", 1)[1]
        await q.edit_message_text("🧪 Backtest en cours…")
        r = await asyncio.to_thread(_svc(context).backtest, raw)
        return await q.edit_message_text(backtest_block(r), parse_mode=MD,
                                         reply_markup=asset_keyboard(raw))
    if data == "settings":
        s = db.get_settings(chat_id)
        return await q.edit_message_text(_settings_text(s, lang), parse_mode=MD,
                                         reply_markup=settings_keyboard(s, lang))
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
        return await q.edit_message_text(_settings_text(s, lang), parse_mode=MD,
                                         reply_markup=settings_keyboard(s, lang))
    if data == "set:digest:toggle":
        s = db.get_settings(chat_id)
        db.set_setting(chat_id, "digest", 0 if s.get("digest", 1) else 1)
        s = db.get_settings(chat_id)
        return await q.edit_message_text(_settings_text(s, lang), parse_mode=MD,
                                         reply_markup=settings_keyboard(s, lang))
    if data == "set:langue:toggle":
        newlang = "en" if lang == "fr" else "fr"
        db.set_setting(chat_id, "langue", newlang)
        s = db.get_settings(chat_id)
        return await q.edit_message_text(_settings_text(s, newlang), parse_mode=MD,
                                         reply_markup=settings_keyboard(s, newlang))


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
            a = await asyncio.to_thread(svc.analyze, asset, False)
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


async def portefeuille_job(context: ContextTypes.DEFAULT_TYPE):
    """Surveille les positions détenues et alerte quand il faudrait envisager de vendre."""
    db: Storage = context.application.bot_data["db"]
    svc: MarketService = context.application.bot_data["svc"]
    # Regroupe les actifs détenus par utilisateur
    seen: set[tuple[int, str]] = set()
    for chat_id in {cid for cid, _ in db.all_watched_pairs()} | set(db.chats_with_digest()):
        for p in db.get_positions(chat_id):
            asset = p["asset"]
            if (chat_id, asset) in seen:
                continue
            seen.add((chat_id, asset))
            try:
                a = await asyncio.to_thread(svc.analyze, asset, False)
                if a.signal is None or a.quote is None:
                    continue
                pnl_pct = None
                if p["buy_price"]:
                    pnl_pct = (a.quote.price - p["buy_price"]) / p["buy_price"] * 100
                # Alerte si signal de vente OU perte importante (> 8%)
                sell = a.signal.direction == Direction.SELL
                stop_hit = pnl_pct is not None and pnl_pct <= -8
                if not (sell or stop_hit):
                    continue
                if not db.should_alert(chat_id, f"PF:{asset}", "VENDRE", 6):
                    continue
                why = "signal de vente" if sell else f"perte de {pnl_pct:.1f}% sur ta position"
                await context.bot.send_message(
                    chat_id,
                    f"💼🔴 *Envisage de vendre {asset}*\n📌 {why}\n"
                    f"Cours : {a.quote.price:g} (achat {p['buy_price']:g})\n"
                    "_⚠️ Outil éducatif — décision finale à toi._",
                    parse_mode=MD,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("Portefeuille %s/%s : %s", chat_id, asset, e)


async def digest_job(context: ContextTypes.DEFAULT_TYPE):
    """Envoie le résumé quotidien aux utilisateurs qui l'ont activé."""
    db: Storage = context.application.bot_data["db"]
    for chat_id in db.chats_with_digest():
        try:
            await _send_digest(chat_id, context)
        except Exception as e:  # noqa: BLE001
            log.warning("Digest %s : %s", chat_id, e)


async def auto_trade_job(context: ContextTypes.DEFAULT_TYPE):
    """Fait trader les comptes autonomes et logge chaque action dans le chat."""
    db: Storage = context.application.bot_data["db"]
    for chat_id in db.paper_active_chats():
        try:
            await _run_auto_cycle(chat_id, context)
        except Exception as e:  # noqa: BLE001
            log.warning("Auto-trade %s : %s", chat_id, e)


async def auto_bilan_job(context: ContextTypes.DEFAULT_TYPE):
    """Bilan quotidien du mode autonome (valeur, bénéfice, actions du jour, graphique)."""
    db: Storage = context.application.bot_data["db"]
    for chat_id in db.paper_active_chats():
        try:
            await _send_bilan(chat_id, context)
        except Exception as e:  # noqa: BLE001
            log.warning("Bilan auto %s : %s", chat_id, e)


async def alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """Vérifie les alertes de prix et notifie quand un seuil est franchi."""
    db: Storage = context.application.bot_data["db"]
    svc: MarketService = context.application.bot_data["svc"]
    alerts = db.all_price_alerts()
    if not alerts:
        return
    prices: dict[str, float] = {}
    for raw in {a["asset"] for a in alerts}:
        q = await asyncio.to_thread(svc.quote, raw)
        if q is not None and q.price == q.price:  # écarte NaN
            prices[raw] = q.price
    for a in alerts:
        p = prices.get(a["asset"])
        if p is None:
            continue
        hit = (a["direction"] == "above" and p >= a["target"]) or \
              (a["direction"] == "below" and p <= a["target"])
        if hit:
            arrow = "≥" if a["direction"] == "above" else "≤"
            try:
                await context.bot.send_message(
                    a["chat_id"],
                    f"🔔 *Alerte prix atteinte* : {a['asset']} {arrow} {a['target']:g}\n"
                    f"Cours actuel : *{p:g}*", parse_mode=MD)
            except Exception:  # noqa: BLE001
                pass
            db.remove_price_alert(a["id"])


async def backup_job(context: ContextTypes.DEFAULT_TYPE):
    """Sauvegarde quotidienne de la base (rotation : 7 dernières)."""
    db: Storage = context.application.bot_data["db"]
    try:
        dest = await asyncio.to_thread(db.backup)
        log.info("Sauvegarde base -> %s", dest)
    except Exception as e:  # noqa: BLE001
        log.warning("Sauvegarde échouée : %s", e)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire d'erreurs global : journalise toute exception non interceptée."""
    log.error("Erreur non interceptée : %s", context.error, exc_info=context.error)


async def autotune_job(context: ContextTypes.DEFAULT_TYPE):
    """S'ajuste tout seul : ré-optimise la stratégie et l'applique aux comptes actifs."""
    db: Storage = context.application.bot_data["db"]
    actives = db.paper_active_chats()
    if not actives:
        return
    try:
        res = await _autotune_universe(context)
    except Exception as e:  # noqa: BLE001
        log.warning("Autotune : %s", e)
        return
    if res is None:
        return
    params, r = res
    for chat_id in actives:
        db.paper_set_params(chat_id, json.dumps(params))
        try:
            await context.bot.send_message(
                chat_id,
                f"🛠️ *Stratégie ré-ajustée automatiquement*\n⚙️ {fmt_params(params)}\n"
                f"_Backtest 2 ans : {r.total_return*100:+.1f}% (DD {r.max_drawdown*100:.1f}%)._",
                parse_mode=MD)
        except Exception:  # noqa: BLE001
            pass


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
    db = Storage()
    db.seed_universe(CONFIG.get("univers_scan", []))
    app.bot_data["db"] = db
    global _DB_REF
    _DB_REF = db

    # Porte d'authentification (priorité haute, avant tout le reste)
    app.add_handler(TypeHandler(Update, auth_gate), group=-1)

    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["aide", "help"], help_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("prix", prix))
    app.add_handler(CommandHandler("analyse", analyse))
    app.add_handler(CommandHandler(["idees", "idee"], idees))
    app.add_handler(CommandHandler(["backtest", "bt"], backtest_cmd))
    app.add_handler(CommandHandler(["graph", "graphique"], graph_cmd))
    app.add_handler(CommandHandler(["movers", "mouvements"], movers_cmd))
    app.add_handler(CommandHandler(["tendance", "trend"], tendance))
    app.add_handler(CommandHandler(["marche", "market"], marche))
    app.add_handler(CommandHandler(["equipe", "team"], equipe))
    app.add_handler(CommandHandler("alpaca", alpaca_cmd))
    app.add_handler(CommandHandler(["ia", "ai", "conseiller"], ia_cmd))
    app.add_handler(CommandHandler(["securite", "security"], securite_cmd))
    app.add_handler(CommandHandler(["deconnexion", "logout"], deconnexion_cmd))
    app.add_handler(CommandHandler(["config", "configuration"], config_cmd))
    app.add_handler(CommandHandler("set", set_cmd))
    app.add_handler(CommandHandler(["del", "supprimer"], del_cmd))
    app.add_handler(CommandHandler(["bilanalpaca", "alpacabilan"],
                                   lambda u, c: _alpaca_bilan(u.effective_chat.id, c)))
    app.add_handler(CommandHandler(["brokers", "courtiers"], brokers_cmd))
    app.add_handler(CommandHandler(["traderepublic", "tr"], traderepublic_cmd))
    app.add_handler(CommandHandler("tr_code", tr_code_cmd))
    app.add_handler(CommandHandler(["broker", "exchange", "echange"], broker_cmd))
    app.add_handler(CommandHandler(["export", "config"], export_cmd))
    app.add_handler(CommandHandler(["sauvegarde", "backup"], sauvegarde_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(CommandHandler(["maitres", "legendes", "masters"], maitres))
    app.add_handler(CommandHandler(["apercu", "brief", "briefing", "dashboard"], apercu))
    app.add_handler(CommandHandler(["sources", "source"], sources))
    app.add_handler(CommandHandler(["macro", "regime"], macro_cmd))
    app.add_handler(CommandHandler(["saison", "season"], saison))
    app.add_handler(CommandHandler(["risque", "risk", "geopolitique"], risque))
    app.add_handler(CommandHandler(["univers", "universe"], univers))
    app.add_handler(CommandHandler(["alerte", "alert"], alerte))
    app.add_handler(CommandHandler("alertes", alertes))
    app.add_handler(CommandHandler(["agressivite", "agro"], agressivite))
    app.add_handler(CommandHandler("actu", actu))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("liste", liste))
    app.add_handler(CommandHandler("ajouter", ajouter))
    app.add_handler(CommandHandler("portefeuille", portefeuille))
    app.add_handler(CommandHandler("perf", perf))
    app.add_handler(CommandHandler("reglages", reglages))
    app.add_handler(CommandHandler(["langue", "language", "lang"], langue_cmd))
    app.add_handler(CommandHandler("digest", digest_cmd))
    app.add_handler(CommandHandler(["auto", "autonome"], auto))
    app.add_handler(CommandHandler(["reset", "reinit"], reset_auto))
    app.add_handler(CommandHandler(["stopauto", "pause"], stop_auto))
    app.add_handler(CommandHandler("bilan", bilan))
    app.add_handler(CommandHandler(["simuler", "simulation"], simuler))
    app.add_handler(CommandHandler(["autotune", "regler"], autotune))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_error_handler(on_error)

    freq_min = CONFIG.get("frequences", {}).get("actions", 15)
    auto_min = CONFIG.get("frequences", {}).get("auto", 5)
    app.job_queue.run_repeating(surveiller_job, interval=freq_min * 60, first=30)
    app.job_queue.run_repeating(portefeuille_job, interval=freq_min * 60, first=90)
    # Trading autonome : lecture du marché toutes les `auto` minutes (défaut 5)
    app.job_queue.run_repeating(auto_trade_job, interval=auto_min * 60, first=120)
    # Digest + bilan autonome + auto-réglage quotidiens (heure du serveur)
    from datetime import time as dtime
    app.job_queue.run_daily(digest_job, time=dtime(hour=8, minute=0))
    app.job_queue.run_daily(auto_bilan_job, time=dtime(hour=18, minute=0))
    app.job_queue.run_daily(autotune_job, time=dtime(hour=7, minute=0))
    app.job_queue.run_daily(backup_job, time=dtime(hour=6, minute=0))
    # Conseil IA quotidien (si activé) — EN PLEINE SÉANCE, à l'heure locale de la bourse :
    # 12h45 America/New_York = milieu de la séance US (novembre/mars gérés par le fuseau).
    from zoneinfo import ZoneInfo
    app.job_queue.run_daily(ia_daily_job,
                            time=dtime(hour=12, minute=45, tzinfo=ZoneInfo("America/New_York")))
    app.job_queue.run_repeating(alerts_job, interval=auto_min * 60, first=60)
    # Trading autonome sur Alpaca (si activé paper/live) — toutes les heures
    app.job_queue.run_repeating(alpaca_auto_job, interval=3600, first=150)
    return app
