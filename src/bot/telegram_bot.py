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
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
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
            [InlineKeyboardButton("📊 Briefing marché", callback_data="apercu")],
            [InlineKeyboardButton("🤖 Mode autonome", callback_data="auto_menu"),
             InlineKeyboardButton("🧪 Simuler", callback_data="simuler")],
            [InlineKeyboardButton("💡 Idées d'achat", callback_data="idees"),
             InlineKeyboardButton("🚀 Top mouvements", callback_data="movers")],
            [InlineKeyboardButton("🌍 Tendance marché", callback_data="marche")],
            [InlineKeyboardButton("👁️ Ma watchlist", callback_data="watchlist"),
             InlineKeyboardButton("💼 Portefeuille", callback_data="pf")],
            [InlineKeyboardButton("📈 Performance", callback_data="perf"),
             InlineKeyboardButton("📰 Actus", callback_data="news_menu")],
            [InlineKeyboardButton("⚙️ Réglages", callback_data="settings"),
             InlineKeyboardButton("❓ Aide", callback_data="help")],
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
    rows.append([InlineKeyboardButton("🧪 Simuler d'abord", callback_data="simuler")])
    rows.append([InlineKeyboardButton("⬅️ Retour", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


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
            [InlineKeyboardButton("📈 Graphique", callback_data=f"graph:{raw}"),
             InlineKeyboardButton("🧪 Backtest", callback_data=f"bt:{raw}")],
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
    lines = [f"🦙 *Alpaca paper* — compte {acc['status']}",
             f"💵 Cash : {acc['cash']:.2f} {acc['currency']}",
             f"📊 Équity : *{acc['equity']:.2f} {acc['currency']}*", ""]
    if pos:
        lines.append("*Positions*")
        for p in pos:
            lines.append(f"• {p['symbol']} : {p['qty']:g} ({p['unrealized_plpc']:+.1f}%)")
    else:
        lines.append("Aucune position ouverte.")
    await msg.edit_text("\n".join(lines), parse_mode=MD)


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
    app.add_handler(CommandHandler(["maitres", "legendes", "masters"], maitres))
    app.add_handler(CommandHandler(["apercu", "brief", "briefing", "dashboard"], apercu))
    app.add_handler(CommandHandler(["sources", "source"], sources))
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
    app.job_queue.run_repeating(alerts_job, interval=auto_min * 60, first=60)
    return app
