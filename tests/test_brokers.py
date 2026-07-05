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
    svc = MagicMock()
    svc.history.side_effect = lambda raw, period="1y": {"STOCK:NVDA": up}.get(raw, down)
    qq = MagicMock(); qq.price = 200.0
    svc.quote.return_value = qq

    ex = trader.run_broker_cycle(broker, svc, ["STOCK:AAPL", "STOCK:NVDA"],
                                 {"max_positions": 5, "alloc_pct": 20}, {})
    sides = {e["asset"]: e["side"] for e in ex}
    assert broker.submit_order.called
    assert sides.get("AAPL") == "VENTE"      # AAPL détenue mais baissière -> vendue
    assert sides.get("NVDA") == "ACHAT"      # NVDA haussière non détenue -> achetée
