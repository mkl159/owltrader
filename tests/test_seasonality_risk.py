"""Tests saisonnalité et climat de risque (logique pure, sans réseau)."""

import datetime

from src.risk_climate import assess, geo_tension, vix_bias
from src.seasonality import days_to_next_holiday, seasonal_context, upcoming_holidays


def test_seasonal_bias_borne():
    s = seasonal_context(datetime.date(2025, 7, 15))   # plein été (faible)
    assert -1.0 <= s.bias <= 1.0
    assert s.strong_season is False


def test_seasonal_noel_fort():
    s = seasonal_context(datetime.date(2025, 12, 24))   # veille de Noël
    assert s.strong_season is True
    assert s.year_end_rally is True
    assert s.bias > 0.3


def test_upcoming_holidays_non_vide():
    h = upcoming_holidays(datetime.date(2025, 1, 1), days=200)
    assert len(h) >= 2
    nh = days_to_next_holiday(datetime.date(2025, 1, 1))
    assert nh is not None and nh[0] >= 0


def test_vix_bias():
    assert vix_bias(12)[0] > 0          # calme -> légèrement positif
    assert vix_bias(45)[0] == -1.0      # panique -> max négatif
    assert vix_bias(None)[0] == 0.0


def test_geo_tension():
    titles = ["War escalates in region", "Apple releases new phone", "New sanctions announced"]
    score, hot = geo_tension(titles)
    assert score > 0
    assert len(hot) == 2                 # 2 titres sur 3 sont géopolitiques


def test_assess_climat():
    rc = assess(35, ["missile strike reported", "tariffs raised"])
    assert rc.bias < 0                   # VIX haut + tension -> risk-off
    assert -1.0 <= rc.bias <= 1.0
