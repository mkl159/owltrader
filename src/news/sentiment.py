"""Analyse de sentiment LOCALE et gratuite (lexique financier).

Interface volontairement simple pour être remplaçable par un LLM plus tard
(mode "llm" dans config) sans toucher au reste — voir CAHIER_DES_CHARGES §12.
"""

from __future__ import annotations

import re

# Lexique financier minimal (EN + FR), score par mot
POSITIVE = {
    "surge", "soar", "rally", "gain", "gains", "rise", "rises", "jump", "beat", "beats",
    "record", "growth", "profit", "profits", "upgrade", "bullish", "outperform", "strong",
    "boost", "high", "wins", "win", "positive", "recovery", "rebound", "buy",
    "hausse", "bond", "croissance", "bénéfice", "bénéfices", "gagne", "hausses",
}
NEGATIVE = {
    "plunge", "crash", "fall", "falls", "drop", "drops", "slump", "loss", "losses", "miss",
    "misses", "downgrade", "bearish", "underperform", "weak", "cut", "cuts", "fear", "fears",
    "low", "warning", "warn", "warns", "decline", "sell", "selloff", "lawsuit", "probe",
    "baisse", "chute", "perte", "pertes", "recul", "alerte", "faillite", "krach", "vente",
}

_WORD = re.compile(r"[a-zàâäéèêëîïôöùûüç]+", re.IGNORECASE)


def score_sentiment(text: str) -> float:
    """Renvoie un score dans [-1, 1] : >0 positif, <0 négatif, 0 neutre."""
    if not text:
        return 0.0
    words = _WORD.findall(text.lower())
    if not words:
        return 0.0
    pos = sum(1 for w in words if w in POSITIVE)
    neg = sum(1 for w in words if w in NEGATIVE)
    if pos == neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 3)
