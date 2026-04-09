"""Briefing service — orchestration layer for news + AI briefing.

All caching logic moved to briefing_cache.py.
This module only handles: public API, SSE streaming, confidence extraction.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator

from backend.services import briefing_cache as _cache

logger = logging.getLogger(__name__)
BEIJING_TZ = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# Public API (backward-compatible — callers unchanged)
# ---------------------------------------------------------------------------

def get_briefing(days: int = 3) -> dict:
    """Return cached briefing + news. Each layer refreshed independently on its own TTL."""
    news = _cache.get_news(days)
    three_layers = _cache.run_three_layers(news, days)
    return {
        "weekly": {
            "layer3": three_layers["layer3"],
            "layer2": three_layers["layer2"],
            "layer1": three_layers["layer1"],
            "confidence": _cache.extract_confidence(three_layers),
            "time_range": _cache.time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def get_layer1(days: int = 3) -> dict:
    news = _cache.get_news(days)
    current_price = _cache._fetch_current_price()
    layer1 = _cache.get_layer1(news, days, current_price)
    return {"layer": "layer1", "content": layer1, "news": news, "news_count": len(news)}


def get_layer2(days: int = 3) -> dict:
    news = _cache.get_news(days)
    three_layers = _cache.run_three_layers(news, days)
    return {"layer": "layer2", "content": three_layers["layer2"]}


def get_layer3(days: int = 3) -> dict:
    news = _cache.get_news(days)
    three_layers = _cache.run_three_layers(news, days)
    return {
        "layer": "layer3",
        "content": three_layers["layer3"],
        "time_range": _cache.time_range(days),
    }


def refresh_news(days: int = 3) -> dict:
    """Force refresh news and all briefing layers."""
    news = _cache.refresh_news(days)
    three_layers = _cache.run_three_layers(news, days)
    return {
        "weekly": {
            "layer3": three_layers["layer3"],
            "layer2": three_layers["layer2"],
            "layer1": three_layers["layer1"],
            "confidence": _cache.extract_confidence(three_layers),
            "time_range": _cache.time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def refresh_briefing_only(days: int = 3) -> dict:
    """Force regenerate all briefing layers only, keep existing news."""
    news = _cache.get_news(days)
    _cache.bust_all_caches()
    three_layers = _cache.run_three_layers(news, days)
    return {
        "weekly": {
            "layer3": three_layers["layer3"],
            "layer2": three_layers["layer2"],
            "layer1": three_layers["layer1"],
            "confidence": _cache.extract_confidence(three_layers),
            "time_range": _cache.time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

async def briefing_stream(days: int) -> AsyncGenerator[dict, None]:
    """流式生成 briefing 事件。固定 3 小时间隔，结果持久化到数据库。

    Yields:
        {"type": "token", "block": "l12"|"l3", "chunk": str}
        {"type": "block-done", "block": "l12"|"l3"}
        {"type": "done", "blocks": {"l12": str, "l3": str}, "news": list}
        {"type": "cached", "blocks": {"l12": str, "l3": str}}
    """
    from backend.repositories.briefing_repo import can_generate, get_recent, save
    if not can_generate(days):
        cached = get_recent(days)
        if cached:
            yield {"type": "cached", "blocks": {"l12": cached["l12_content"], "l3": cached["l3_content"]}}
            return

    from backend.services.news_service import get_news as ns_get_news
    from backend.data.sources.briefing import call_claude_cli_streaming, build_l12_prompt, build_l3_prompt

    news, kline_data, current_price = await asyncio.gather(
        asyncio.to_thread(lambda: ns_get_news(days=days)),
        asyncio.to_thread(lambda: _cache.safe_fetch_kline()),
        asyncio.to_thread(_cache._fetch_current_price),
    )

    kline_summary = "（K线数据暂不可用）" if not kline_data else _cache.aggregate_kline(kline_data)

    l12_prompt = build_l12_prompt(news, current_price, kline_summary)
    l12_full = ""
    l3_full = ""

    # L12 stream
    try:
        async for chunk in call_claude_cli_streaming(l12_prompt):
            l12_full += chunk
            yield {"type": "token", "block": "l12", "chunk": chunk}
        yield {"type": "block-done", "block": "l12"}
    except Exception as e:
        logger.warning(f"L12 streaming failed: {e}")
        l12_full = f"近{days}日共{len(news)}条新闻，AI 分析生成失败。"
        yield {"type": "block-done", "block": "l12"}

    # L3 stream
    l3_prompt = build_l3_prompt(l12_full)
    try:
        async for chunk in call_claude_cli_streaming(l3_prompt):
            l3_full += chunk
            yield {"type": "token", "block": "l3", "chunk": chunk}
        yield {"type": "block-done", "block": "l3"}
    except Exception as e:
        logger.warning(f"L3 streaming failed: {e}")
        l3_full = "金价预期生成失败。"
        yield {"type": "block-done", "block": "l3"}

    save(days, l12_full, l3_full, news)
    yield {"type": "done", "blocks": {"l12": l12_full, "l3": l3_full}, "news": news}
