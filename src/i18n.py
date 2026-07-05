"""Internationalisation (FR/EN). Le français reste la langue par défaut.

Usage : t("welcome", lang) ; les valeurs peuvent contenir des {placeholders}.
"""

from __future__ import annotations

LANGS = ("fr", "en")
DEFAULT_LANG = "fr"

TR: dict[str, dict[str, str]] = {
    # --- Accueil ---
    "welcome": {
        "fr": (
            "🦉 *Bienvenue sur OwlTrader !*\n\n"
            "Ton assistant de marché — actions, crypto, devises, matières premières — qui te dit "
            "*acheter*, *vendre* ou *conserver*, sans jargon et sans te noyer d'infos.\n\n"
            "✨ *Pour bien démarrer :*\n"
            "1️⃣ 🧪 *Simuler* — vois la stratégie prouvée sur 10 ans\n"
            "2️⃣ 🤖 *Mode autonome* — confie-lui 1000 € fictifs, il trade tout seul\n"
            "3️⃣ 💡 *Idées d'achat* — les meilleures opportunités du moment\n\n"
            "_100 % gratuit · trading fictif · aucun risque. Touche un bouton 👇_"
        ),
        "en": (
            "🦉 *Welcome to OwlTrader!*\n\n"
            "Your market assistant — stocks, crypto, forex, commodities — telling you when to "
            "*buy*, *sell* or *hold*, without jargon or information overload.\n\n"
            "✨ *To get started:*\n"
            "1️⃣ 🧪 *Simulate* — see the strategy proven over 10 years\n"
            "2️⃣ 🤖 *Autonomous mode* — give it €1000 fictional, it trades on its own\n"
            "3️⃣ 💡 *Buy ideas* — the best opportunities right now\n\n"
            "_100% free · fictional trading · zero risk. Tap a button 👇_"
        ),
    },
    # --- Menu principal (boutons) ---
    "btn_briefing": {"fr": "📊 Briefing marché", "en": "📊 Market briefing"},
    "btn_auto": {"fr": "🤖 Mode autonome", "en": "🤖 Autonomous mode"},
    "btn_simulate": {"fr": "🧪 Simuler", "en": "🧪 Simulate"},
    "btn_ideas": {"fr": "💡 Idées d'achat", "en": "💡 Buy ideas"},
    "btn_movers": {"fr": "🚀 Top mouvements", "en": "🚀 Top movers"},
    "btn_market": {"fr": "🌍 Tendance marché", "en": "🌍 Market trend"},
    "btn_ia": {"fr": "🧠 Conseiller IA", "en": "🧠 AI advisor"},
    "btn_watchlist": {"fr": "👁️ Ma watchlist", "en": "👁️ My watchlist"},
    "btn_portfolio": {"fr": "💼 Portefeuille", "en": "💼 Portfolio"},
    "btn_perf": {"fr": "📈 Performance", "en": "📈 Performance"},
    "btn_news": {"fr": "📰 Actus", "en": "📰 News"},
    "btn_settings": {"fr": "⚙️ Réglages", "en": "⚙️ Settings"},
    "btn_help": {"fr": "❓ Aide", "en": "❓ Help"},
    "btn_back": {"fr": "⬅️ Retour", "en": "⬅️ Back"},
    "menu_title": {"fr": "🦉 *Menu principal*", "en": "🦉 *Main menu*"},
    # --- Réglages ---
    "settings_title": {"fr": "⚙️ *Réglages*", "en": "⚙️ *Settings*"},
    "settings_sensitivity": {"fr": "Sensibilité des alertes", "en": "Alert sensitivity"},
    "settings_digest": {"fr": "Résumé quotidien", "en": "Daily digest"},
    "settings_language": {"fr": "Langue", "en": "Language"},
    "on": {"fr": "activé", "en": "on"},
    "off": {"fr": "désactivé", "en": "off"},
    "btn_language": {"fr": "🌐 Langue : Français", "en": "🌐 Language: English"},
    "lang_changed": {"fr": "🌐 Langue réglée sur *Français*.", "en": "🌐 Language set to *English*."},
    # --- Messages courants ---
    "data_unavailable": {"fr": "❌ Donnée indisponible pour cet actif.",
                         "en": "❌ Data unavailable for this asset."},
    "loading": {"fr": "⏳ Un instant…", "en": "⏳ One moment…"},
    "disclaimer": {"fr": "_⚠️ Outil éducatif — aucune recommandation d'investissement._",
                   "en": "_⚠️ Educational tool — not investment advice._"},
}


def t(key: str, lang: str | None = None, **fmt) -> str:
    lang = lang if lang in LANGS else DEFAULT_LANG
    entry = TR.get(key, {})
    s = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    return s.format(**fmt) if fmt else s


def normalize_lang(code: str | None) -> str:
    """Déduit fr/en depuis un code langue Telegram (ex. 'en-US' -> 'en')."""
    if not code:
        return DEFAULT_LANG
    code = code.lower()[:2]
    return code if code in LANGS else DEFAULT_LANG
