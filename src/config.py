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
    "frequences": {"actions": 15, "auto": 5},  # minutes
    # Paramètres du mode autonome (paper-trading fictif)
    "paper": {
        "capital": 1000,
        "frais_pct": 0.20,      # frais de courtage en % par transaction (achat ET vente)
        "frais_min": 1.0,       # frais minimum par transaction
        "max_positions": 5,     # nombre max de positions simultanées
        "alloc_pct": 20,        # % du capital investi par position
        "devise": "EUR",
        # Risk manager — calibré sur 10 ans (2016-2026, incl. krach COVID + bear 2022).
        # Stop-loss large = filet quasi gratuit. Coupe-circuit DÉSACTIVÉ : il ratait les
        # reprises post-krach et divisait le rendement par ~25 sur 10 ans.
        "stop_loss_pct": 25,    # vente auto si une position perd plus de X% depuis l'achat
        "max_dd_pause": 0,      # 0 = désactivé (la sortie de tendance gère déjà les krachs)
        "backtest_period": "5y",  # fenêtre de simulation/auto-réglage (robustesse multi-régimes)
        "regime_filter": True,    # n'acheter que si le marché (S&P) est au-dessus de sa MM200
        "regime_symbol": "INDEX:^GSPC",
        # Dimensionnement par volatilité (façon Ray Dalio / Turtles) : investir moins sur
        # les actifs volatils. 0.20 retenu car robuste sur 5 ANS ET 10 ANS (le 0.30 brillait
        # à 10 ans mais était fragile à 5 ans). Améliore Sharpe et réduit le drawdown.
        "vol_target": 0.20,       # volatilité annualisée cible par position (0 = taille fixe)
        # Classement des candidats par momentum relatif (force-relative / dual momentum).
        # 21j (1 mois) retenu : améliore Sharpe ET drawdown sur 5 ANS ET 10 ANS (le 6 mois
        # brillait à 10 ans mais était fragile à 5 ans). 0 = ordre de la liste.
        "rank_lookback": 21,
        # Momentum absolu (Antonacci) : ne pas acheter un actif en baisse sur N jours.
        # Validé robuste 5 ET 10 ans (n'a jamais nui). 126j ≈ 6 mois.
        "abs_mom_lookback": 126,
        "abs_mom_min": 0.0,
    },
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


_kv_store = None


def _kv():
    """Magasin de config (SQLite) mis en cache — pour les clés réglées via Telegram."""
    global _kv_store
    if _kv_store is None:
        from .storage import Storage
        _kv_store = Storage()
    return _kv_store


def get_secret(name: str) -> str | None:
    """Valeur d'un secret/clé : d'abord la config réglée par Telegram, sinon le .env."""
    try:
        v = _kv().get_config(name)
        if v:
            return v
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get(name)


CONFIG = load_config()
