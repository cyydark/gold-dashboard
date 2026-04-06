"""Briefing service — news scrapers + AI briefing, in-memory cache.

News cache (10 min) and briefing cache (1 hour) are independent.
"""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_NEWS_TTL = 600      # 10 minutes
_ANALYSIS_TTL = 3600  # 1 hour

_news_cache: dict = {"ts": 0, "data": None}
_analysis_cache: dict = {"ts": 0, "data": ""}


def get_briefing(days: int = 3) -> dict:
    """Return cached briefing + news. Each refreshed independently on TTL."""
    news = _get_news(days)
    brief = _get_briefing(news, days)
    return {
        "weekly": {
            "content": brief,
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def _get_news(days: int) -> list:
    if _news_cache["data"] is not None and (time.time() - _news_cache["ts"]) < _NEWS_TTL:
        return _news_cache["data"]
    news = _fetch_news(days)
    _news_cache["data"] = news
    _news_cache["ts"] = time.time()
    return news


def _get_briefing(news: list, days: int) -> str:
    if _analysis_cache["data"] is not None and (time.time() - _analysis_cache["ts"]) < _ANALYSIS_TTL:
        return _analysis_cache["data"]
    content = _generate_briefing(news, days)
    _analysis_cache["data"] = content
    _analysis_cache["ts"] = time.time()
    return content


def refresh_news(days: int = 3) -> dict:
    """Force refresh news. AI analysis is only regenerated when its TTL (1h) has expired."""
    news = _fetch_news(days)
    _news_cache["data"] = news
    _news_cache["ts"] = time.time()

    # AI 分析只在 TTL 过期时才重新生成
    brief = _get_briefing(news, days)
    return {
        "weekly": {
            "content": brief,
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def refresh_briefing_only(days: int = 3) -> dict:
    """Force regenerate briefing only, keep existing news."""
    news = _get_news(days)
    content = _generate_briefing(news, days)
    _analysis_cache["data"] = content
    _analysis_cache["ts"] = time.time()
    return {
        "weekly": {
            "content": content,
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def _fetch_news(days: int) -> list:
    """Fetch news via news_service (filtered by days) and merge from all sources."""
    from backend.services.news_service import get_news as ns_get_news
    return ns_get_news(days=days)


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
