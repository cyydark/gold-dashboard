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
    """Try to fetch news from backend.data.sources.briefing."""
    try:
        from backend.data.sources import briefing
        fn = getattr(briefing, "fetch_news", None)
        if fn:
            result = fn()
            if isinstance(result, list):
                return result
    except Exception:
        pass
    return []
