"""Modèle de frais de courtage (à l'achat ET à la vente)."""

from __future__ import annotations


def courtage(montant: float, pct: float = 0.20, minimum: float = 1.0) -> float:
    """Frais pour une transaction d'un montant donné : max(minimum, pct% du montant)."""
    return round(max(minimum, abs(montant) * pct / 100.0), 4)
