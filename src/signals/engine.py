"""Scoring multi-critères → ACHETER / VENDRE / CONSERVER, avec gestion du risque."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from ..config import CONFIG
from ..indicators import compute_indicators
from ..models import Direction, Signal


def analyze(symbol: str, df: pd.DataFrame, cfg: dict | None = None,
            sentiment: float | None = None) -> Optional[Signal]:
    """Analyse un historique OHLCV et renvoie un Signal (ou None si trop peu de données).

    sentiment : score d'actu dans [-1, 1] (optionnel) — pondère légèrement la décision.
    """
    if df is None or len(df) < 30:
        return None
    cfg = (cfg or CONFIG).get("signaux", {})
    ind = compute_indicators(df)
    price = ind["close"]
    if price is None:
        return None

    # --- Vote pondéré : chaque critère pousse vers l'achat (+) ou la vente (-) ---
    votes: list[tuple[float, str]] = []

    # Sentiment des actualités (poids modéré)
    if sentiment is not None and abs(sentiment) > 0.15:
        w = round(sentiment * 1.5, 2)
        mood = "actus positives" if sentiment > 0 else "actus négatives"
        votes.append((w, mood))

    rsi = ind["rsi"]
    if rsi is not None:
        if rsi < cfg.get("rsi_survente", 30):
            votes.append((2.0, f"RSI en survente ({rsi:.0f})"))
        elif rsi > cfg.get("rsi_surachat", 70):
            votes.append((-2.0, f"RSI en surachat ({rsi:.0f})"))

    if ind["macd_cross_up"]:
        votes.append((1.5, "croisement MACD haussier"))
    if ind["macd_cross_down"]:
        votes.append((-1.5, "croisement MACD baissier"))
    elif ind["macd"] is not None and ind["macd_signal"] is not None:
        votes.append((0.5 if ind["macd"] > ind["macd_signal"] else -0.5, "MACD"))

    if ind["golden_cross"]:
        votes.append((2.5, "golden cross (SMA50 > SMA200)"))
    if ind["death_cross"]:
        votes.append((-2.5, "death cross (SMA50 < SMA200)"))

    # Tendance de fond
    if ind["sma200"] is not None:
        votes.append((0.8 if price > ind["sma200"] else -0.8, "position vs SMA200"))
    if ind["sma50"] is not None:
        votes.append((0.5 if price > ind["sma50"] else -0.5, "position vs SMA50"))

    # Bandes de Bollinger (retour à la moyenne)
    if ind["boll_lower"] and price <= ind["boll_lower"]:
        votes.append((1.0, "sous la bande de Bollinger basse"))
    if ind["boll_upper"] and price >= ind["boll_upper"]:
        votes.append((-1.0, "au-dessus de la bande de Bollinger haute"))

    raw = sum(w for w, _ in votes)
    # Normalisation en score 0–100 (50 = neutre)
    score = max(0.0, min(100.0, 50 + raw * 8))

    if raw >= 2.5:
        direction = Direction.BUY
    elif raw <= -2.5:
        direction = Direction.SELL
    else:
        direction = Direction.HOLD

    # Raison principale = le vote de plus fort poids dans le sens du signal
    reason = _main_reason(votes, direction)

    # --- Gestion du risque : stop via ATR, take-profit via ratio R/R ---
    stop = tp = rr = None
    atr = ind.get("atr")
    if atr and direction == Direction.BUY:
        k = cfg.get("atr_multiplicateur_stop", 2.0)
        rr_target = cfg.get("ratio_risque_rendement_min", 1.5)
        stop = price - k * atr
        tp = price + k * atr * rr_target
        rr = rr_target

    return Signal(
        symbol=symbol, direction=direction, score=round(score, 1), reason=reason,
        price=price, stop_loss=stop, take_profit=tp, risk_reward=rr,
    )


def _main_reason(votes, direction) -> str:
    if not votes:
        return "configuration neutre"
    if direction == Direction.BUY:
        rel = [v for v in votes if v[0] > 0] or votes
        return max(rel, key=lambda v: v[0])[1]
    if direction == Direction.SELL:
        rel = [v for v in votes if v[0] < 0] or votes
        return min(rel, key=lambda v: v[0])[1]
    return "signaux contradictoires, pas de tendance nette"
