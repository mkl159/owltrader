"""Moteur de trading autonome (live, fictif) — exécute les décisions et applique les frais.

Logique strictement identique au simulateur : on détient un actif tant que la stratégie
le veut, on vend dès qu'elle ne le veut plus, dans la limite de N positions.
"""

from __future__ import annotations

import json
import logging

from ..strategy import position_series
from .fees import courtage

log = logging.getLogger(__name__)

_STRAT_KEYS = ("short", "long", "rsi_entry_max", "rsi_exit")


def strat_params(params: dict | None) -> dict:
    params = params or {}
    return {k: params[k] for k in _STRAT_KEYS if k in params}


def run_cycle(db, svc, chat_id: int, universe: list[str], paper_cfg: dict) -> list[dict]:
    """Exécute un cycle de décision pour un compte. Renvoie la liste des trades effectués."""
    acc = db.paper_get(chat_id)
    if not acc or not acc.get("active"):
        return []
    params = json.loads(acc["params"]) if acc.get("params") else {}
    sp = strat_params(params)
    fee_pct = paper_cfg.get("frais_pct", 0.20)
    fee_min = paper_cfg.get("frais_min", 1.0)
    # max_positions / alloc viennent du profil d'agressivité ou de l'auto-tuning (params),
    # sinon de la config par défaut.
    max_pos = int(params.get("max_positions", paper_cfg.get("max_positions", 5)))
    alloc = params.get("alloc_pct", paper_cfg.get("alloc_pct", 20))

    hist = svc.fetch_histories(universe, period="1y")
    wants: dict[str, bool] = {}
    prices: dict[str, float] = {}
    for a, df in hist.items():
        try:
            wants[a] = bool(position_series(df, **sp).iloc[-1])
            prices[a] = float(df["close"].iloc[-1])
        except Exception:  # noqa: BLE001
            continue

    cash = acc["cash"]
    held = {p["asset"]: p for p in db.paper_positions(chat_id)}
    executed: list[dict] = []

    # --- VENTES : on solde ce que la stratégie ne veut plus ---
    for a, p in list(held.items()):
        if a not in prices:
            continue
        if not wants.get(a, False):
            price = prices[a]
            qty = p["quantity"]
            gross = qty * price
            fee = courtage(gross, fee_pct, fee_min)
            cash += gross - fee
            pnl = (price - p["entry_price"]) * qty - fee - p["entry_fee"]
            db.paper_remove_position(chat_id, a)
            db.paper_record_trade(chat_id, a, "VENTE", qty, price, fee, pnl)
            executed.append({"side": "VENTE", "asset": a, "quantity": qty,
                             "price": price, "fee": fee, "pnl": pnl})
            del held[a]

    # --- ACHATS : on prend ce que la stratégie veut, dans la limite des slots/cash ---
    free = max_pos - len(held)
    equity_now = cash + sum(held[a]["quantity"] * prices[a] for a in held if a in prices)
    cands = [a for a in universe if wants.get(a) and a not in held and a in prices]
    for a in cands[: max(0, free)]:
        target = min(equity_now * alloc / 100.0, cash - fee_min)
        if target < 10:
            continue
        price = prices[a]
        gross = target / (1 + fee_pct / 100.0)
        fee = courtage(gross, fee_pct, fee_min)
        if gross + fee > cash:
            gross = cash - fee
        if gross < 10:
            continue
        qty = gross / price
        cash -= gross + fee
        db.paper_add_position(chat_id, a, qty, price, fee)
        db.paper_record_trade(chat_id, a, "ACHAT", qty, price, fee, 0.0)
        executed.append({"side": "ACHAT", "asset": a, "quantity": qty,
                         "price": price, "fee": fee, "pnl": 0.0})

    db.paper_set_cash(chat_id, cash)
    return executed


def account_state(db, svc, chat_id: int):
    """Renvoie (compte, équity courante, positions valorisées)."""
    acc = db.paper_get(chat_id)
    if not acc:
        return None, 0.0, []
    holdings = []
    value = 0.0
    for p in db.paper_positions(chat_id):
        q = svc.quote(p["asset"])
        price = q.price if q else p["entry_price"]
        v = p["quantity"] * price
        value += v
        pnl_pct = ((price - p["entry_price"]) / p["entry_price"] * 100) if p["entry_price"] else None
        holdings.append({"asset": p["asset"], "value": v, "pnl_pct": pnl_pct})
    return acc, acc["cash"] + value, holdings
