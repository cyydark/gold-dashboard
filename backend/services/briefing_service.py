"""Briefing service — news scrapers + AI briefing, in-memory cache.

Three independent layer caches with separate TTLs:
  - News cache: 10 min
  - Layer 1 (news briefing): 30 min
  - Layer 2 (cross-validation): 60 min
  - Layer 3 (price forecast): 15 min
"""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_NEWS_TTL = 600          # 10 minutes
_LAYER1_TTL = 1800      # 30 minutes
_LAYER2_TTL = 3600      # 60 minutes
_LAYER3_TTL = 900       # 15 minutes

_news_cache: dict = {"ts": 0, "data": None}
_layer1_cache: dict = {"ts": 0, "data": ""}
_layer2_cache: dict = {"ts": 0, "data": ""}
_layer3_cache: dict = {"ts": 0, "data": ""}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_briefing(days: int = 3) -> dict:
    """Return cached briefing + news. Each layer refreshed independently on its own TTL."""
    news = _get_news(days)
    three_layers = _run_three_layers(news, days)
    return {
        "weekly": {
            "layer3": three_layers["layer3"],
            "layer2": three_layers["layer2"],
            "layer1": three_layers["layer1"],
            "confidence": _extract_confidence(three_layers),
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def refresh_news(days: int = 3) -> dict:
    """Force refresh news. AI layers are refreshed independently on their own TTLs."""
    news = _fetch_news(days)
    _news_cache["data"] = news
    _news_cache["ts"] = time.time()

    three_layers = _run_three_layers(news, days)
    return {
        "weekly": {
            "layer3": three_layers["layer3"],
            "layer2": three_layers["layer2"],
            "layer1": three_layers["layer1"],
            "confidence": _extract_confidence(three_layers),
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def refresh_briefing_only(days: int = 3) -> dict:
    """Force regenerate all briefing layers only, keep existing news."""
    news = _get_news(days)

    # Bust all layer caches so _run_three_layers regenerates everything
    _layer1_cache["ts"] = 0
    _layer1_cache["data"] = ""
    _layer2_cache["ts"] = 0
    _layer2_cache["data"] = ""
    _layer3_cache["ts"] = 0
    _layer3_cache["data"] = ""

    three_layers = _run_three_layers(news, days)
    return {
        "weekly": {
            "layer3": three_layers["layer3"],
            "layer2": three_layers["layer2"],
            "layer1": three_layers["layer1"],
            "confidence": _extract_confidence(three_layers),
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


# ---------------------------------------------------------------------------
# News layer (unchanged)
# ---------------------------------------------------------------------------

def _get_news(days: int) -> list:
    if _news_cache["data"] is not None and (time.time() - _news_cache["ts"]) < _NEWS_TTL:
        return _news_cache["data"]
    news = _fetch_news(days)
    _news_cache["data"] = news
    _news_cache["ts"] = time.time()
    return news


def _fetch_news(days: int) -> list:
    """Fetch news via news_service (filtered by days) and merge from all sources."""
    from backend.services.news_service import get_news as ns_get_news
    return ns_get_news(days=days)


# ---------------------------------------------------------------------------
# Layer helpers
# ---------------------------------------------------------------------------

def _fetch_current_price() -> str:
    """Fetch current XAUUSD price for Layer 1 prompt injection."""
    try:
        from backend.data.sources import binance_kline
        ticker = binance_kline._fetch_ticker()
        if ticker:
            return str(ticker["price"])
    except Exception:
        pass
    return "N/A"


def _get_layer1(news: list[dict], days: int, current_price: str) -> str:
    """Layer 1 cache with 30-min TTL."""
    if (
        _layer1_cache["data"] != ""
        and (time.time() - _layer1_cache["ts"]) < _LAYER1_TTL
    ):
        return _layer1_cache["data"]
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer1 = asyncio.run(mod.generate_daily_briefing_from_news(news, current_price))
    _layer1_cache["data"] = layer1
    _layer1_cache["ts"] = time.time()
    return layer1


def _get_layer2(layer1: str, kline_data: list[dict] | None) -> str:
    """Layer 2 cache with 60-min TTL. Falls back to 'signal insufficient' if kline unavailable."""
    if (
        _layer2_cache["data"] != ""
        and (time.time() - _layer2_cache["ts"]) < _LAYER2_TTL
    ):
        return _layer2_cache["data"]
    if not kline_data:
        fallback = "【验证结果】信号不足\n【实际走势】K线数据暂不可用\n【分歧说明】\n【验证置信度】低"
        _layer2_cache["data"] = fallback
        _layer2_cache["ts"] = time.time()
        return fallback
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer2 = asyncio.run(mod.generate_cross_validation(layer1, kline_data))
    if not layer2:
        layer2 = "【验证结果】信号不足\n【实际走势】分析生成失败\n【分歧说明】\n【验证置信度】低"
    _layer2_cache["data"] = layer2
    _layer2_cache["ts"] = time.time()
    return layer2


def _get_layer3(layer1: str, layer2: str) -> str:
    """Layer 3 cache with 15-min TTL."""
    if (
        _layer3_cache["data"] != ""
        and (time.time() - _layer3_cache["ts"]) < _LAYER3_TTL
    ):
        return _layer3_cache["data"]
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer3 = asyncio.run(mod.generate_price_forecast(layer1, layer2))
    _layer3_cache["data"] = layer3
    _layer3_cache["ts"] = time.time()
    return layer3


# ---------------------------------------------------------------------------
# Core: three-layer pipeline
# ---------------------------------------------------------------------------

def _run_three_layers(news: list[dict], days: int) -> dict:
    """Run all three layers sequentially and cache each independently."""
    if not news:
        return {"layer1": "暂无足够新闻数据生成分析。", "layer2": "", "layer3": ""}

    # Step 1: Layer 1 (concurrent with Kline fetch)
    current_price = _fetch_current_price()

    async def _layer1_task() -> tuple[str, list[dict] | None]:
        async def gen() -> str:
            import importlib
            mod = importlib.import_module("backend.data.sources.briefing")
            return await mod.generate_daily_briefing_from_news(news, current_price)

        def fetch_kline():
            from backend.data.sources import binance_kline
            return binance_kline.fetch_xauusd_kline()

        results = await asyncio.gather(
            asyncio.to_thread(fetch_kline),
            gen(),
            return_exceptions=True,
        )
        kline_data = results[0] if not isinstance(results[0], Exception) else None
        layer1 = results[1] if not isinstance(results[1], Exception) else ""
        if not layer1:
            layer1 = f"近{days}日共{len(news)}条新闻，详情见列表。"
        return (layer1, kline_data)

    layer1, kline_data = asyncio.run(_layer1_task())

    # Step 2: Layer 2
    layer2 = _get_layer2(layer1, kline_data)

    # Step 3: Layer 3
    layer3 = _get_layer3(layer1, layer2)

    logger.info(
        f"Three-layer analysis: L1={len(layer1)} chars, "
        f"L2={len(layer2)} chars, L3={len(layer3)} chars"
    )
    return {"layer1": layer1, "layer2": layer2, "layer3": layer3}


# ---------------------------------------------------------------------------
# Confidence extraction
# ---------------------------------------------------------------------------

def _extract_confidence(three_layers: dict) -> str:
    """Extract overall confidence: prefer Layer 3, fall back to Layer 2."""
    for layer_key in ("layer3", "layer2"):
        text = three_layers.get(layer_key, "")
        if not text:
            continue
        for line in text.split("\n"):
            if "置信度" in line:
                for kw in ["高", "中", "低"]:
                    if kw in line:
                        return kw
    return "低"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _time_range(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"
