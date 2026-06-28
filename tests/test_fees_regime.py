"""Tests des frais de courtage, du filtre de régime et du stockage."""

import tempfile
from pathlib import Path

from src.paper.fees import courtage
from src.regime import market_ok_now, regime_series
from src.storage import Storage


def test_courtage_pourcentage():
    assert courtage(1000, pct=0.20, minimum=1.0) == 2.0


def test_courtage_minimum():
    # petit montant -> on applique le minimum
    assert courtage(100, pct=0.20, minimum=1.0) == 1.0


def test_regime_haussier(uptrend):
    assert market_ok_now(uptrend) is True
    assert regime_series(uptrend).iloc[-1]


def test_regime_baissier(downtrend):
    assert market_ok_now(downtrend) is False


def test_storage_paper_cycle():
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "t.db")
        db.paper_open(42, 1000, "EUR")
        acc = db.paper_get(42)
        assert acc["cash"] == 1000 and acc["active"] == 1
        db.paper_add_position(42, "STOCK:X", 2, 50, 1.0)
        assert len(db.paper_positions(42)) == 1
        db.paper_set_cash(42, 900)
        assert db.paper_get(42)["cash"] == 900
        # reset efface tout
        db.paper_open(42, 500, "EUR")
        assert db.paper_get(42)["cash"] == 500
        assert db.paper_positions(42) == []


def test_storage_antispam():
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "t.db")
        assert db.should_alert(1, "STOCK:X", "ACHETER", 4) is True
        assert db.should_alert(1, "STOCK:X", "ACHETER", 4) is False  # bloqué


def test_storage_backup():
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "t.db")
        db.paper_open(7, 1000, "EUR")
        dest = db.backup(Path(d) / "bk")
        assert dest.exists() and dest.stat().st_size > 0
        # la sauvegarde est une base lisible
        restored = Storage(dest)
        assert restored.paper_get(7)["cash"] == 1000


def test_esc_md():
    from src.formatting import esc_md
    assert esc_md("a_b*c[d]`e") == "a b c d  e"
    assert esc_md("") == ""


def test_coingecko_supports():
    from src.collectors.coingecko_provider import CoinGeckoProvider
    from src.symbols import Asset
    cg = CoinGeckoProvider()
    assert cg.supports(Asset.parse("CRYPTO:BTC")) is True
    assert cg.supports(Asset.parse("STOCK:AAPL")) is False
    assert cg.supports(Asset.parse("CRYPTO:UNKNOWNXYZ")) is False


def test_storage_authorization():
    import tempfile
    from pathlib import Path
    from src.storage import Storage
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "t.db")
        assert db.is_authorized(9) is False
        db.authorize(9)
        assert db.is_authorized(9) is True
        db.deauthorize(9)
        assert db.is_authorized(9) is False
