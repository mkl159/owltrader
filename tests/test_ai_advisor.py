"""Tests du conseiller IA (mockés — aucun appel réel à OpenAI)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import ai_advisor as ai
from src.storage import Storage


def _db():
    d = tempfile.mkdtemp()
    return Storage(Path(d) / "t.db")


def test_quota_un_par_jour():
    db = _db()
    assert ai.can_call(db) is True
    ai.record_call(db)
    assert ai.can_call(db) is False      # 2e appel le même jour -> refusé


def test_is_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch("src.ai_advisor.get_secret", return_value=None):
        assert ai.is_configured() is False
    with patch("src.ai_advisor.get_secret", return_value="sk-test"):
        assert ai.is_configured() is True


def test_ask_sans_cle():
    with patch("src.ai_advisor.get_secret", return_value=None):
        with pytest.raises(RuntimeError):
            ai.ask("contexte")


def test_ask_appel_mocke():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": "VENDRE BTC. ⚠️"}}]}
    resp.raise_for_status.return_value = None

    def fake_secret(name):
        return {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-5.4-mini",
                "AI_MAX_TOKENS": "100000"}.get(name)

    with patch("src.ai_advisor.get_secret", side_effect=fake_secret), \
         patch("src.ai_advisor.requests.post", return_value=resp) as post:
        out = ai.ask("contexte de test")
        assert "VENDRE" in out
        payload = post.call_args.kwargs["json"]
        assert payload["model"] == "gpt-5.4-mini"
        assert payload["max_completion_tokens"] == 100000     # plafond respecté
        assert payload["messages"][0]["role"] == "system"


def test_max_tokens_invalide_retombe_sur_defaut():
    with patch("src.ai_advisor.get_secret", return_value="pas-un-nombre"):
        assert ai._max_tokens() == ai.DEFAULT_MAX_TOKENS


def test_parse_orders():
    txt = ('1) ACHETER AAPL...\n⚠️ Avis IA.\n'
           '{"orders":[{"action":"BUY","asset":"STOCK:AAPL"},{"action":"SELL","asset":"CRYPTO:BTC"}]}')
    clean, orders = ai.parse_orders(txt)
    assert "orders" not in clean            # JSON retiré du texte affiché
    assert orders == [{"action": "BUY", "asset": "STOCK:AAPL"},
                      {"action": "SELL", "asset": "CRYPTO:BTC"}]


def test_parse_orders_sans_json():
    clean, orders = ai.parse_orders("Aucun ordre aujourd'hui.")
    assert orders == [] and "Aucun ordre" in clean


def test_parse_orders_json_invalide():
    clean, orders = ai.parse_orders('bla {"orders": [pas du json]} bla')
    assert orders == []


def test_execute_orders_paper():
    from src.paper import trader
    db = _db()
    db.paper_open(1, 1000, "EUR")
    svc = MagicMock()
    quote = MagicMock(); quote.price = 100.0
    svc.quote.return_value = quote
    cfg = {"frais_pct": 0.2, "frais_min": 1.0, "max_positions": 5, "alloc_pct": 20, "devise": "EUR"}
    uni = ["STOCK:AAPL", "CRYPTO:BTC"]
    ex = trader.execute_orders(db, svc, 1, [{"action": "BUY", "asset": "STOCK:AAPL"}], cfg, uni)
    assert len(ex) == 1 and ex[0]["side"] == "ACHAT" and ex[0]["motif"] == "ordre IA"
    assert db.paper_positions(1)[0]["asset"] == "STOCK:AAPL"
    # vente de la position par ordre IA
    ex2 = trader.execute_orders(db, svc, 1, [{"action": "SELL", "asset": "STOCK:AAPL"}], cfg, uni)
    assert len(ex2) == 1 and ex2[0]["side"] == "VENTE"
    assert db.paper_positions(1) == []
    # actif HORS liste mais cotable -> DÉCOUVERTE : acheté + ajouté à l'univers
    ex3 = trader.execute_orders(db, svc, 1, [{"action": "BUY", "asset": "STOCK:PLTR"}], cfg, uni)
    assert len(ex3) == 1 and "découverte" in ex3[0]["motif"]
    assert "STOCK:PLTR" in db.get_universe()
    # actif inconnu SANS cotation -> refusé
    svc.quote.return_value = None
    ex4 = trader.execute_orders(db, svc, 1, [{"action": "BUY", "asset": "STOCK:FAUXTICKER"}], cfg, uni)
    assert ex4 == []
