"""Tests du connecteur Alpaca (mock, aucun appel réseau)."""

from unittest.mock import MagicMock

import pytest

from src.brokers.alpaca import AlpacaBroker, to_alpaca_symbol


def test_to_alpaca_symbol():
    assert to_alpaca_symbol("STOCK:AAPL") == "AAPL"
    assert to_alpaca_symbol("CRYPTO:BTC") == "BTC/USD"
    assert to_alpaca_symbol("FX:EURUSD") is None
    assert to_alpaca_symbol("COMMO:GOLD") is None


def test_alpaca_requires_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        AlpacaBroker(session=MagicMock())


def test_alpaca_get_account_parse():
    sess = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"cash": "1000.5", "equity": "1200.0",
                              "currency": "USD", "status": "ACTIVE"}
    resp.raise_for_status.return_value = None
    sess.get.return_value = resp
    b = AlpacaBroker(key="k", secret="s", session=sess)
    acc = b.get_account()
    assert acc["cash"] == 1000.5
    assert acc["equity"] == 1200.0
    assert acc["status"] == "ACTIVE"
    # l'en-tête d'authentification a bien été posé
    assert sess.headers.update.called


def test_alpaca_submit_order_payload():
    sess = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"id": "x", "status": "accepted"}
    resp.raise_for_status.return_value = None
    sess.post.return_value = resp
    b = AlpacaBroker(key="k", secret="s", session=sess)
    b.submit_order("AAPL", 2, "buy")
    _, kwargs = sess.post.call_args
    assert kwargs["json"]["symbol"] == "AAPL"
    assert kwargs["json"]["side"] == "buy"
    assert kwargs["json"]["type"] == "market"


def test_to_ccxt_symbol():
    from src.brokers import to_ccxt_symbol
    assert to_ccxt_symbol("CRYPTO:BTC") == "BTC/USDT"
    assert to_ccxt_symbol("CRYPTO:ETH", quote="USD") == "ETH/USD"
    assert to_ccxt_symbol("STOCK:AAPL") is None


def test_alpaca_base_mode():
    from src.brokers.alpaca import ALPACA_LIVE, ALPACA_PAPER, alpaca_base
    assert alpaca_base("paper") == ALPACA_PAPER
    assert alpaca_base("live") == ALPACA_LIVE
    assert alpaca_base(None) == ALPACA_PAPER          # défaut = paper (sûr)


def test_run_broker_cycle_buys_and_sells():
    from unittest.mock import MagicMock

    import numpy as np
    import pandas as pd

    from src.paper import trader
    from src.strategy import should_hold

    def series(trend, seed):
        idx = pd.date_range("2019-01-01", periods=400, freq="D", tz="UTC")
        rng = np.random.default_rng(seed)
        close = 100 * np.cumprod(1 + trend + rng.normal(0, 0.01, 400))
        return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                             "close": close, "volume": 1000.0}, index=idx)

    up = series(0.0015, 1)     # tendance haussière (le bot veut détenir)
    down = series(-0.0015, 2)  # tendance baissière (le bot ne veut pas)
    assert should_hold(up) and not should_hold(down)   # pré-condition du test

    broker = MagicMock()
    broker.get_account.return_value = {"equity": 10000, "cash": 5000, "currency": "USD"}
    broker.get_positions.return_value = [{"symbol": "AAPL", "qty": 10, "avg_entry_price": 100}]
    broker.get_open_orders.return_value = []
    histories = {"STOCK:NVDA": up, "STOCK:AAPL": down}
    svc = MagicMock()
    # Nouveau cycle : récupération parallèle de tout l'univers d'un coup.
    svc.fetch_histories.side_effect = lambda uni, period="1y": {a: histories[a] for a in uni}
    svc.history.side_effect = lambda raw, period="1y": histories.get(raw)

    ex = trader.run_broker_cycle(broker, svc, ["STOCK:AAPL", "STOCK:NVDA"],
                                 {"max_positions": 5, "alloc_pct": 20}, {})
    sides = {e["asset"]: e["side"] for e in ex}
    assert broker.submit_order.called
    assert sides.get("AAPL") == "VENTE"      # AAPL détenue mais baissière -> vendue
    assert sides.get("NVDA") == "ACHAT"      # NVDA haussière non détenue -> achetée


def test_run_broker_cycle_ranks_by_momentum(monkeypatch):
    """Univers large : le cycle doit acheter les plus FORTES (momentum), pas les premières.

    On force la stratégie à vouloir les 3 (patch de position_series) pour isoler la
    logique de CLASSEMENT : c'est le momentum réel (calculé sur les prix) qui doit trancher.
    """
    from unittest.mock import MagicMock

    import numpy as np
    import pandas as pd

    import src.strategy as strategy
    from src.paper import trader

    def series(last_21d_return, seed):
        """Série plate puis rampe finale calibrant le momentum 21 jours voulu."""
        idx = pd.date_range("2019-01-01", periods=400, freq="D", tz="UTC")
        rng = np.random.default_rng(seed)
        close = 100 + rng.normal(0, 0.05, 400).cumsum()
        ramp = np.linspace(0, last_21d_return, 21)          # +X% sur les 21 derniers jours
        close[-21:] = close[-22] * (1 + ramp)
        return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                             "close": close, "volume": 1000.0}, index=idx)

    histories = {"STOCK:WEAK": series(0.03, 1),      # +3 % sur 21 j
                 "STOCK:MID": series(0.08, 2),       # +8 %
                 "STOCK:STRONG": series(0.15, 3)}    # +15 % (la plus forte)
    # La stratégie veut détenir les 3 : le tri par momentum est le seul discriminant.
    monkeypatch.setattr(strategy, "position_series",
                        lambda df, **kw: pd.Series([1] * len(df), index=df.index))

    broker = MagicMock()
    broker.get_account.return_value = {"equity": 10000, "cash": 10000, "currency": "USD"}
    broker.get_positions.return_value = []
    broker.get_open_orders.return_value = []
    svc = MagicMock()
    svc.fetch_histories.side_effect = lambda uni, period="1y": {a: histories[a] for a in uni}
    svc.history.side_effect = lambda raw, period="1y": histories.get(raw)

    pc = {"max_positions": 2, "alloc_pct": 20, "rank_lookback": 21}
    ex = trader.run_broker_cycle(broker, svc, list(histories), pc, {})
    bought = [e["asset"] for e in ex if e["side"] == "ACHAT"]
    assert "STRONG" in bought and "MID" in bought   # les 2 plus fortes
    assert "WEAK" not in bought                       # la plus faible écartée (place limitée)


def test_us_trading_universe_override_and_fetch_guards(monkeypatch):
    """La liste stockée (mise à jour hebdo) prime sur la liste figée ; fetch rejette l'anormal."""
    from src import universe_us as uu

    # Override : la liste à jour remplace la figée, extra dédoublonné
    out = uu.us_trading_universe(["CRYPTO:BTC", "STOCK:AAA"], symbols=["AAA", "BBB"])
    assert out == ["STOCK:AAA", "STOCK:BBB", "CRYPTO:BTC"]
    # Sans override : liste figée
    assert len(uu.us_trading_universe()) == len(uu.SP500)

    # Garde-fous de fetch_sp500 : liste trop courte ou symbole invalide -> None
    class FakeResp:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: FakeResp("Symbol\nAAPL\nMSFT\n"))
    assert uu.fetch_sp500() is None          # 2 valeurs : anormal, rejeté
    bad = "Symbol\n" + "\n".join(f"T{i}" for i in range(460)) + "\n$INVALID!\n"
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(bad))
    assert uu.fetch_sp500() is None          # symbole invalide : rejeté
    good = "Symbol\n" + "\n".join(f"T{i}" for i in range(460))
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(good))
    got = uu.fetch_sp500()
    assert got is not None and len(got) == 460


def test_ai_buy_protected_from_autonomous_cycle():
    """Anti-bagotement : l'IA achète -> le cycle autonome ne revend PAS pendant ia_hold_days."""
    from unittest.mock import MagicMock

    import numpy as np
    import pandas as pd

    from src.paper import trader

    class FakeDB:                                # kv minimal en mémoire
        def __init__(self): self.kv = {}
        def get_config(self, k): return self.kv.get(k)
        def set_config(self, k, v): self.kv[k] = v

    db = FakeDB()
    # 1) L'IA achète HOOD sur Alpaca
    broker = MagicMock()
    broker.get_account.return_value = {"equity": 10000, "cash": 10000, "currency": "USD"}
    broker.get_positions.return_value = []
    broker.get_open_orders.return_value = []
    svc = MagicMock()
    qq = MagicMock(); qq.price = 100.0
    svc.quote.return_value = qq
    ex = trader.execute_orders_alpaca(
        broker, svc, [{"action": "BUY", "asset": "STOCK:HOOD"}], {"alloc_pct": 20}, db)
    assert [e["side"] for e in ex] == ["ACHAT"]
    assert "HOOD" in trader.ai_protected(db, "alpaca", {"ia_hold_days": 7})

    # 2) Une heure après, le cycle autonome tourne : la stratégie ne veut PAS HOOD
    #    (série baissière) -> sans protection il vendrait ; avec, il NE VEND PAS.
    idx = pd.date_range("2019-01-01", periods=400, freq="D", tz="UTC")
    rng = np.random.default_rng(2)
    close = 100 * np.cumprod(1 - 0.0015 + rng.normal(0, 0.01, 400))
    down = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": 1000.0}, index=idx)
    broker2 = MagicMock()
    broker2.get_account.return_value = {"equity": 10000, "cash": 8000, "currency": "USD"}
    broker2.get_positions.return_value = [{"symbol": "HOOD", "qty": 20, "avg_entry_price": 100}]
    broker2.get_open_orders.return_value = []
    svc2 = MagicMock()
    svc2.fetch_histories.side_effect = lambda uni, period="1y": {"STOCK:HOOD": down}
    svc2.history.side_effect = lambda raw, period="1y": down
    ex2 = trader.run_broker_cycle(broker2, svc2, ["STOCK:HOOD"],
                                  {"max_positions": 5, "alloc_pct": 20, "ia_hold_days": 7}, {}, db)
    assert not [e for e in ex2 if e["side"] == "VENTE"]      # position IA protégée
    assert not broker2.submit_order.called

    # 3) Protection expirée (ia_hold_days=0) -> le cycle reprend la main et vend
    ex3 = trader.run_broker_cycle(broker2, svc2, ["STOCK:HOOD"],
                                  {"max_positions": 5, "alloc_pct": 20, "ia_hold_days": 0}, {}, db)
    assert [e["side"] for e in ex3] == ["VENTE"]

    # 4) Un SELL de l'IA lève la protection
    trader.ai_mark_held(db, "alpaca", "HOOD")
    broker3 = MagicMock()
    broker3.get_account.return_value = {"equity": 10000, "cash": 8000, "currency": "USD"}
    broker3.get_positions.return_value = [{"symbol": "HOOD", "qty": 20, "avg_entry_price": 100}]
    broker3.get_open_orders.return_value = []
    trader.execute_orders_alpaca(
        broker3, svc, [{"action": "SELL", "asset": "STOCK:HOOD"}], {"alloc_pct": 20}, db)
    assert "HOOD" not in trader.ai_protected(db, "alpaca", {"ia_hold_days": 7})


@pytest.mark.horaires_reels
def test_market_open_now_horaires():
    """Séances par actif : crypto 24/7, US 9h30-16h NY, Europe 9h-17h30 Paris, week-end fermé."""
    from datetime import datetime, timezone

    from src.paper.trader import market_open_now

    # Mardi 14 juillet 2026, 18h00 UTC = 14h00 New York (séance US) / 20h00 Paris (fermé)
    mardi_seance_us = datetime(2026, 7, 14, 18, 0, tzinfo=timezone.utc)
    assert market_open_now("STOCK:AAPL", mardi_seance_us)
    assert market_open_now("INDEX:^GSPC", mardi_seance_us)
    assert not market_open_now("STOCK:MC.PA", mardi_seance_us)      # Paris fermé à 20h
    # Mardi 10h00 UTC = 12h00 Paris (séance) / 6h00 New York (fermé)
    mardi_matin = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)
    assert market_open_now("STOCK:MC.PA", mardi_matin)
    assert not market_open_now("STOCK:AAPL", mardi_matin)
    # Samedi : tout fermé sauf crypto
    samedi = datetime(2026, 7, 11, 18, 0, tzinfo=timezone.utc)
    assert not market_open_now("STOCK:AAPL", samedi)
    assert not market_open_now("STOCK:MC.PA", samedi)
    assert not market_open_now("FX:EURUSD", samedi)
    assert market_open_now("CRYPTO:BTC", samedi)


def test_decision_df_ignore_bougie_du_jour():
    """La bougie du jour (en formation) est écartée ; une bougie d'hier est gardée."""
    from datetime import datetime, timedelta, timezone

    import numpy as np
    import pandas as pd

    from src.paper.trader import decision_df

    today = pd.Timestamp(datetime.now(timezone.utc).date(), tz="UTC")
    idx = pd.date_range(end=today, periods=100, freq="D", tz="UTC")
    df = pd.DataFrame({"close": np.linspace(100, 120, 100)}, index=idx)
    out = decision_df(df)
    assert len(out) == 99 and out.index[-1] < today          # bougie du jour écartée

    hier = today - timedelta(days=1)
    idx2 = pd.date_range(end=hier, periods=100, freq="D", tz="UTC")
    df2 = pd.DataFrame({"close": np.linspace(100, 120, 100)}, index=idx2)
    assert len(decision_df(df2)) == 100                       # historique clos : intact


def test_pause_urgence_bloque_achats_pas_ventes(monkeypatch):
    """/stopachats (façon freqtrade /stopentry) : aucun achat (cycle + IA), ventes actives."""
    from unittest.mock import MagicMock, patch

    import numpy as np
    import pandas as pd

    import src.strategy as strategy_mod
    from src.paper import trader

    class FakeDB:
        def __init__(self): self.kv = {"TRADING_PAUSED": "1"}
        def get_config(self, k): return self.kv.get(k)
        def set_config(self, k, v): self.kv[k] = v

    db = FakeDB()
    idx = pd.date_range("2019-01-01", periods=400, freq="D", tz="UTC")
    rng = np.random.default_rng(1)
    close = 100 + rng.normal(0.05, 0.5, 400).cumsum()
    up = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                       "close": close, "volume": 1000.0}, index=idx)
    svc = MagicMock()
    svc.fetch_histories.side_effect = lambda uni, period="1y": {"STOCK:AAA": up}
    svc.history.side_effect = lambda raw, period="1y": up
    qq = MagicMock(); qq.price = 100.0
    svc.quote.return_value = qq

    with patch.object(strategy_mod, "position_series",
                      lambda df, **kw: pd.Series([1] * len(df), index=df.index)):
        # Cycle autonome : la stratégie veut AAA, mais pause -> AUCUN achat
        b = MagicMock()
        b.get_account.return_value = {"equity": 10000, "cash": 10000, "currency": "USD"}
        b.get_positions.return_value = []
        b.get_open_orders.return_value = []
        assert trader.run_broker_cycle(b, svc, ["STOCK:AAA"],
                                       {"max_positions": 5, "alloc_pct": 20}, {}, db) == []
        # Ordres IA : BUY filtré, SELL passe (protège les positions)
        b2 = MagicMock()
        b2.get_account.return_value = {"equity": 10000, "cash": 10000, "currency": "USD"}
        b2.get_positions.return_value = [{"symbol": "AAA", "qty": 5, "avg_entry_price": 90}]
        b2.get_open_orders.return_value = []
        ex = trader.execute_orders_alpaca(
            b2, svc, [{"action": "BUY", "asset": "STOCK:BBB"},
                      {"action": "SELL", "asset": "STOCK:AAA"}], {"alloc_pct": 20}, db)
        assert [e["side"] for e in ex] == ["VENTE"]
        # Reprise -> les achats refonctionnent
        db.set_config("TRADING_PAUSED", "0")
        b3 = MagicMock()
        b3.get_account.return_value = {"equity": 10000, "cash": 10000, "currency": "USD"}
        b3.get_positions.return_value = []
        b3.get_open_orders.return_value = []
        ex3 = trader.run_broker_cycle(b3, svc, ["STOCK:AAA"],
                                      {"max_positions": 5, "alloc_pct": 20}, {}, db)
        assert [e["side"] for e in ex3] == ["ACHAT"]
