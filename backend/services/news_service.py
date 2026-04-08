"""News service — in-memory cache backed by SQLite persistence."""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from backend.repositories.news_repo import get_recent_news, save_news

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

# In-memory TTL: 10 minutes (matches news_repo TTL)
_CACHE_TTL = 600
_cache: dict[str, Any] = {"ts": 0, "data": [], "days": 1}


def get_news(days: int = 1) -> list:
    """Return cached news list.

    Layer 1 — in-memory: fast, per-process.
    Layer 2 — SQLite: persistent across restarts, shared (future).
    Refreshes from sources if both layers are stale.
    """
    now = time.monotonic()
    if _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL and _cache.get("days") == days:
        return _cache["data"]

    # Try SQLite first (faster than scraping)
    db_items = _fetch_from_db(days)
    if db_items:
        _cache["data"] = db_items
        _cache["ts"] = now
        _cache["days"] = days
        return db_items

    # Fall back to scraping
    items = _fetch_news_from_sources()
    items = _filter_by_days(items, days)
    _cache["data"] = items
    _cache["ts"] = now
    _cache["days"] = days
    save_news(items)
    return items


def _fetch_from_db(days: int) -> list:
    """Try to get fresh news from SQLite."""
    try:
        items = get_recent_news(days)
        if items:
            logger.debug("News from DB: %d items", len(items))
        return items
    except Exception as e:
        logger.warning("News from DB failed: %s", e)
        return []


def _filter_by_days(items: list, days: int) -> list:
    """Filter news items to those published within the last `days` days, sorted newest first."""
    if days <= 0:
        return _sort_news(items)
    cutoff = datetime.now(BEIJING_TZ) - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()
    filtered = [it for it in items if it.get("published_ts", 0) >= cutoff_ts]
    return _sort_news(filtered)


def _sort_news(items: list) -> list:
    """Sort news by published_ts descending (newest first)."""
    return sorted(items, key=lambda x: x.get("published_ts", 0), reverse=True)


def _fetch_news_from_sources() -> list:
    """Fetch news from available news sources."""
    all_news: list = []
    fetchers = [
        _fetch_bernama,
        _fetch_futu,
        _fetch_aastocks,
        _fetch_cnbc,
        _fetch_local_news,
    ]
    for fn in fetchers:
        try:
            items = fn()
            if isinstance(items, list):
                all_news.extend(items)
        except Exception:
            pass
    return all_news


def _fetch_bernama() -> list:
    try:
        from backend.data.sources.bernama import fetch_bernama_gold_news
        return fetch_bernama_gold_news()
    except Exception:
        return []


def _fetch_futu() -> list:
    try:
        from backend.data.sources.futu import fetch_futu_news
        return fetch_futu_news()
    except Exception:
        return []


def _fetch_aastocks() -> list:
    try:
        from backend.data.sources.aastocks import fetch_aastocks_news
        return fetch_aastocks_news()
    except Exception:
        return []


def _fetch_cnbc() -> list:
    try:
        from backend.data.sources.cnbc import fetch_cnbc_news
        return fetch_cnbc_news()
    except Exception:
        return []


def _fetch_local_news() -> list:
    try:
        from backend.data.sources.local_news import fetch_local_news as _fetch
        return _fetch()
    except Exception:
        return []
