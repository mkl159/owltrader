"""DataRouter — interroge plusieurs sources et garde TOUJOURS la donnée la plus récente.

Patterns : Chain of Responsibility (repli) + sélection par fraîcheur d'horodatage.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd

from ..collectors.base import DataProvider
from ..models import Quote
from ..symbols import Asset

log = logging.getLogger(__name__)


class DataRouter:
    def __init__(self, providers: list[DataProvider]):
        if not providers:
            raise ValueError("Au moins une source de données est requise.")
        self.providers = providers

    def get_quote(self, asset: Asset) -> Optional[Quote]:
        """Interroge toutes les sources en parallèle et renvoie la cotation la PLUS FRAÎCHE."""
        candidates = [p for p in self.providers if p.supports(asset)]
        quotes: list[Quote] = []

        with ThreadPoolExecutor(max_workers=max(1, len(candidates))) as ex:
            futures = {ex.submit(p.get_quote, asset): p for p in candidates}
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    q = fut.result()
                    if q is not None:
                        quotes.append(q)
                except Exception as e:  # noqa: BLE001
                    log.warning("Source %s en échec pour %s : %s", p.name, asset.raw, e)

        if not quotes:
            return None
        # On retient l'horodatage le plus récent (donnée la plus à jour)
        freshest = max(quotes, key=lambda q: q.timestamp)
        if len(quotes) > 1:
            log.info(
                "%s : %d sources, retenu %s (%s) ; autres : %s",
                asset.raw, len(quotes), freshest.source,
                freshest.timestamp.isoformat(),
                ", ".join(f"{q.source}@{q.timestamp:%H:%M}" for q in quotes if q is not freshest),
            )
        return freshest

    def get_history(self, asset: Asset, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
        """Historique depuis la première source qui répond (repli en cascade)."""
        for p in self.providers:
            if not p.supports(asset):
                continue
            df = p.get_history(asset, period=period, interval=interval)
            if df is not None and not df.empty:
                return df
        return None
