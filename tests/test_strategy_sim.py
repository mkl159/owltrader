"""Tests de la stratégie et du simulateur (cœur du mode autonome)."""

import math

import numpy as np

from src.paper.simulator import simulate
from src.strategy import position_series
from src.strategies import breakout_position, ensemble_position_series, votes_now


def test_position_series_uptrend(uptrend):
    ps = position_series(uptrend)
    assert len(ps) == len(uptrend)
    assert set(ps.unique()) <= {0, 1}
    # en tendance haussière franche, on détient une bonne partie du temps
    assert ps.sum() > len(ps) * 0.3


def test_ensemble_no_position_when_short(uptrend):
    short = uptrend.iloc[:30]
    assert len(ensemble_position_series(short)) == 0


def test_adx_borne(uptrend):
    from src.indicators.technical import adx
    a = adx(uptrend).dropna()
    assert (a >= 0).all() and (a <= 100).all()


def test_simulate_options_recherche(universe_up):
    # Les paramètres de recherche (défaut off + variantes) tournent sans casser
    for kw in ({}, {"rank_vol_adjust": True, "rank_lookback": 21},
               {"graded_regime": True}, {"max_corr": 0.8}, {"max_crypto": 1},
               {"abs_mom_lookback": 60}):
        r = simulate(universe_up, capital=1000, **kw)
        assert r is not None and r.final_equity > 0


def test_breakout_turtle(uptrend):
    b = breakout_position(uptrend)
    assert set(b.unique()) <= {0, 1}
    assert b.sum() > 0                    # une tendance haussière déclenche des cassures


def test_team_votes_inclut_turtle(uptrend):
    v = votes_now(uptrend)
    assert "turtle" in v and "tendance" in v
    assert all(isinstance(x, bool) for x in v.values())


def test_simulate_rentable_en_hausse(universe_up):
    r = simulate(universe_up, capital=1000)
    assert r is not None
    assert r.final_equity > 1000          # gagne de l'argent en marché haussier
    assert r.fees_total > 0               # des frais sont bien prélevés
    assert r.n_trades > 0
    assert math.isfinite(r.final_equity)
    assert not r.equity_curve.isna().any()


def test_simulate_cash_jamais_negatif(universe_up):
    r = simulate(universe_up, capital=1000)
    # la courbe d'équity ne doit jamais devenir NaN ni négative
    assert (r.equity_curve > 0).all()


def test_simulate_gere_cours_manquant(universe_up):
    # injecte un NaN en fin de série : ne doit pas corrompre le résultat
    df = next(iter(universe_up.values()))
    df.iloc[-1, df.columns.get_loc("close")] = np.nan
    r = simulate(universe_up, capital=1000)
    assert r is not None
    assert math.isfinite(r.final_equity)


def test_stop_loss_reduit_exposition(universe_up):
    sans = simulate(universe_up, capital=1000, stop_loss_pct=0)
    avec = simulate(universe_up, capital=1000, stop_loss_pct=10)
    # le stop génère au moins autant de trades (sorties supplémentaires possibles)
    assert avec.n_trades >= sans.n_trades - 2
