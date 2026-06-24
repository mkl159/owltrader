"""Interface commune des brokers (pattern Strategy)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Broker(ABC):
    name: str = "base"

    @abstractmethod
    def get_account(self) -> dict:
        """-> {cash, equity, currency, status}"""

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """-> [{symbol, qty, avg_entry_price, market_value, unrealized_plpc}]"""

    @abstractmethod
    def submit_order(self, symbol: str, qty: float, side: str) -> dict:
        """Passe un ordre marché. side = 'buy' ou 'sell'."""
