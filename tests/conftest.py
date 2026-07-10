"""Fixtures de test : données synthétiques (aucun appel réseau)."""

import numpy as np
import pandas as pd
import pytest


def _series(trend: float, n: int = 400, seed: int = 0, start: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range("2019-01-01", periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(seed)
    rets = trend + rng.normal(0, 0.01, n)
    close = start * np.cumprod(1 + rets)
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99,
         "close": close, "volume": 1000.0},
        index=idx,
    )


@pytest.fixture(autouse=True)
def _market_toujours_ouvert(request, monkeypatch):
    """Les tests de cycles ne doivent pas dépendre de l'heure d'exécution de la CI.

    On fige « marché ouvert » partout, SAUF pour les tests marqués `horaires_reels`
    qui testent justement la fonction market_open_now.
    """
    if "horaires_reels" in request.keywords:
        yield
        return
    from src.paper import trader
    monkeypatch.setattr(trader, "market_open_now", lambda raw, now=None: True)
    yield


@pytest.fixture
def uptrend():
    return _series(trend=0.0015, seed=1)


@pytest.fixture
def downtrend():
    return _series(trend=-0.0015, seed=2)


@pytest.fixture
def universe_up():
    return {f"STOCK:A{i}": _series(trend=0.0012, seed=i) for i in range(4)}
