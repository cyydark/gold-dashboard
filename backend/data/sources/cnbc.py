"""CNBC Commodities RSS gold news via search JSON API.

数据源: https://search.cnbc.com/rs/search/combinedcms/view.json?id=10000664
RSS feed: commodities/business news
过滤: gold, XAU, silver, bullion 等关键词
"""
import html
import logging
import re
import time
from datetime import datetime, timedelta

import httpx

from backend.config import BEIJING_TZ
from backend.data.constants import NEWS_TTL

logger = logging.getLogger(__name__)

_cache: list[dict] = []
_cache_ts: float = 0.0

_RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.json?partnerId=wrss01&id=10000664"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
}

# 黄金关键词过滤
GOLD_KEYWORDS = [
    "gold", "xau", "xauusd", "silver", "bullion",
    "precious metal", "goldman sachs", "gold futures",
    "gold etf", "gold rally", "gold surge",
]
EXCLUDE_KEYWORDS = [
    "bitcoin", "cryptocurrency", "tesla deliveries",
]


def _is_gold_article(title: str) -> bool:
    t = title.lower()
    if any(kw in t for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw in t for kw in GOLD_KEYWORDS)


def _parse_rss_date(date_str: str) -> datetime:
    """Parse RFC 2822 date like 'Sun, 06 Apr 2026 13:44:33 GMT'."""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).astimezone(BEIJING_TZ)
    except Exception:
        return datetime.now(BEIJING_TZ)


def fetch_cnbc_news() -> list[dict]:
    """Fetch gold news from CNBC Commodities RSS feed.

    Returns:
        List of news items [{"title", "url", "source", "published_ts", "published"}, ...]
    """
    global _cache, _cache_ts

    if _cache and (time.time() - _cache_ts) < NEWS_TTL:
        return _cache

    try:
        resp = httpx.get(_RSS_URL, headers=_HEADERS, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("rss", {}).get("channel", {}).get("item", [])
    except Exception as e:
        logger.warning(f"CNBC RSS error: {e}")
        return _cache if _cache else []

    news: list[dict] = []
    for item in items:
        raw_title = item.get("title", "")
        if isinstance(raw_title, list):
            raw_title = raw_title[0] if raw_title else ""
        title = html.unescape(str(raw_title)).strip()
        if not _is_gold_article(title):
            continue

        link_list = item.get("link", [])
        if isinstance(link_list, list):
            link = link_list[0] if link_list else ""
        else:
            link = str(link_list)

        pub_str = item.get("pubDate", "")
        dt = _parse_rss_date(pub_str)
        news.append({
            "title": title,
            "title_en": title,
            "url": link,
            "source": "CNBC",
            "published_ts": int(dt.timestamp()),
            "published": dt.strftime("%Y-%m-%d"),
        })

    news.sort(key=lambda x: x["published_ts"], reverse=True)
    _cache = news
    _cache_ts = time.time()
    logger.info(f"CNBC gold news: {len(news)} items")
    return news
