"""Briefing service — no DB, pure in-memory cache."""
import time

# TTL: 1 hour
_CACHE_TTL = 3600
_cache: dict = {"ts": 0, "data": None}


def get_briefing(days: int = 3) -> dict:
    """Return cached briefing + news. Refreshes if TTL expired."""
    now = time.monotonic()
    if _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]
    # Refresh: fetch news and generate briefing
    news = _fetch_news(days)
    content = _generate_briefing(news, days)
    result = {
        "weekly": {
            "content": content,
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }
    _cache["data"] = result
    _cache["ts"] = now
    return result


def _fetch_news(days: int) -> list:
    """Fetch news from backend.data.sources.briefing.fetch_news if available."""
    try:
        from backend.data.sources import briefing
        fn = getattr(briefing, "fetch_news", None)
        if fn:
            return fn()
    except Exception:
        pass
    return []


def _generate_briefing(news: list, days: int) -> str:
    """Generate briefing text. Currently returns a placeholder."""
    if not news:
        return "暂无足够新闻数据生成周报。"
    return f"近{days}日共{len(news)}条新闻，详情见列表。"


def _time_range(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"
