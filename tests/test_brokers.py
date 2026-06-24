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
