"""Interface commune à toutes les sources de données (pattern Strategy/Adapter)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from ..models import Quote
from ..symbols import Asset


class DataProvider(ABC):
    """Une source de données de marché. Chaque source l'implémente."""

    name: str = "base"

    @abstractmethod
    def get_quote(self, asset: Asset) -> Optional[Quote]:
        """Dernière cotation, ou None si indisponible."""

    @abstractmethod
    def get_history(
        self, asset: Asset, period: str = "6mo", interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """Historique OHLCV normalisé : colonnes open/high/low/close/volume, index daté UTC."""

    def supports(self, asset: Asset) -> bool:
        """La source sait-elle traiter cet actif ?"""
        return True
