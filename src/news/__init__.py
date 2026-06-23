"""Actualités : collecte de flux gratuits (RSS) + analyse de sentiment locale."""

from .collector import NewsItem, get_news  # noqa: F401
from .sentiment import score_sentiment  # noqa: F401
