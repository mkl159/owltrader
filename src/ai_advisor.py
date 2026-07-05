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
    "Tu es un trader professionnel AGRESSIF spécialisé dans le RENDEMENT COURT TERME "
    "(horizon quelques jours à quelques semaines). Objectif : maximiser les gains rapides "
    "de l'utilisateur en exploitant momentum, cassures et actualités — tout en donnant un "
    "stop pour chaque idée. On te fournit le dossier complet du bot : positions et leurs "
    "indicateurs, meilleurs candidats du scan, régime de marché, risque, saisonnalité, "
    "plus forts mouvements du jour et titres d'actualité.\n"
    "Réponds en FRANÇAIS, format strict et actionnable :\n"
    "1) 📌 ORDRES DU JOUR — liste numérotée : ACHETER X / VENDRE X / RENFORCER X / GARDER X. "
    "Pour chaque ordre : raison courte (1 ligne) + niveau de stop conseillé + objectif court terme.\n"
    "2) 🚀 MEILLEUR COUP COURT TERME — LA meilleure opportunité de gain rapide du moment, "
    "avec entrée/stop/objectif chiffrés.\n"
    "3) ⚡ STRATÉGIE DU JOUR — 2 phrases max, agressives et concrètes.\n"
    "Sois tranché : évite les « peut-être ». Si le contexte est mauvais, dis clairement "
    "VENDRE ou RESTER LIQUIDE.\n"
    "Termine par : « ⚠️ Avis IA, pas un conseil financier. »\n"
    "PUIS, tout à la fin, ajoute un bloc JSON STRICT sur une seule ligne, au format exact :\n"
    '{"orders":[{"action":"BUY","asset":"STOCK:AAPL"},{"action":"SELL","asset":"CRYPTO:BTC"}]}\n'
    "Règles du JSON : uniquement les ordres à exécuter MAINTENANT (BUY/SELL), en utilisant "
    "exactement les identifiants d'actifs fournis dans le contexte (ex. STOCK:AAPL). "
    'Liste vide {"orders":[]} si aucun ordre.'
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

    # Détail technique de CHAQUE position (indicateurs complets du bot)
    try:
        for h in holdings[:8]:
            a = svc.analyze(h["asset"], with_news=False)
            ind = a.indicators or {}
            det = []
            if a.signal:
                det.append(f"signal {a.signal.direction.value} force {a.signal.score:.0f} ({a.signal.reason})")
            if ind.get("rsi") is not None:
                det.append(f"RSI {ind['rsi']:.0f}")
            if ind.get("close") and ind.get("sma50"):
                det.append(f"cours {'>' if ind['close']>ind['sma50'] else '<'} SMA50")
            if ind.get("macd_hist") is not None:
                det.append(f"MACD {'haussier' if ind['macd_hist']>0 else 'baissier'}")
            if ind.get("atr") and ind.get("close"):
                det.append(f"ATR {ind['atr']:.2f} (stop 2xATR ≈ {ind['close']-2*ind['atr']:.2f})")
            parts.append(f"TECHNIQUE {h['asset']}: " + " | ".join(det))
    except Exception:  # noqa: BLE001
        pass

    # Meilleurs candidats du scan (pistes d'achat du bot, classées)
    try:
        top = svc.scan(universe, top=5)
        if top:
            parts.append("MEILLEURS CANDIDATS DU SCAN (bot):")
            for s in top:
                extra = ""
                if s.stop_loss:
                    extra = f" | stop≈{s.stop_loss:.2f} objectif≈{s.take_profit:.2f}"
                parts.append(f"- {s.symbol}: {s.direction.value} force {s.score:.0f} ({s.reason}){extra}")
    except Exception:  # noqa: BLE001
        pass

    # Plus forts mouvements du jour (momentum court terme)
    try:
        movers = svc.movers(universe)
        if movers:
            gain = ", ".join(f"{a} {q.change_pct:+.1f}%" for a, q in movers[:3])
            lose = ", ".join(f"{a} {q.change_pct:+.1f}%" for a, q in movers[-3:])
            parts.append(f"MOVERS JOUR: hausses [{gain}] | baisses [{lose}]")
    except Exception:  # noqa: BLE001
        pass

    # Marché global + régime + risque + saison
    try:
        m = svc.market_trend(universe)
        if m:
            parts.append(f"MARCHÉ: {m.label}, {m.breadth:.0f}% haussiers, score {m.avg_score:+.0f}")
    except Exception:  # noqa: BLE001
        pass
    try:
        from .regime import market_ok_now
        mkt = svc.history("INDEX:^GSPC", period="1y")
        parts.append(f"RÉGIME: {'FAVORABLE (achats permis)' if market_ok_now(mkt) else 'DÉFAVORABLE (S&P<MM200)'}")
    except Exception:  # noqa: BLE001
        pass
    try:
        rc = svc.risk_climate()
        parts.append(f"RISQUE: {rc.label} | {rc.vix_note} | tension géo {rc.geo_score*100:.0f}%")
    except Exception:  # noqa: BLE001
        pass
    try:
        s, _, nh = svc.season()
        hol = f", prochain férié {nh[1]} dans {nh[0]}j" if nh else ""
        parts.append(f"SAISON: biais {s.bias:+.2f}{hol}")
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


def parse_orders(text: str) -> tuple[str, list[dict]]:
    """Extrait le bloc JSON d'ordres de la réponse IA.

    Renvoie (texte_sans_le_json, [{"action": "BUY"/"SELL", "asset": "STOCK:AAPL"}, ...]).
    Tolérant : si pas de JSON valide, renvoie le texte tel quel et une liste vide.
    """
    import json
    import re
    m = None
    for m in re.finditer(r'\{\s*"orders"\s*:\s*\[.*?\]\s*\}', text, re.S):
        pass  # garde la DERNIÈRE occurrence (le bloc final)
    if not m:
        return text.strip(), []
    try:
        data = json.loads(m.group(0))
        orders = []
        for o in data.get("orders", []):
            action = str(o.get("action", "")).upper()
            asset = str(o.get("asset", "")).upper().strip()
            if action in ("BUY", "SELL") and ":" in asset:
                orders.append({"action": action, "asset": asset})
        clean = (text[:m.start()] + text[m.end():]).strip()
        clean = clean.replace("```json", "").replace("```", "").strip()
        return clean, orders
    except Exception:  # noqa: BLE001
        return text.strip(), []


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
