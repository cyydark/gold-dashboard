"""News service — no DB, pure in-memory cache."""
import time
from typing import Any

# TTL: 30 minutes
_CACHE_TTL = 1800
_cache: dict[str, Any] = {"ts": 0, "data": []}


def get_news(days: int = 1) -> list:
    """Return cached news list. Refreshes if TTL expired."""
    now = time.monotonic()
    if _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]
    items = _fetch_news_from_sources()
    _cache["data"] = items
    _cache["ts"] = now
    return items


def _fetch_news_from_sources() -> list:
    """Fetch news from available news sources."""
    all_news: list = []
    fetchers = [
        _fetch_bernama,
        _fetch_aastocks,
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


def _fetch_aastocks() -> list:
    try:
        from backend.data.sources.aastocks import fetch_aastocks_news
        return fetch_aastocks_news()
    except Exception:
        return []
