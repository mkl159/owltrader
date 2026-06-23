"""Gestion des identifiants d'actifs au format CLASSE:SYMBOLE.

Exemples : STOCK:AAPL, INDEX:^FCHI, CRYPTO:BTC, FX:EURUSD, COMMO:GOLD
"""

from __future__ import annotations

from dataclasses import dataclass

# Correspondances pratiques vers les symboles Yahoo Finance
_COMMO_YF = {"GOLD": "GC=F", "SILVER": "SI=F", "OIL": "CL=F", "GAS": "NG=F"}


@dataclass
class Asset:
    raw: str          # ex. "STOCK:AAPL"
    klass: str        # STOCK, INDEX, CRYPTO, FX, COMMO
    symbol: str       # ex. "AAPL"

    @classmethod
    def parse(cls, raw: str) -> "Asset":
        raw = raw.strip().upper()
        if ":" in raw:
            klass, symbol = raw.split(":", 1)
        else:
            klass, symbol = "STOCK", raw
        return cls(raw=f"{klass}:{symbol}", klass=klass, symbol=symbol)

    @property
    def yahoo_symbol(self) -> str:
        """Symbole tel qu'attendu par Yahoo Finance / yfinance."""
        if self.klass == "CRYPTO":
            return f"{self.symbol}-USD"
        if self.klass == "FX":
            return f"{self.symbol}=X"
        if self.klass == "COMMO":
            return _COMMO_YF.get(self.symbol, self.symbol)
        return self.symbol  # STOCK, INDEX

    @property
    def stooq_symbol(self) -> str | None:
        """Symbole Stooq (repli). None si non pris en charge simplement."""
        if self.klass == "STOCK":
            # Stooq attend généralement le suffixe marché ; .us par défaut
            if "." in self.symbol:
                return self.symbol.lower()
            return f"{self.symbol.lower()}.us"
        if self.klass == "FX":
            return self.symbol.lower()
        return None

    def label(self) -> str:
        return f"{self.symbol} ({self.klass.lower()})"
