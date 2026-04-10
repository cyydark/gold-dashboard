"""Local RSS news aggregator — gold news from RSSHUB.

数据源: RSSHUB RSS aggregator
来源: Bloomberg Markets / FX Street Gold / Investing.com Commodities
"""
import logging
import os
import time
from datetime import datetime, timedelta

from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx

from backend.config import BEIJING_TZ
from backend.data.constants import NEWS_TTL

logger = logging.getLogger(__name__)

_cache: list[dict] = []
_cache_ts: float = 0.0

# 黄金关键词过滤（英文）
GOLD_KEYWORDS = [
    "gold", "xau", "xauusd", "silver", "bullion",
    "precious metal", "goldman sachs", "gold futures",
    "gold etf", "gold rally", "gold surge",
]
EXCLUDE_KEYWORDS = [
    "bitcoin", "cryptocurrency", "tesla deliveries",
    "iphone", "apple", "women's sports", "wnba",
]


def _is_gold_article(title: str) -> bool:
    t = title.lower()
    if any(kw in t for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw in t for kw in GOLD_KEYWORDS)

_RSS_URL = os.environ.get("RSSHUB_URL", "http://localhost:18080/news")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
}


def _parse_rss_date(date_str: str) -> datetime:
    """Parse RFC 2822 date like 'Mon, 06 Apr 2026 17:02:00 +0800'."""
    try:
        return parsedate_to_datetime(date_str).astimezone(BEIJING_TZ)
    except Exception:
        return datetime.now(BEIJING_TZ)


def fetch_local_news() -> list[dict]:
    """Fetch gold news from localhost RSS aggregator.

    Returns:
        List of news items [{"title", "url", "source", "published_ts", "published"}, ...]
    """
    global _cache, _cache_ts

    if _cache and (time.time() - _cache_ts) < NEWS_TTL:
        return _cache

    try:
        resp = httpx.get(_RSS_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else []
    except Exception as e:
        logger.warning(f"Local RSS error: {e}")
        return _cache if _cache else []

    news: list[dict] = []
    for item in items:
        title = (item.findtext("title") or "").strip()
        if not title or not _is_gold_article(title):
            continue
        link = (item.findtext("link") or "").strip()
        pub_str = (item.findtext("pubDate") or "").strip()
        dt = _parse_rss_date(pub_str)
        source = (item.findtext("category") or "LocalRSS").strip() or "LocalRSS"

        news.append({
            "title": title,
            "title_en": title,
            "url": link,
            "source": source,
            "published_ts": int(dt.timestamp()),
            "published": dt.strftime("%Y-%m-%d"),
        })

    news.sort(key=lambda x: x["published_ts"], reverse=True)
    _cache = news
    _cache_ts = time.time()
    logger.info(f"LocalRSS gold news: {len(news)} items")
    return news
