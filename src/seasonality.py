"""Saisonnalité de marché : effets calendaires + jours fériés boursiers (US).

Effets historiques pris en compte :
- 🎃 Effet Halloween / « Sell in May » : nov→avr historiquement plus porteur que mai→oct.
- 📅 Effet fin de mois : rendements concentrés autour du changement de mois.
- 🎄 Rallye de fin d'année (dernières séances de décembre).
- 🦃 Effet pré-jour férié : tendance haussière la veille des fêtes.
Aucune dépendance externe (pandas fournit le calendrier des fériés US).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd
from pandas.tseries.holiday import (
    GoodFriday,
    Holiday,
    USFederalHolidayCalendar,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
)
from pandas.tseries.offsets import CustomBusinessDay


class _USMarketCalendar(USFederalHolidayCalendar):
    """Fériés boursiers US (≈ NYSE) : fédéraux pertinents + Vendredi saint."""
    rules = [
        Holiday("New Year", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


_CAL = _USMarketCalendar()
_BDAY = CustomBusinessDay(calendar=_CAL)


def _to_date(d) -> date:
    if d is None:
        from datetime import timezone
        return datetime.now(timezone.utc).date()
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return pd.Timestamp(d).date()


def upcoming_holidays(d=None, days: int = 60) -> list[tuple[date, str]]:
    d = _to_date(d)
    hol = _CAL.holidays(start=d, end=d + timedelta(days=days), return_name=True)
    return [(ts.date(), name) for ts, name in hol.items()]


def is_market_holiday(d=None) -> bool:
    d = _to_date(d)
    hols = set(_CAL.holidays(start=d - timedelta(days=1), end=d + timedelta(days=1)))
    return pd.Timestamp(d) in hols


def days_to_next_holiday(d=None) -> tuple[int, str] | None:
    d = _to_date(d)
    nxt = upcoming_holidays(d, 90)
    for hd, name in nxt:
        if hd >= d:
            # nombre de jours ouvrés d'ici là
            n = len(pd.bdate_range(d, hd, freq=_BDAY)) - 1
            return max(n, 0), name
    return None


@dataclass
class Season:
    strong_season: bool         # nov-avr
    turn_of_month: bool
    year_end_rally: bool
    pre_holiday: bool
    bias: float                 # biais saisonnier net dans [-1, 1]
    notes: list[str] = field(default_factory=list)


def seasonal_context(d=None) -> Season:
    d = _to_date(d)
    notes = []
    bias = 0.0

    strong = d.month in (11, 12, 1, 2, 3, 4)
    if strong:
        bias += 0.4
        notes.append("🎃 Période forte (nov→avr)")
    else:
        bias -= 0.3
        notes.append("🌤️ Période faible (mai→oct, « sell in May »)")

    # fin de mois : 2 derniers jours ouvrés ou 3 premiers
    last = (d + pd.offsets.BMonthEnd(0)).date()
    first = (d + pd.offsets.BMonthBegin(-1)).date() if d.day > 5 else (d + pd.offsets.BMonthBegin(0)).date()
    tom = (last - d).days <= 2 and (last - d).days >= 0 or 1 <= (d - first).days <= 3 or d.day <= 3 or d.day >= 27
    if tom:
        bias += 0.2
        notes.append("📅 Effet fin/début de mois")

    rally = d.month == 12 and d.day >= 20
    if rally:
        bias += 0.2
        notes.append("🎄 Rallye de fin d'année")

    nh = days_to_next_holiday(d)
    pre_hol = nh is not None and nh[0] <= 1
    if pre_hol:
        bias += 0.15
        notes.append(f"🦃 Veille de jour férié ({nh[1]})")

    bias = max(-1.0, min(1.0, bias))
    return Season(strong_season=strong, turn_of_month=bool(tom), year_end_rally=rally,
                  pre_holiday=bool(pre_hol), bias=round(bias, 2), notes=notes)
