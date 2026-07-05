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
