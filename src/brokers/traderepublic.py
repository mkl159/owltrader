"""Connecteur Trade Republic (API NON OFFICIELLE, via pytr) — LECTURE SEULE.

⚠️ ARGENT RÉEL. API reverse-engineered (peut casser), contraire aux CGU de TR.
Ce connecteur NE FAIT QUE LIRE : cash, positions, prix de revient, valeur totale.
Il NE passe JAMAIS d'ordre (chaque ordre TR exige un 2FA côté serveur, impossible à
automatiser). Tu valides tes ordres toi-même dans l'app — le bot te dit quoi faire.

Login en 2 temps (2FA) : begin_login(phone, pin) -> code reçu par l'app -> finish_login(code).
La session est persistée (cookies), donc pas de 2FA les fois suivantes.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..config import get_secret
from .base import Broker

log = logging.getLogger(__name__)

_COOKIE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "tr_session"


def _run(coro):
    """Exécute une coroutine pytr dans une boucle dédiée (appelé depuis un thread worker)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_api(phone: str | None = None, pin: str | None = None):
    from pytr.api import TradeRepublicApi  # import paresseux (dépendance optionnelle)
    _COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    return TradeRepublicApi(
        phone_no=phone or get_secret("TR_PHONE"),
        pin=pin or get_secret("TR_PIN"),
        locale="fr",
        cookies_file=str(_COOKIE_DIR / "cookies.txt"),
    )


async def _read_one(api, subscribe):
    """Souscrit à un flux, récupère une réponse, se désabonne."""
    sub_id = await subscribe
    try:
        while True:
            rec_id, _, response = await api.recv()
            if rec_id == sub_id:
                return response
    finally:
        try:
            await api.unsubscribe(sub_id)
        except Exception:  # noqa: BLE001
            pass


class TradeRepublicBroker(Broker):
    name = "traderepublic"

    def __init__(self, api=None):
        self.api = api or _make_api()

    # --- Connexion (2FA) ---
    def resume(self) -> bool:
        """Tente de reprendre une session existante (cookies). True si connecté sans 2FA."""
        try:
            self.api.resume_websession()
            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def begin_login(phone: str, pin: str):
        """Déclenche le 2FA. Renvoie (api, countdown) ; countdown à passer à finish_login."""
        api = _make_api(phone, pin)
        countdown = api.inititate_weblogin()  # (orthographe pytr) -> envoie le code 2FA
        return api, countdown

    @staticmethod
    def finish_login(api, countdown, code: str) -> "TradeRepublicBroker":
        api.complete_weblogin(countdown, code)  # valide + persiste la session
        return TradeRepublicBroker(api=api)

    # --- Lecture seule ---
    def get_account(self) -> dict:
        cash_amount = 0.0
        net = 0.0
        try:
            cash = _run(_read_one(self.api, self.api.cash()))
            if isinstance(cash, list) and cash:
                cash_amount = float(cash[0].get("amount", 0) or 0)
        except Exception as e:  # noqa: BLE001
            log.info("TR cash : %s", e)
        try:
            pf = _run(_read_one(self.api, self.api.portfolio()))
            net = float(pf.get("netValue", 0) or 0)
        except Exception as e:  # noqa: BLE001
            log.info("TR portfolio : %s", e)
        return {"cash": cash_amount, "equity": cash_amount + net, "invested": net,
                "currency": "EUR", "status": "Trade Republic (réel · lecture seule)"}

    def get_positions(self) -> list[dict]:
        try:
            pf = _run(_read_one(self.api, self.api.compact_portfolio()))
        except Exception as e:  # noqa: BLE001
            log.info("TR positions : %s", e)
            return []
        out = []
        for p in (pf or {}).get("positions", []):
            out.append({
                "symbol": p.get("instrumentId", "?"),       # ISIN
                "qty": float(p.get("netSize", 0) or 0),
                "avg_entry_price": float(p.get("averageBuyIn", 0) or 0),
                "market_value": 0.0, "unrealized_plpc": 0.0,
            })
        return out

    def submit_order(self, symbol: str, qty: float, side: str):
        raise NotImplementedError(
            "Trade Republic : exécution automatique impossible (2FA obligatoire par ordre, "
            "argent réel). Le bot lit et conseille ; tu passes l'ordre dans l'app TR."
        )
