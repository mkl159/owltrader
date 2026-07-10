"""Moteur de trading autonome (live, fictif) — exécute les décisions et applique les frais.

Logique strictement identique au simulateur : on détient un actif tant que la stratégie
le veut, on vend dès qu'elle ne le veut plus, dans la limite de N positions.
"""

from __future__ import annotations

import json
import logging
import math

from ..strategy import position_series
from .fees import courtage

log = logging.getLogger(__name__)

_STRAT_KEYS = ("short", "long", "rsi_entry_max", "rsi_exit")


def strat_params(params: dict | None) -> dict:
    params = params or {}
    return {k: params[k] for k in _STRAT_KEYS if k in params}


# --- Protection des achats IA (anti-bagotement) -----------------------------------
# L'IA (agressive, court terme) et la stratégie de tendance (lente) peuvent se
# contredire : l'IA achète, et au cycle suivant la stratégie revend faute de signal.
# Règle : une position ouverte par l'IA est INTOUCHABLE par le cycle autonome pendant
# `ia_hold_days` jours — seule l'IA (ordre SELL) ou le stop-loss peuvent la fermer.

def _ai_hold_key(scope: str) -> str:
    return f"AI_HOLDINGS_{scope}"


def _ai_holdings(db, scope: str) -> dict:
    """{symbole: date ISO d'achat} des positions ouvertes par l'IA."""
    if db is None:
        return {}
    try:
        raw = db.get_config(_ai_hold_key(scope))
        return json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        return {}


def ai_mark_held(db, scope: str, symbol: str):
    from datetime import datetime, timezone
    if db is None:
        return
    d = _ai_holdings(db, scope)
    d[symbol] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.set_config(_ai_hold_key(scope), json.dumps(d))


def ai_unmark_held(db, scope: str, symbol: str):
    if db is None:
        return
    d = _ai_holdings(db, scope)
    if symbol in d:
        del d[symbol]
        db.set_config(_ai_hold_key(scope), json.dumps(d))


def ai_protected(db, scope: str, paper_cfg: dict) -> set[str]:
    """Symboles encore sous protection IA (achat plus récent que ia_hold_days)."""
    from datetime import datetime, timedelta, timezone
    days = int(paper_cfg.get("ia_hold_days", 7) or 0)
    if days <= 0:
        return set()
    d = _ai_holdings(db, scope)
    now = datetime.now(timezone.utc)
    out = set()
    for sym, ts in d.items():
        try:
            if now - datetime.fromisoformat(ts).replace(tzinfo=timezone.utc) <= timedelta(days=days):
                out.add(sym)
        except ValueError:
            continue
    return out


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

    vt = paper_cfg.get("vol_target", 0) or 0
    rlb = int(paper_cfg.get("rank_lookback", 0) or 0)
    amlb = int(paper_cfg.get("abs_mom_lookback", 0) or 0)
    ammin = paper_cfg.get("abs_mom_min", 0) or 0
    hist = svc.fetch_histories(universe, period="1y")
    wants: dict[str, bool] = {}
    prices: dict[str, float] = {}
    vols: dict[str, float] = {}
    moms: dict[str, float] = {}
    for a, df in hist.items():
        try:
            last_close = float(df["close"].iloc[-1])
            if math.isnan(last_close) or last_close <= 0:
                continue  # cours manquant : on ne décide/trade pas cet actif ce tour-ci
            wants[a] = bool(position_series(df, **sp).iloc[-1])
            prices[a] = last_close
            if vt > 0:
                v = float(df["close"].pct_change().rolling(20).std().iloc[-1]) * (252 ** 0.5)
                if v == v and v > 0:
                    vols[a] = v
            if rlb > 0 and len(df) > rlb:
                m = float(df["close"].iloc[-1] / df["close"].iloc[-1 - rlb] - 1)
                if m == m:
                    moms[a] = m
        except Exception:  # noqa: BLE001
            continue

    sl = paper_cfg.get("stop_loss_pct", 0) / 100.0
    ddp = paper_cfg.get("max_dd_pause", 0) / 100.0

    cash = acc["cash"]
    held = {p["asset"]: p for p in db.paper_positions(chat_id)}
    executed: list[dict] = []
    # Positions ouvertes par l'IA : le cycle ne les revend pas pendant ia_hold_days
    # (anti-bagotement) — mais le STOP-LOSS garde toujours la priorité (risque d'abord).
    protected = ai_protected(db, f"paper_{chat_id}", paper_cfg)

    # --- VENTES : la stratégie n'en veut plus OU stop-loss du risk manager ---
    for a, p in list(held.items()):
        if a not in prices:
            continue
        price = prices[a]
        stop_hit = sl > 0 and price <= p["entry_price"] * (1 - sl)
        if a in protected and not stop_hit:
            continue  # position IA récente : seule l'IA (ou le stop-loss) la ferme
        if not wants.get(a, False) or stop_hit:
            qty = p["quantity"]
            gross = qty * price
            fee = courtage(gross, fee_pct, fee_min)
            cash += gross - fee
            pnl = (price - p["entry_price"]) * qty - fee - p["entry_fee"]
            db.paper_remove_position(chat_id, a)
            db.paper_record_trade(chat_id, a, "VENTE", qty, price, fee, pnl)
            ai_unmark_held(db, f"paper_{chat_id}", a)
            executed.append({"side": "VENTE", "asset": a, "quantity": qty, "price": price,
                             "fee": fee, "pnl": pnl,
                             "motif": "stop-loss" if stop_hit else "signal"})
            del held[a]

    # --- Coupe-circuit + filtre de régime : conditions de pause des achats ---
    equity_now = cash + sum(held[a]["quantity"] * prices[a] for a in held if a in prices)
    paused = False
    if ddp > 0:
        curve = [e for _, e in db.paper_equity_curve(chat_id)]
        peak = max(curve + [equity_now, acc["capital"]])
        paused = equity_now < peak * (1 - ddp)
    if not paused and paper_cfg.get("regime_filter"):
        from ..regime import market_ok_now
        mkt = hist.get(paper_cfg.get("regime_symbol", "INDEX:^GSPC"))
        if mkt is not None and not market_ok_now(mkt):
            paused = True  # marché global baissier : on n'ouvre pas de position

    # --- ACHATS : on prend ce que la stratégie veut, dans la limite des slots/cash ---
    free = 0 if paused else max_pos - len(held)
    cands = [a for a in universe if wants.get(a) and a not in held and a in prices]
    if amlb > 0:  # momentum absolu : on écarte les actifs en baisse sur ~6 mois
        def _abs_mom(a):
            df = hist.get(a)
            if df is None or len(df) <= amlb:
                return None
            return float(df["close"].iloc[-1] / df["close"].iloc[-1 - amlb] - 1)
        cands = [a for a in cands if (_abs_mom(a) is not None and _abs_mom(a) >= ammin)]
    if rlb > 0:  # classe par momentum relatif : les plus forts d'abord
        cands.sort(key=lambda a: moms.get(a, -9e9), reverse=True)
    for a in cands[: max(0, free)]:
        base = equity_now * alloc / 100.0
        if vt > 0 and a in vols:
            base *= min(1.5, max(0.5, vt / vols[a]))  # moins sur les actifs volatils
        target = min(base, cash - fee_min)
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


def execute_orders(db, svc, chat_id: int, orders: list[dict], paper_cfg: dict,
                   universe: list[str]) -> list[dict]:
    """Exécute les ordres du conseiller IA sur le compte fictif (frais inclus).

    Garde-fous : actifs connus uniquement (univers ou positions), respect du cash,
    du nombre max de positions et des frais — comme le mode autonome.
    """
    from ..symbols import Asset
    acc = db.paper_get(chat_id)
    if not acc or not acc.get("active") or not orders:
        return []
    fee_pct = paper_cfg.get("frais_pct", 0.20)
    fee_min = paper_cfg.get("frais_min", 1.0)
    max_pos = int(paper_cfg.get("max_positions", 5))
    alloc = paper_cfg.get("alloc_pct", 20)

    cash = acc["cash"]
    held = {p["asset"]: p for p in db.paper_positions(chat_id)}
    known = set(universe) | set(held)
    executed: list[dict] = []

    # 1) VENTES d'abord (libèrent du cash pour les achats)
    for o in [o for o in orders if o["action"] == "SELL"]:
        asset = Asset.parse(o["asset"]).raw
        p = held.get(asset)
        if not p:
            continue
        q = svc.quote(asset)
        if q is None or not (q.price == q.price) or q.price <= 0:
            continue
        qty, price = p["quantity"], q.price
        gross = qty * price
        fee = courtage(gross, fee_pct, fee_min)
        cash += gross - fee
        pnl = (price - p["entry_price"]) * qty - fee - p["entry_fee"]
        db.paper_remove_position(chat_id, asset)
        db.paper_record_trade(chat_id, asset, "VENTE", qty, price, fee, pnl)
        ai_unmark_held(db, f"paper_{chat_id}", asset)
        executed.append({"side": "VENTE", "asset": asset, "quantity": qty, "price": price,
                         "fee": fee, "pnl": pnl, "motif": "ordre IA"})
        del held[asset]

    # 2) ACHATS (une seule cotation par actif détenu)
    equity_now = cash
    for a, p in held.items():
        q = svc.quote(a)
        price = q.price if (q and q.price == q.price) else p["entry_price"]
        equity_now += p["quantity"] * price
    for o in [o for o in orders if o["action"] == "BUY"]:
        asset = Asset.parse(o["asset"]).raw
        if asset in held or len(held) >= max_pos:
            continue
        q = svc.quote(asset)
        if q is None or not (q.price == q.price) or q.price <= 0:
            continue  # actif non cotable (ticker inventé/illiquide) -> ignoré
        discovered = asset not in known
        if discovered:
            # Découverte IA (via actus) : on l'ajoute à l'univers pour que le bot
            # le suive ensuite (stop-loss, signaux de vente, surveillance).
            db.add_to_universe(asset)
            known.add(asset)
        target = min(equity_now * alloc / 100.0, cash - fee_min)
        if target < 10:
            continue
        price = q.price
        gross = target / (1 + fee_pct / 100.0)
        fee = courtage(gross, fee_pct, fee_min)
        if gross + fee > cash:
            gross = cash - fee
        if gross < 10:
            continue
        qty = gross / price
        cash -= gross + fee
        db.paper_add_position(chat_id, asset, qty, price, fee)
        db.paper_record_trade(chat_id, asset, "ACHAT", qty, price, fee, 0.0)
        ai_mark_held(db, f"paper_{chat_id}", asset)
        executed.append({"side": "ACHAT", "asset": asset, "quantity": qty, "price": price,
                         "fee": fee, "pnl": 0.0,
                         "motif": "découverte IA (actus)" if discovered else "ordre IA"})
        held[asset] = {"quantity": qty, "entry_price": price, "entry_fee": fee}

    db.paper_set_cash(chat_id, cash)
    return executed


def execute_orders_alpaca(broker, svc, orders: list[dict], paper_cfg: dict,
                          db=None) -> list[dict]:
    """Exécute les ordres du conseiller IA sur le compte Alpaca (paper ou live).

    L'IA peut proposer n'importe quel actif ; seuls ceux tradables chez Alpaca (actions US
    + crypto) sont exécutés. Les autres (Paris, indices…) sont ignorés proprement.
    Chaque ACHAT est marqué « position IA » : le cycle autonome ne pourra pas la revendre
    pendant ia_hold_days (anti-bagotement) ; un SELL de l'IA lève la protection.
    """
    from ..brokers.alpaca import to_alpaca_symbol
    alloc = paper_cfg.get("alloc_pct", 20)
    acc = broker.get_account()
    equity, cash = acc.get("equity", 0.0), acc.get("cash", 0.0)
    positions = {p["symbol"]: p for p in broker.get_positions()}
    pending = set(broker.get_open_orders()) if hasattr(broker, "get_open_orders") else set()
    executed: list[dict] = []

    for o in [x for x in orders if x["action"] == "SELL"]:
        sym = to_alpaca_symbol(o["asset"])
        if not sym or sym not in positions or sym in pending:
            continue
        try:
            broker.submit_order(sym, abs(positions[sym]["qty"]), "sell")
            ai_unmark_held(db, "alpaca", sym)
            executed.append({"side": "VENTE", "asset": sym, "quantity": positions[sym]["qty"],
                             "price": positions[sym].get("avg_entry_price", 0), "fee": 0.0,
                             "pnl": 0.0, "motif": "ordre IA"})
        except Exception as e:  # noqa: BLE001
            log.warning("Alpaca IA vente %s : %s", sym, e)

    for o in [x for x in orders if x["action"] == "BUY"]:
        sym = to_alpaca_symbol(o["asset"])
        if not sym or sym in positions or sym in pending or cash < 5:
            continue
        q = svc.quote(o["asset"])
        if q is None or not (q.price == q.price) or q.price <= 0:
            continue
        qty = round(min(equity * alloc / 100.0, cash * 0.98) / q.price, 6)
        if qty <= 0:
            continue
        try:
            broker.submit_order(sym, qty, "buy")
            ai_mark_held(db, "alpaca", sym)
            cash -= qty * q.price
            executed.append({"side": "ACHAT", "asset": sym, "quantity": qty, "price": q.price,
                             "fee": 0.0, "pnl": 0.0, "motif": "ordre IA"})
        except Exception as e:  # noqa: BLE001
            log.warning("Alpaca IA achat %s : %s", sym, e)
    return executed


def run_broker_cycle(broker, svc, universe: list[str], paper_cfg: dict, params: dict,
                     db=None) -> list[dict]:
    """Applique la stratégie du bot sur un VRAI broker (Alpaca) : achète/vend en autonome.

    Mêmes règles que le mode autonome interne (`run_cycle`) : décision de tendance,
    filtre de régime (S&P > MM200), momentum absolu (Antonacci) et surtout CLASSEMENT
    par momentum relatif — indispensable quand l'univers est large (S&P 500) : on achète
    les plus FORTES, pas les premières dans l'ordre. Exécution via l'API du broker
    (compte paper gratuit ou live).
    """
    import math

    from ..brokers.alpaca import to_alpaca_symbol
    from ..strategy import position_series
    max_pos = int(params.get("max_positions", paper_cfg.get("max_positions", 5)))
    alloc = params.get("alloc_pct", paper_cfg.get("alloc_pct", 20))
    sp = {k: params[k] for k in ("short", "long", "rsi_entry_max", "rsi_exit") if k in params}
    vt = paper_cfg.get("vol_target", 0) or 0
    rlb = int(paper_cfg.get("rank_lookback", 0) or 0)
    amlb = int(paper_cfg.get("abs_mom_lookback", 0) or 0)
    ammin = paper_cfg.get("abs_mom_min", 0) or 0

    acc = broker.get_account()
    equity = acc.get("equity", 0.0)
    cash = acc.get("cash", 0.0)
    positions = {p["symbol"]: p for p in broker.get_positions()}
    pending = set(broker.get_open_orders()) if hasattr(broker, "get_open_orders") else set()

    # Récupération parallèle de tout l'univers tradable (rapide même sur 500 actions).
    tradable = [raw for raw in universe if to_alpaca_symbol(raw)]
    hist = svc.fetch_histories(tradable, period="1y")

    # Décisions + métriques (momentum relatif/absolu, volatilité) par actif.
    wants: dict[str, str] = {}      # symbole broker -> actif interne
    prices: dict[str, float] = {}
    vols: dict[str, float] = {}
    moms: dict[str, float] = {}
    for raw, df in hist.items():
        sym = to_alpaca_symbol(raw)
        if not sym or df is None or len(df) < 2:
            continue
        try:
            last = float(df["close"].iloc[-1])
            if math.isnan(last) or last <= 0:
                continue
            prices[sym] = last
            if bool(position_series(df, **sp).iloc[-1]):
                wants[sym] = raw
            if vt > 0:
                v = float(df["close"].pct_change().rolling(20).std().iloc[-1]) * (252 ** 0.5)
                if v == v and v > 0:
                    vols[sym] = v
            if rlb > 0 and len(df) > rlb:
                m = float(df["close"].iloc[-1] / df["close"].iloc[-1 - rlb] - 1)
                if m == m:
                    moms[sym] = m
        except Exception:  # noqa: BLE001
            continue

    # Filtre de régime : marché global baissier -> on n'ouvre plus de position.
    paused = False
    if paper_cfg.get("regime_filter"):
        from ..regime import market_ok_now
        mkt = svc.history(paper_cfg.get("regime_symbol", "INDEX:^GSPC"), period="2y")
        if mkt is not None and not market_ok_now(mkt):
            paused = True

    executed: list[dict] = []
    # Positions ouvertes par l'IA : intouchables pendant ia_hold_days (anti-bagotement).
    protected = ai_protected(db, "alpaca", paper_cfg)
    # VENTES : positions détenues que la stratégie ne veut plus (et sans ordre en attente).
    for sym, p in positions.items():
        if sym in protected:
            continue  # position IA récente : seule l'IA décide de la vendre
        if sym not in wants and sym not in pending:
            try:
                broker.submit_order(sym, abs(p["qty"]), "sell")
                ai_unmark_held(db, "alpaca", sym)   # protection expirée : on nettoie
                executed.append({"side": "VENTE", "asset": sym, "quantity": p["qty"],
                                 "price": p.get("avg_entry_price", 0), "fee": 0.0,
                                 "pnl": 0.0, "motif": "broker"})
            except Exception as e:  # noqa: BLE001
                log.warning("Alpaca vente %s : %s", sym, e)

    # ACHATS : candidats voulus, filtrés momentum absolu, CLASSÉS par momentum relatif.
    free = 0 if paused else max_pos - len(positions)
    cands = [s for s in wants if s not in positions and s not in pending and s in prices]
    if amlb > 0:
        def _abs_mom(sym):
            df = hist.get(wants[sym])
            if df is None or len(df) <= amlb:
                return None
            return float(df["close"].iloc[-1] / df["close"].iloc[-1 - amlb] - 1)
        cands = [s for s in cands if (_abs_mom(s) is not None and _abs_mom(s) >= ammin)]
    if rlb > 0:  # les plus fortes d'abord
        cands.sort(key=lambda s: moms.get(s, -9e9), reverse=True)

    for sym in cands[: max(0, free)]:
        if cash < 5:
            break
        price = prices[sym]
        base = equity * alloc / 100.0
        if vt > 0 and sym in vols:
            base *= min(1.5, max(0.5, vt / vols[sym]))   # moins sur les actifs volatils
        target = min(base, cash * 0.98)
        qty = round(target / price, 6)
        if qty <= 0:
            continue
        try:
            broker.submit_order(sym, qty, "buy")
            cash -= qty * price
            executed.append({"side": "ACHAT", "asset": sym, "quantity": qty,
                             "price": price, "fee": 0.0, "pnl": 0.0, "motif": "broker"})
        except Exception as e:  # noqa: BLE001
            log.warning("Alpaca achat %s : %s", sym, e)
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
        price = q.price if (q and not math.isnan(q.price)) else p["entry_price"]
        v = p["quantity"] * price
        value += v
        pnl_pct = ((price - p["entry_price"]) / p["entry_price"] * 100) if p["entry_price"] else None
        holdings.append({"asset": p["asset"], "value": v, "pnl_pct": pnl_pct})
    return acc, acc["cash"] + value, holdings
