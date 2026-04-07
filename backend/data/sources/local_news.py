"""Local RSS news aggregator — gold news from localhost:18080 (RSSHUB).

数据源: http://localhost:18080/news
来源: Bloomberg Markets / FX Street Gold / Investing.com Commodities
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 300  # 5 minutes
_cache: list[dict] = []
_cache_ts: float = 0.0

_RSS_URL = "http://localhost:18080/news"
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

    if _cache and (time.time() - _cache_ts) < _TTL:
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
        if not title:
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
