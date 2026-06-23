"""Profils d'agressivité : règlent le dimensionnement et la réactivité de la stratégie."""

from __future__ import annotations

# Chaque profil = paramètres de stratégie + gestion du risque
AGRESSIVITES: dict[str, dict] = {
    "prudent": {
        "max_positions": 3, "alloc_pct": 15,
        "short": 20, "long": 100, "rsi_entry_max": 65, "rsi_exit": 78,
    },
    "normale": {
        "max_positions": 5, "alloc_pct": 20,
        "short": 20, "long": 50, "rsi_entry_max": 70, "rsi_exit": 80,
    },
    "agressif": {
        "max_positions": 8, "alloc_pct": 25,
        "short": 10, "long": 50, "rsi_entry_max": 78, "rsi_exit": 85,
    },
}

DEFAULT = "normale"


def profile(name: str | None) -> dict:
    return dict(AGRESSIVITES.get(name or DEFAULT, AGRESSIVITES[DEFAULT]))
