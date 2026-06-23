"""Modèles de données communs à toutes les sources (format normalisé)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Quote:
    """Cotation normalisée, quelle que soit la source."""

    symbol: str
    price: float
    timestamp: datetime          # horodatage de la donnée (UTC) — sert à choisir la + fraîche
    source: str                  # nom de la source d'où vient la donnée
    previous_close: Optional[float] = None
    currency: Optional[str] = None

    @property
    def change(self) -> Optional[float]:
        if self.previous_close is None:
            return None
        return self.price - self.previous_close

    @property
    def change_pct(self) -> Optional[float]:
        if not self.previous_close:
            return None
        return (self.price - self.previous_close) / self.previous_close * 100

    def age_seconds(self) -> float:
        return (now_utc() - self.timestamp).total_seconds()


class Direction(str, Enum):
    BUY = "ACHETER"
    SELL = "VENDRE"
    HOLD = "CONSERVER"


@dataclass
class Signal:
    """Signal produit par le moteur d'analyse."""

    symbol: str
    direction: Direction
    score: float                 # force du signal, 0–100
    reason: str                  # raison principale, courte
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = now_utc()

    @property
    def emoji(self) -> str:
        return {Direction.BUY: "🟢", Direction.SELL: "🔴", Direction.HOLD: "🟡"}[self.direction]
