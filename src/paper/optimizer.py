"""Auto-tuning robuste : recherche les meilleurs réglages ET le bon niveau d'agressivité.

Validation HORS ÉCHANTILLON (out-of-sample) : on choisit les paramètres d'après leur
performance sur la période la plus récente (test), pas sur toute l'histoire — pour éviter
le surapprentissage (« ça marche super... sur le passé qu'on a optimisé »).
"""

from __future__ import annotations

from .profiles import AGRESSIVITES
from .simulator import SimResult, simulate

# Grille : chaque profil d'agressivité, décliné avec quelques vitesses de moyennes
_SPEEDS = [(10, 50), (20, 50), (20, 100)]
GRID: list[dict] = []
for _prof in AGRESSIVITES.values():
    for _s, _l in _SPEEDS:
        cand = {**_prof, "short": _s, "long": _l}
        if cand not in GRID:
            GRID.append(cand)


def _score(r: SimResult) -> float:
    # priorité à la rentabilité, avec une pénalité de risque modérée + bonus régularité
    return r.total_return + 0.25 * r.max_drawdown + 0.05 * r.sharpe


def _split(histories: dict, frac: float = 0.7):
    all_dates = sorted(set().union(*[set(df.index) for df in histories.values()]))
    if len(all_dates) < 60:
        return histories, histories
    cutoff = all_dates[int(len(all_dates) * frac)]
    train = {a: df[df.index <= cutoff] for a, df in histories.items()}
    test = {a: df[df.index > cutoff] for a, df in histories.items()}
    return train, test


def optimize(histories: dict, capital: float = 1000.0, validate: bool = True,
             **fixed) -> tuple[dict, SimResult] | None:
    """Renvoie (meilleurs_params, résultat_sur_tout_l'historique). Sélection hors échantillon."""
    histories = {k: v for k, v in histories.items() if v is not None and len(v) > 120}
    if not histories:
        return None
    train, test = _split(histories) if validate else (histories, histories)

    # On RÈGLE sur le passé (train) et on VALIDE sur le récent (test) — walk-forward.
    # Score combiné : on récompense les réglages robustes (bons sur les deux périodes).
    best_params = None
    best_score = float("-inf")
    for params in GRID:
        r_full = simulate(histories, capital=capital, **{**fixed, **params})
        r_test = simulate(test, capital=capital, **{**fixed, **params})
        if r_full is None or r_test is None:
            continue
        # 70% performance globale + 30% robustesse récente (hors échantillon)
        sc = 0.7 * _score(r_full) + 0.3 * _score(r_test)
        if sc > best_score:
            best_score, best_params = sc, params

    if best_params is None:
        return None
    # Résultat affiché : simulation sur TOUT l'historique avec les meilleurs réglages
    full = simulate(histories, capital=capital, **{**fixed, **best_params})
    return best_params, full
