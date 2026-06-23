"""Auto-tuning : cherche les meilleurs paramètres de la stratégie sur l'historique.

Recherche par grille (grid search) ; sélection par score = rendement pénalisé par le
drawdown (pour éviter les réglages spectaculaires mais trop risqués).
"""

from __future__ import annotations

from .simulator import SimResult, simulate

# Grille de paramètres testés (volontairement compacte pour rester rapide)
GRID = [
    {"short": s, "long": l, "rsi_entry_max": rem}
    for s in (10, 20)
    for l in (50, 100)
    for rem in (70, 75)
]


def _score(r: SimResult) -> float:
    # rendement net pénalisé par le drawdown (max_drawdown est négatif)
    return r.total_return + 0.5 * r.max_drawdown


def optimize(histories: dict, capital: float = 1000.0, **fixed) -> tuple[dict, SimResult] | None:
    """Renvoie (meilleurs_params, meilleur_résultat). fixed : frais, alloc, etc."""
    best = None
    best_params = None
    best_score = float("-inf")
    for params in GRID:
        r = simulate(histories, capital=capital, **{**fixed, **params})
        if r is None:
            continue
        sc = _score(r)
        if sc > best_score:
            best_score, best, best_params = sc, r, params
    if best is None:
        return None
    return best_params, best
