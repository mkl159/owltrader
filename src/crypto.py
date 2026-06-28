"""Chiffrement des secrets stockés en base (Fernet/AES).

La clé est dérivée du token du bot (présent dans .env, jamais en base) : sans le .env,
les secrets en base sont illisibles. Les valeurs chiffrées sont préfixées par `enc::`.
"""

from __future__ import annotations

import base64
import hashlib
import os

try:
    from cryptography.fernet import Fernet
    _AVAILABLE = True
except Exception:  # noqa: BLE001
    _AVAILABLE = False

_PREFIX = "enc::"


def _key() -> bytes:
    base = (os.environ.get("SECRET_KEY") or os.environ.get("TELEGRAM_BOT_TOKEN")
            or "owltrader-fallback-key")
    return base64.urlsafe_b64encode(hashlib.sha256(("owltrader::" + base).encode()).digest())


def encrypt(text: str | None) -> str | None:
    if not _AVAILABLE or not text:
        return text
    return _PREFIX + Fernet(_key()).encrypt(text.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if not _AVAILABLE or not value or not value.startswith(_PREFIX):
        return value
    try:
        return Fernet(_key()).decrypt(value[len(_PREFIX):].encode()).decode()
    except Exception:  # noqa: BLE001
        return value  # clé changée / valeur corrompue : on renvoie tel quel
