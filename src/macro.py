"""Régime macro cross-actifs (risk-on / risk-off).

Inspiré du « pilier macro » d'agentic-trading-desk (github.com/Oft3r/agentic-trading-desk) :
on lit la tendance de RAPPORTS entre ETF qui révèlent l'appétit pour le risque du marché,
bien mieux qu'un seul indice. Tout en données gratuites (Yahoo). C'est de l'INFO de contexte
(pour l'IA et l'utilisateur), pas un signal de trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# (numérateur, dénominateur, libellé, sens) : rising = risk-on par défaut
MACRO_PAIRS = [
    ("RSP", "SPY", "Largeur du marché (equal vs cap-weight)"),
    ("HYG", "LQD", "Appétit crédit (high yield vs investment grade)"),
    ("IWM", "SPY", "Small caps vs large caps"),
    ("SPY", "TLT", "Actions vs obligations"),
    ("XLY", "XLP", "Cyclique vs défensif (conso disc. vs staples)"),
]


@dataclass
class MacroRegime:
    score: float                 # -100 (risk-off) … +100 (risk-on)
    label: str
    components: list = field(default_factory=list)   # (libellé, "risk-on"/"risk-off", variation %)

    @property
    def emoji(self) -> str:
        if self.score >= 25:
            return "🟢"
        if self.score <= -25:
            return "🔴"
        return "⚪"


def _regime_label(score: float) -> str:
    if score >= 40:
        return "Franc RISK-ON (appétit pour le risque)"
    if score >= 15:
        return "Risk-on modéré"
    if score <= -40:
        return "Franc RISK-OFF (fuite vers la sécurité)"
    if score <= -15:
        return "Risk-off modéré"
    return "Neutre / indécis"


def macro_regime(svc, lookback: int = 20) -> MacroRegime | None:
    """Calcule le régime cross-actifs à partir des tendances de rapports d'ETF."""
    votes = []
    comps = []
    for num, den, label in MACRO_PAIRS:
        dn = svc.history(f"STOCK:{num}", period="6mo")
        dd = svc.history(f"STOCK:{den}", period="6mo")
        if dn is None or dd is None:
            continue
        ratio = (dn["close"].astype(float) / dd["close"].reindex(dn.index).astype(float)).dropna()
        if len(ratio) <= lookback:
            continue
        chg = ratio.iloc[-1] / ratio.iloc[-1 - lookback] - 1
        risk_on = chg > 0
        votes.append(1 if risk_on else -1)
        comps.append((label, "risk-on" if risk_on else "risk-off", round(chg * 100, 1)))
    if not votes:
        return None
    score = sum(votes) / len(votes) * 100
    return MacroRegime(score=round(score, 0), label=_regime_label(score), components=comps)


def macro_summary_line(m: MacroRegime | None) -> str:
    """Une ligne compacte pour le dossier IA."""
    if m is None:
        return ""
    det = "; ".join(f"{c[0].split('(')[0].strip()} {c[1]} ({c[2]:+.1f}%)" for c in m.components)
    return f"MACRO CROSS-ACTIFS: {m.label} (score {m.score:+.0f}) — {det}"
