"""Tests sécurité : chiffrement des secrets + config chiffrée en base."""

import os
import sqlite3
import tempfile
from pathlib import Path

from src.crypto import decrypt, encrypt
from src.storage import Storage


def test_encrypt_roundtrip():
    os.environ["TELEGRAM_BOT_TOKEN"] = "unit-test-token"
    enc = encrypt("secret-value")
    assert enc != "secret-value"
    assert enc.startswith("enc::")
    assert decrypt(enc) == "secret-value"


def test_decrypt_passthrough_plaintext():
    # une valeur non chiffrée passe telle quelle (rétro-compat)
    assert decrypt("plain") == "plain"
    assert decrypt("") == ""


def test_config_encrypted_at_rest():
    os.environ["TELEGRAM_BOT_TOKEN"] = "unit-test-token"
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "t.db")
        db.set_config("EXCHANGE_API_SECRET", "TOPSECRET")
        # lecture applicative -> en clair
        assert db.get_config("EXCHANGE_API_SECRET") == "TOPSECRET"
        # lecture brute en base -> JAMAIS en clair
        raw = sqlite3.connect(db.path).execute(
            "SELECT value FROM kv_config WHERE key='EXCHANGE_API_SECRET'").fetchone()[0]
        assert "TOPSECRET" not in raw
        assert raw.startswith("enc::")
        db.del_config("EXCHANGE_API_SECRET")
        assert db.get_config("EXCHANGE_API_SECRET") is None


def test_audit_log_and_auth():
    import tempfile
    from pathlib import Path
    from src.storage import Storage
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "t.db")
        db.log_event(1, "auth_fail", "x (try 1)")
        db.log_event(1, "auth_ok", "x")
        ev = db.recent_audit(5)
        assert ev[0]["event"] == "auth_ok"      # plus récent en premier
        assert len(ev) == 2
        db.authorize(1)
        assert db.all_authorized() == [1]
