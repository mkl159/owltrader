"""Chargement de la configuration (config.yaml) et des secrets (.env)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# Charge .env s'il existe (jamais commité)
load_dotenv(ROOT / ".env")

DEFAULTS = {
    "langue": "fr",
    "fuseau_horaire": "Europe/Paris",
    "watchlist": ["STOCK:AAPL", "STOCK:MSFT", "INDEX:^FCHI"],
    # Univers balayé par le screener pour proposer des pistes d'achat
    "univers_scan": [
        "STOCK:AAPL", "STOCK:MSFT", "STOCK:GOOGL", "STOCK:AMZN", "STOCK:NVDA",
        "STOCK:META", "STOCK:TSLA", "STOCK:JPM", "STOCK:V", "STOCK:NFLX",
        "STOCK:MC.PA", "STOCK:OR.PA", "STOCK:AIR.PA", "STOCK:TTE.PA", "STOCK:SAN.PA",
        "INDEX:^GSPC", "INDEX:^FCHI",
        "CRYPTO:BTC", "CRYPTO:ETH", "CRYPTO:SOL", "CRYPTO:BNB",
        "COMMO:GOLD", "COMMO:SILVER", "COMMO:OIL",
        "FX:EURUSD",
    ],
    "frequences": {"actions": 15},  # minutes
    "signaux": {
        "rsi_survente": 30,
        "rsi_surachat": 70,
        "ratio_risque_rendement_min": 1.5,
        "atr_multiplicateur_stop": 2.0,
        "anti_spam_heures": 4,
    },
}


def load_config() -> dict:
    """Charge config.yaml si présent, sinon config.example.yaml, sinon les défauts."""
    for name in ("config.yaml", "config.example.yaml"):
        path = ROOT / name
        if path.exists():
            with open(path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return {**DEFAULTS, **cfg}
    return dict(DEFAULTS)


def get_secret(name: str) -> str | None:
    return os.environ.get(name)


CONFIG = load_config()
