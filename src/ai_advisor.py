"""Conseiller IA (OpenAI) — FACULTATIF, désactivé par défaut.

Agrège le contexte complet (positions, signaux, tendance marché, risque, actus RSS)
et demande UNE FOIS PAR JOUR MAX à un modèle OpenAI un avis acheter/vendre, avec un
profil agressif orienté gains. Limites strictes :
- 1 requête par jour (quota partagé live + simulateur), stockée en base ;
- plafond de tokens de sortie configurable (défaut 100 000) ;
- pas d'appel si aucune position en cours (côté live) ;
- clé API stockée chiffrée (via /set) ou dans .env — jamais dans le dépôt.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from .config import get_secret

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_TOKENS = 100_000

SYSTEM_PROMPT = (
    "Tu es un conseiller de trading expérimenté au profil AGRESSIF : ton objectif est de "
    "maximiser les gains de l'utilisateur, tout en signalant les risques majeurs. "
    "On te fournit un contexte complet : positions actuelles, signaux techniques, tendance "
    "de marché, climat de risque et titres d'actualité. Réponds en FRANÇAIS, de façon "
    "concise et actionnable :\n"
    "1) Pour CHAQUE position : RENFORCER / VENDRE / GARDER, avec une raison courte.\n"
    "2) Top 2-3 opportunités d'achat si le contexte s'y prête.\n"
    "3) Un conseil global agressif du jour (1-2 phrases).\n"
    "Termine par : « ⚠️ Avis IA, pas un conseil financier. »"
)


def is_configured() -> bool:
    return bool(get_secret("OPENAI_API_KEY"))


def _model() -> str:
    return get_secret("OPENAI_MODEL") or DEFAULT_MODEL


def _max_tokens() -> int:
    try:
        return int(get_secret("AI_MAX_TOKENS") or DEFAULT_MAX_TOKENS)
    except ValueError:
        return DEFAULT_MAX_TOKENS


# --- Quota : 1 requête / jour, partagé entre live et simulateur ---
def can_call(db) -> bool:
    last = db.get_config("AI_LAST_CALL")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return last != today


def record_call(db):
    db.set_config("AI_LAST_CALL", datetime.now(timezone.utc).strftime("%Y-%m-%d"))


def build_context(svc, db, chat_id: int, universe: list[str]) -> str:
    """Agrège tout le contexte utile en un texte compact pour le modèle."""
    from .paper import trader
    parts: list[str] = []

    # Positions & compte
    acc, equity, holdings = trader.account_state(db, svc, chat_id)
    if acc:
        parts.append(f"COMPTE (fictif): total {equity:.2f} {acc.get('devise','EUR')}, "
                     f"cash {acc['cash']:.2f}, capital initial {acc['capital']:.0f}")
    if holdings:
        parts.append("POSITIONS:")
        for h in holdings:
            pnl = f" ({h['pnl_pct']:+.1f}%)" if h.get("pnl_pct") is not None else ""
            parts.append(f"- {h['asset']}: {h['value']:.2f}{pnl}")

    # Signaux sur les positions
    try:
        for h in holdings[:6]:
            a = svc.analyze(h["asset"], with_news=False)
            if a.signal:
                parts.append(f"SIGNAL {h['asset']}: {a.signal.direction.value} "
                             f"(force {a.signal.score:.0f}) — {a.signal.reason}")
    except Exception:  # noqa: BLE001
        pass

    # Marché global + risque + saison
    try:
        m = svc.market_trend(universe)
        if m:
            parts.append(f"MARCHÉ: {m.label}, {m.breadth:.0f}% haussiers, score {m.avg_score:+.0f}")
    except Exception:  # noqa: BLE001
        pass
    try:
        rc = svc.risk_climate()
        parts.append(f"RISQUE: {rc.label} | {rc.vix_note} | tension géo {rc.geo_score*100:.0f}%")
    except Exception:  # noqa: BLE001
        pass

    # Actus agrégées (multi-RSS)
    try:
        from .news import get_market_news
        news = get_market_news(10)
        if news:
            parts.append("ACTUS (titres récents):")
            for it in news:
                parts.append(f"- [{it.source}] {it.title}")
    except Exception:  # noqa: BLE001
        pass

    return "\n".join(parts) if parts else "Aucun contexte disponible."


def ask(context_text: str, question: str | None = None) -> str:
    """Envoie le contexte au modèle OpenAI et renvoie l'avis (texte)."""
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Clé OpenAI absente (OPENAI_API_KEY).")
    user_msg = context_text if not question else f"{context_text}\n\nQUESTION: {question}"
    payload = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_completion_tokens": _max_tokens(),
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.post("https://api.openai.com/v1/chat/completions",
                      headers=headers, json=payload, timeout=90)
    if r.status_code == 400 and "max_completion_tokens" in r.text:
        # anciens modèles : paramètre max_tokens
        payload.pop("max_completion_tokens", None)
        payload["max_tokens"] = min(_max_tokens(), 16_000)
        r = requests.post("https://api.openai.com/v1/chat/completions",
                          headers=headers, json=payload, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
