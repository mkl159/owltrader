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
    clean, orders, plan = ai.parse_orders(txt)
    assert "orders" not in clean            # JSON retiré du texte affiché
    assert orders == [{"action": "BUY", "asset": "STOCK:AAPL"},
                      {"action": "SELL", "asset": "CRYPTO:BTC"}]
    assert plan is None                     # pas de plan dans ce bloc


def test_parse_orders_avec_plan():
    txt = ('Avis...\n{"orders":[{"action":"BUY","asset":"STOCK:NVDA"}],'
           '"plan":{"bias":"AGRESSIF","focus":["STOCK:NVDA","pasdeformat"],'
           '"eviter":["STOCK:TSLA"],"note":"Déployer sur les semi-conducteurs."}}')
    clean, orders, plan = ai.parse_orders(txt)
    assert orders == [{"action": "BUY", "asset": "STOCK:NVDA"}]
    assert plan == {"bias": "agressif", "focus": ["STOCK:NVDA"],
                    "eviter": ["STOCK:TSLA"], "note": "Déployer sur les semi-conducteurs."}
    # bias inconnu -> neutre
    _, _, p2 = ai.parse_orders('{"orders":[],"plan":{"bias":"nimporte","focus":[],"eviter":[],"note":""}}')
    assert p2["bias"] == "neutre"


def test_parse_orders_sans_json():
    clean, orders, plan = ai.parse_orders("Aucun ordre aujourd'hui.")
    assert orders == [] and plan is None and "Aucun ordre" in clean


def test_parse_orders_json_invalide():
    clean, orders, plan = ai.parse_orders('bla {"orders": [pas du json]} bla')
    assert orders == [] and plan is None


def test_plan_24h_guide_le_cycle_autonome():
    """Osmose : bias défensif = aucun achat ; eviter exclu ; focus prioritaire."""
    from unittest.mock import MagicMock

    import numpy as np
    import pandas as pd

    import src.strategy as strategy_mod
    from src.paper import trader

    class FakeDB:
        def __init__(self): self.kv = {}
        def get_config(self, k): return self.kv.get(k)
        def set_config(self, k, v): self.kv[k] = v

    def series(seed):
        idx = pd.date_range("2019-01-01", periods=400, freq="D", tz="UTC")
        rng = np.random.default_rng(seed)
        close = 100 + rng.normal(0.05, 0.5, 400).cumsum()
        return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                             "close": close, "volume": 1000.0}, index=idx)

    histories = {"STOCK:AAA": series(1), "STOCK:BBB": series(2), "STOCK:CCC": series(3)}
    svc = MagicMock()
    svc.fetch_histories.side_effect = lambda uni, period="1y": {a: histories[a] for a in uni}
    svc.history.side_effect = lambda raw, period="1y": histories.get(raw)

    def broker():
        b = MagicMock()
        b.get_account.return_value = {"equity": 10000, "cash": 10000, "currency": "USD"}
        b.get_positions.return_value = []
        b.get_open_orders.return_value = []
        return b

    pc = {"max_positions": 1, "alloc_pct": 20}
    from unittest.mock import patch
    with patch.object(strategy_mod, "position_series",
                      lambda df, **kw: pd.Series([1] * len(df), index=df.index)):
        db = FakeDB()
        # 1) bias défensif -> AUCUN achat malgré 3 candidats
        ai.save_plan(db, {"bias": "defensif", "focus": [], "eviter": [], "note": ""})
        b1 = broker()
        assert trader.run_broker_cycle(b1, svc, list(histories), pc, {}, db) == []
        assert not b1.submit_order.called
        # 2) focus CCC + eviter AAA -> le seul slot va à CCC
        ai.save_plan(db, {"bias": "agressif", "focus": ["STOCK:CCC"],
                          "eviter": ["STOCK:AAA"], "note": ""})
        b2 = broker()
        ex = trader.run_broker_cycle(b2, svc, list(histories), pc, {}, db)
        assert [e["asset"] for e in ex if e["side"] == "ACHAT"] == ["CCC"]


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
