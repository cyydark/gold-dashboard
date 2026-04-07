"""Briefing service — news scrapers + AI briefing, in-memory cache.

News cache (10 min) and briefing cache (1 hour) are independent.
"""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_NEWS_TTL = 600       # 10 minutes
_ANALYSIS_TTL = 3600  # 1 hour

_news_cache: dict = {"ts": 0, "data": None}
_analysis_cache: dict = {"ts": 0, "data": {"news_analysis": "", "cross_validation": ""}}


def get_briefing(days: int = 3) -> dict:
    """Return cached briefing + news. Each refreshed independently on TTL."""
    news = _get_news(days)
    analysis = _get_briefing(news, days)
    content = analysis["cross_validation"] or analysis["news_analysis"]
    return {
        "weekly": {
            "content": content,
            "news_analysis": analysis["news_analysis"],
            "cross_validation": analysis["cross_validation"],
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


def _get_briefing(news: list, days: int) -> dict:
    if (
        _analysis_cache["data"] is not None
        and _analysis_cache["data"]["news_analysis"] != ""
        and (time.time() - _analysis_cache["ts"]) < _ANALYSIS_TTL
    ):
        return _analysis_cache["data"]
    analysis = _generate_analysis(news, days)
    _analysis_cache["data"] = analysis
    _analysis_cache["ts"] = time.time()
    return analysis


def refresh_news(days: int = 3) -> dict:
    """Force refresh news. AI analysis is only regenerated when its TTL (1h) has expired."""
    news = _fetch_news(days)
    _news_cache["data"] = news
    _news_cache["ts"] = time.time()

    # AI 分析只在 TTL 过期时才重新生成
    analysis = _get_briefing(news, days)
    content = analysis["cross_validation"] or analysis["news_analysis"]
    return {
        "weekly": {
            "content": content,
            "news_analysis": analysis["news_analysis"],
            "cross_validation": analysis["cross_validation"],
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def refresh_briefing_only(days: int = 3) -> dict:
    """Force regenerate briefing only, keep existing news."""
    news = _get_news(days)
    analysis = _generate_analysis(news, days)
    _analysis_cache["data"] = analysis
    _analysis_cache["ts"] = time.time()
    content = analysis["cross_validation"] or analysis["news_analysis"]
    return {
        "weekly": {
            "content": content,
            "news_analysis": analysis["news_analysis"],
            "cross_validation": analysis["cross_validation"],
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


def _generate_analysis(news: list, days: int) -> dict:
    """Two-layer AI analysis.

    Step 1 (concurrent): news analysis + kline fetch.
    Step 2 (serial): cross-validation using Step 1 results.
    """
    if not news:
        return {
            "news_analysis": "暂无足够新闻数据生成分析。",
            "cross_validation": "",
        }

    # --- Step 1: concurrent ---
    async def _step1(news: list, days: int) -> tuple[str, list[dict] | None]:
        """Run news analysis and kline fetch concurrently."""
        mod = __import__("backend.data.sources.briefing", fromlist=[""])

        async def gen() -> str:
            fn = getattr(mod, "generate_daily_briefing_from_news")
            return await fn(news)

        def fetch_kline() -> list[dict] | None:
            from backend.data.sources import binance_kline
            return binance_kline.fetch_xauusd_kline()

        kline_data: list[dict] | None = None
        news_analysis = ""

        results = await asyncio.gather(
            gen(),
            asyncio.to_thread(fetch_kline),
            return_exceptions=True,
        )
        news_analysis_result, kline_result = results
        news_analysis = news_analysis_result if not isinstance(news_analysis_result, Exception) else ""
        kline_data = kline_result if not isinstance(kline_result, Exception) else None

        # Only retry the one that failed
        if not news_analysis:
            try:
                news_analysis = await gen()
            except Exception:
                pass
        if kline_data is None:
            try:
                kline_data = asyncio.to_thread(fetch_kline)
            except Exception:
                pass

        if not news_analysis:
            logger.warning("News analysis empty, falling back")
            news_analysis = f"近{days}日共{len(news)}条新闻，详情见列表。"

        return (news_analysis, kline_data)

    news_analysis, kline_data = asyncio.run(_step1(news, days))

    # --- Step 2: serial cross-validation ---
    cross_validation = ""
    if kline_data:
        try:
            fn = getattr(__import__("backend.data.sources.briefing", fromlist=[""]), "generate_cross_validation")
            cross_validation = asyncio.run(fn(news_analysis, kline_data))
        except Exception as e:
            logger.warning(f"Cross-validation failed: {e}")
            cross_validation = ""
    # kline_data is None → cross_validation stays ""

    logger.info(
        f"Analysis generated: {len(news)} news, "
        f"news_analysis={len(news_analysis)} chars, "
        f"cross_validation={len(cross_validation)} chars, "
        f"kline={'ok' if kline_data else 'N/A'}"
    )
    return {
        "news_analysis": news_analysis,
        "cross_validation": cross_validation,
    }


def _time_range(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"
