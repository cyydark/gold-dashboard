"""Briefing service — no DB, pure in-memory cache."""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

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
    """Fetch news from available news sources."""
    all_news: list = []
    fetchers = [
        _fetch_bernama,
        _fetch_futu,
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


def _generate_briefing(news: list, days: int) -> str:
    """Generate briefing text using AI via Claude CLI."""
    if not news:
        return "暂无足够新闻数据生成周报。"
    try:
        import importlib
        mod = importlib.import_module("backend.data.sources.briefing")
        gen = getattr(mod, "generate_daily_briefing_from_news")
        content = asyncio.run(gen(news, ""))
        if content:
            logger.info(f"Briefing generated, {len(news)} news items, {len(content)} chars")
            return content
        logger.warning("Briefing empty, falling back")
    except Exception as e:
        logger.error(f"Briefing generation failed: {e}")
    return f"近{days}日共{len(news)}条新闻，详情见列表。"


def _time_range(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"
