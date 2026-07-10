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
    "IMPORTANT — CHASSE GLOBALE : tu n'es PAS limité à la liste d'actifs fournie. "
    "Exploite les ACTUS (titres RSS) et ta connaissance du marché pour proposer N'IMPORTE "
    "QUELLE action liquide (US/Europe) ou grande crypto à fort potentiel de gain court terme : "
    "résultats explosifs, annonces, momentum d'actualité, rotations sectorielles. "
    "Utilise le format STOCK:TICKER (ex. STOCK:PLTR, STOCK:AIR.PA) ou CRYPTO:SYMBOLE — "
    "le bot pourra les acheter et les suivre automatiquement.\n"
    "Réponds en FRANÇAIS, format strict et actionnable :\n"
    "1) 📌 ORDRES DU JOUR — liste numérotée : ACHETER X / VENDRE X / RENFORCER X / GARDER X. "
    "Pour chaque ordre : raison courte (1 ligne) + niveau de stop conseillé + objectif court terme.\n"
    "2) 🔍 DÉCOUVERTES HORS LISTE — 1 à 3 actifs PAS dans la liste fournie, repérés via "
    "l'actualité, avec le meilleur potentiel de gain rapide (raison + niveau d'entrée).\n"
    "3) 🚀 MEILLEUR COUP COURT TERME — LA meilleure opportunité de gain rapide du moment "
    "(liste ou découverte), avec entrée/stop/objectif chiffrés.\n"
    "4) ⚡ STRATÉGIE DU JOUR — 2 phrases max, agressives et concrètes.\n"
    "5) 🤝 PLAN 24H POUR LE ROBOT — tu es le CHEF DE DESK d'un robot de trading autonome qui "
    "tourne TOUTES LES HEURES pendant les prochaines 24h (stratégie tendance+momentum, il "
    "achète les plus fortes du S&P 500). Donne-lui ses consignes : biais général "
    "(agressif = déployer / défensif = aucun nouvel achat), actifs à PRIVILÉGIER en tête de "
    "ses achats, actifs à ÉVITER absolument, et une consigne d'une phrase.\n"
    "Sois tranché : évite les « peut-être ». Si le contexte est mauvais, dis clairement "
    "VENDRE ou RESTER LIQUIDE.\n"
    "Termine par : « ⚠️ Avis IA, pas un conseil financier. »\n"
    "PUIS, tout à la fin, ajoute un bloc JSON STRICT sur une seule ligne, au format exact :\n"
    '{"orders":[{"action":"BUY","asset":"STOCK:AAPL"}],'
    '"plan":{"bias":"agressif","focus":["STOCK:NVDA"],"eviter":["STOCK:TSLA"],'
    '"note":"consigne d\'une phrase pour le robot"}}\n'
    "Règles du JSON : orders = uniquement les ordres à exécuter MAINTENANT (BUY/SELL) ; "
    "plan = tes consignes que le robot APPLIQUERA automatiquement à chaque cycle horaire "
    "pendant 24h (bias: agressif|neutre|defensif ; focus/eviter: identifiants exacts "
    "type STOCK:XXX ou CRYPTO:XXX, listes vides acceptées). "
    'Format minimal si rien : {"orders":[],"plan":{"bias":"neutre","focus":[],"eviter":[],"note":""}}.'
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


# --- Quota : 1 requête / jour pour la consultation AUTOMATIQUE (économie de tokens) ---
def can_call(db) -> bool:
    last = db.get_config("AI_LAST_CALL")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return last != today


def record_call(db):
    db.set_config("AI_LAST_CALL", datetime.now(timezone.utc).strftime("%Y-%m-%d"))


# --- Demande MANUELLE (bouton) : illimitée, mais protégée d'un double-clic accidentel ---
MANUAL_COOLDOWN_S = 45


def manual_ready(db) -> bool:
    """True si on peut relancer une demande manuelle (anti-double-clic, pas une limite/jour)."""
    import time
    last = db.get_config("AI_LAST_MANUAL")
    if not last:
        return True
    try:
        return (time.time() - float(last)) >= MANUAL_COOLDOWN_S
    except ValueError:
        return True


def record_manual(db):
    import time
    db.set_config("AI_LAST_MANUAL", str(time.time()))


def build_context(svc, db, chat_id: int, universe: list[str]) -> str:
    """Agrège tout le contexte utile en un texte compact pour le modèle."""
    from .config import CONFIG
    from .paper import trader
    parts: list[str] = []

    # Mode d'exécution + COÛTS de transaction (l'IA doit raisonner frais inclus)
    pc = CONFIG.get("paper", {})
    fee_pct = pc.get("frais_pct", 0.20)
    fee_min = pc.get("frais_min", 1.0)
    dev = pc.get("devise", "EUR")
    parts.append(
        "MODE D'EXÉCUTION: SIMULATEUR paper-trading interne (argent fictif). "
        "Tes ordres BUY/SELL y seront exécutés automatiquement si l'utilisateur l'a activé."
    )
    parts.append(
        f"COÛTS DE TRANSACTION: {fee_pct}% par ordre avec minimum {fee_min:.2f} {dev}, "
        f"payés à l'ACHAT ET à la VENTE (aller-retour ≈ {2*fee_pct}% ou 2x{fee_min:.2f} {dev} minimum). "
        "Un aller-retour n'est rentable que si le gain attendu dépasse ces frais : évite le sur-trading."
    )
    parts.append(
        f"RÈGLES DE DIMENSIONNEMENT: max {pc.get('max_positions', 5)} positions simultanées, "
        f"≈{pc.get('alloc_pct', 20)}% du capital par position (ajusté volatilité), "
        f"stop-loss automatique du bot à -{pc.get('stop_loss_pct', 25)}%."
    )
    parts.append(
        "TON RÔLE DE CHEF DE DESK: le robot autonome tourne toutes les heures (tendance+momentum "
        "sur le S&P 500). TON plan 24h le pilote : bias defensif = il n'ouvre AUCUN nouvel achat ; "
        "focus = il achète ces actifs EN PRIORITÉ ; eviter = il ne les achètera pas. "
        f"Tes achats (orders) sont protégés {pc.get('ia_hold_days', 7)} jours : le robot ne peut "
        "pas les revendre, TOI seul peux les vendre (ordre SELL) — gère-les activement."
    )
    try:
        prev = current_plan(db)
        if prev:
            parts.append(
                f"TON PLAN ACTUEL (émis {prev.get('ts', '?')[:16]}, à renouveler/ajuster): "
                f"bias={prev.get('bias')}, focus={prev.get('focus')}, eviter={prev.get('eviter')}, "
                f"note={prev.get('note')!r}"
            )
        mine = trader._ai_holdings(db, "alpaca") or trader._ai_holdings(db, f"paper_{chat_id}")
        if mine:
            parts.append("POSITIONS OUVERTES PAR TOI (protégées, à toi de les gérer/vendre): "
                         + ", ".join(f"{s} (achat {d})" for s, d in mine.items()))
    except Exception:  # noqa: BLE001
        pass

    # Positions & compte
    acc, equity, holdings = trader.account_state(db, svc, chat_id)
    if acc:
        parts.append(f"COMPTE (fictif): total {equity:.2f} {acc.get('devise','EUR')}, "
                     f"cash disponible {acc['cash']:.2f}, capital initial {acc['capital']:.0f}")
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
        from .macro import macro_regime, macro_summary_line
        line = macro_summary_line(macro_regime(svc))
        if line:
            parts.append(line)
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


def parse_orders(text: str) -> tuple[str, list[dict], dict | None]:
    """Extrait le bloc JSON (ordres + plan 24h) de la réponse IA.

    Renvoie (texte_sans_le_json, ordres, plan|None) où plan =
    {"bias": "agressif|neutre|defensif", "focus": [...], "eviter": [...], "note": "..."}.
    Tolérant : si pas de JSON valide, renvoie le texte tel quel, [] et None.
    """
    import json
    import re
    matches = list(re.finditer(
        r'\{\s*"orders"\s*:\s*\[.*?\]\s*(?:,\s*"plan"\s*:\s*\{.*?\}\s*)?\}', text, re.S))
    if not matches:
        return text.strip(), [], None
    m = matches[-1]  # garde la DERNIÈRE occurrence (le bloc final)
    try:
        data = json.loads(m.group(0))
        orders = []
        for o in data.get("orders", []):
            action = str(o.get("action", "")).upper()
            asset = str(o.get("asset", "")).upper().strip()
            if action in ("BUY", "SELL") and ":" in asset:
                orders.append({"action": action, "asset": asset})
        plan = None
        p = data.get("plan")
        if isinstance(p, dict):
            bias = str(p.get("bias", "neutre")).lower()
            plan = {
                "bias": bias if bias in ("agressif", "neutre", "defensif") else "neutre",
                "focus": [str(a).upper().strip() for a in p.get("focus", []) if ":" in str(a)],
                "eviter": [str(a).upper().strip() for a in p.get("eviter", []) if ":" in str(a)],
                "note": str(p.get("note", ""))[:300],
            }
        clean = (text[:m.start()] + text[m.end():]).strip()
        clean = clean.replace("```json", "").replace("```", "").strip()
        return clean, orders, plan
    except Exception:  # noqa: BLE001
        return text.strip(), [], None


# --- Plan de trade 24h : l'IA guide le cycle autonome (osmose stratège/exécutant) ---
def save_plan(db, plan: dict):
    """Enregistre le plan IA (avec horodatage) — le cycle autonome l'appliquera 24h."""
    import json
    plan = dict(plan)
    plan["ts"] = datetime.now(timezone.utc).isoformat()
    db.set_config("AI_PLAN", json.dumps(plan, ensure_ascii=False))


def current_plan(db) -> dict | None:
    """Plan IA encore valide (moins de 24h), sinon None."""
    import json
    from datetime import timedelta
    raw = db.get_config("AI_PLAN") if db is not None else None
    if not raw:
        return None
    try:
        plan = json.loads(raw)
        ts = datetime.fromisoformat(plan.get("ts", ""))
        if datetime.now(timezone.utc) - ts > timedelta(hours=24):
            return None
        return plan
    except Exception:  # noqa: BLE001
        return None


def plan_summary(plan: dict | None) -> str:
    """Résumé lisible du plan pour Telegram ('' si aucun plan actif)."""
    if not plan:
        return ""
    ic = {"agressif": "🔥", "neutre": "⚖️", "defensif": "🛡️"}.get(plan.get("bias", ""), "⚖️")
    out = [f"{ic} Biais : *{plan.get('bias', 'neutre')}*"]
    if plan.get("focus"):
        out.append("🎯 Privilégier : " + ", ".join(plan["focus"][:6]))
    if plan.get("eviter"):
        out.append("🚫 Éviter : " + ", ".join(plan["eviter"][:6]))
    if plan.get("note"):
        out.append(f"🗒️ « {plan['note']} »")
    return "\n".join(out)


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
