"""Collecte d'actualités depuis des flux RSS gratuits (sans clé API)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import feedparser

from ..symbols import Asset
from .sentiment import score_sentiment

log = logging.getLogger(__name__)

# Flux RSS gratuits par classe d'actif
YAHOO_TICKER_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"
GENERIC_FEEDS = {
    "CRYPTO": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "MARKET": "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # marchés généraux
}
# Flux macro/marché agrégés (plusieurs sources gratuites pour une vue large)
MARKET_FEEDS = [
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Investing.com", "https://www.investing.com/rss/news.rss"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
]


@dataclass
class NewsItem:
    title: str
    link: str
    published: Optional[datetime]
    source: str
    sentiment: float = 0.0  # -1 (négatif) … +1 (positif)

    @property
    def mood(self) -> str:
        if self.sentiment > 0.15:
            return "🟢"
        if self.sentiment < -0.15:
            return "🔴"
        return "⚪"


def _parse_date(entry) -> Optional[datetime]:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    return datetime(*t[:6], tzinfo=timezone.utc)


def get_news(raw_asset: str, limit: int = 5) -> list[NewsItem]:
    """Renvoie les dernières actus pour un actif, triées du plus récent au plus ancien."""
    asset = Asset.parse(raw_asset)
    urls: list[tuple[str, str]] = []
    if asset.klass in ("STOCK", "INDEX"):
        urls.append((YAHOO_TICKER_RSS.format(sym=asset.yahoo_symbol), "Yahoo Finance"))
    elif asset.klass == "CRYPTO":
        urls.append((GENERIC_FEEDS["CRYPTO"], "CoinDesk"))
    else:
        urls.append((GENERIC_FEEDS["MARKET"], "CNBC"))

    items: list[NewsItem] = []
    for url, source in urls:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[: limit * 2]:
                title = getattr(e, "title", "").strip()
                if not title:
                    continue
                items.append(
                    NewsItem(
                        title=title,
                        link=getattr(e, "link", ""),
                        published=_parse_date(e),
                        source=source,
                        sentiment=score_sentiment(title),
                    )
                )
        except Exception as ex:  # noqa: BLE001
            log.warning("RSS %s a échoué : %s", url, ex)

    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:limit]


def get_market_news(limit: int = 12) -> list[NewsItem]:
    """Agrège les actus macro/marché depuis PLUSIEURS sources (vue large)."""
    items: list[NewsItem] = []
    seen = set()
    for source, url in MARKET_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:limit]:
                title = getattr(e, "title", "").strip()
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                items.append(NewsItem(title=title, link=getattr(e, "link", ""),
                                      published=_parse_date(e), source=source,
                                      sentiment=score_sentiment(title)))
        except Exception as ex:  # noqa: BLE001
            log.info("flux marché %s : %s", source, ex)
    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:limit]


def aggregate_sentiment(items: list[NewsItem]) -> float:
    """Sentiment moyen pondéré (récence) sur un lot d'actus, dans [-1, 1]."""
    if not items:
        return 0.0
    return round(sum(i.sentiment for i in items) / len(items), 3)
