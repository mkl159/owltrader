"""Climat de risque macro / géopolitique (gratuit, quantifiable).

Deux sources agrégées :
- 📉 VIX (« indice de la peur ») : monte avec l'incertitude et les tensions géopolitiques.
- 📰 Scan des actualités : densité de mots-clés de tension (guerre, sanctions, tarifs…).

Renvoie un biais « risk-off » dans [-1, 1] (négatif = climat risqué) + un libellé.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

GEO_KEYWORDS = {
    # EN
    "war", "warns", "conflict", "invasion", "invade", "sanction", "sanctions", "tariff",
    "tariffs", "missile", "strike", "attack", "nuclear", "tension", "tensions", "crisis",
    "embargo", "ceasefire", "military", "troops", "escalation", "coup", "terror",
    # FR
    "guerre", "conflit", "tarifs", "attaque", "nucléaire", "crise", "militaire",
    "escalade", "frappe", "frappes",
}
_WORD = re.compile(r"[a-zàâäéèêëîïôöùûüç]+", re.IGNORECASE)


def vix_bias(vix_level: float | None) -> tuple[float, str]:
    """VIX -> (biais risk-off [-1,0], libellé). Plus le VIX est haut, plus c'est négatif."""
    if vix_level is None:
        return 0.0, "VIX indisponible"
    if vix_level < 15:
        return 0.15, f"VIX {vix_level:.0f} — marché calme 🟢"
    if vix_level < 20:
        return 0.0, f"VIX {vix_level:.0f} — normal ⚪"
    if vix_level < 28:
        return -0.4, f"VIX {vix_level:.0f} — nervosité 🟠"
    if vix_level < 38:
        return -0.7, f"VIX {vix_level:.0f} — forte peur 🔴"
    return -1.0, f"VIX {vix_level:.0f} — panique 🔴🔴"


def geo_tension(titles: list[str]) -> tuple[float, list[str]]:
    """Densité de tension géopolitique dans des titres d'actu -> (score 0..1, titres chauds)."""
    if not titles:
        return 0.0, []
    hot = []
    flagged = 0
    for t in titles:
        words = set(_WORD.findall(t.lower()))
        if words & GEO_KEYWORDS:
            flagged += 1
            hot.append(t)
    return round(flagged / len(titles), 2), hot[:4]


@dataclass
class RiskClimate:
    bias: float                 # [-1, 1] : négatif = risk-off
    vix: float | None
    vix_note: str
    geo_score: float            # 0..1
    hot_headlines: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.bias <= -0.5:
            return "Risque élevé (risk-off) 🔴"
        if self.bias <= -0.2:
            return "Prudence 🟠"
        if self.bias >= 0.15:
            return "Climat serein 🟢"
        return "Neutre ⚪"


def assess(vix_level: float | None, titles: list[str]) -> RiskClimate:
    vb, vnote = vix_bias(vix_level)
    gscore, hot = geo_tension(titles)
    geo_bias = -min(1.0, gscore * 1.5)            # plus de tension -> plus négatif
    bias = max(-1.0, min(1.0, 0.6 * vb + 0.4 * geo_bias))
    return RiskClimate(bias=round(bias, 2), vix=vix_level, vix_note=vnote,
                       geo_score=gscore, hot_headlines=hot)
