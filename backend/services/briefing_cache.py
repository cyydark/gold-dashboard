"""Three-layer briefing cache — extracted from briefing_service.py.

Handles all in-memory cache management (news + L1/L2/L3 layers).
briefing_service.py imports from here for the caching logic.
"""
import asyncio
import importlib
import logging
import time

logger = logging.getLogger(__name__)

_NEWS_TTL = 600          # 10 minutes
_LAYER1_TTL = 1800       # 30 minutes
_LAYER2_TTL = 3600       # 60 minutes
_LAYER3_TTL = 900        # 15 minutes

_news_cache: dict = {"ts": 0, "data": None}
_layer1_cache: dict = {"ts": 0, "data": ""}
_layer2_cache: dict = {"ts": 0, "data": ""}
_layer3_cache: dict = {"ts": 0, "data": ""}


def bust_all_caches():
    """Clear all layer caches to force regeneration on next call."""
    _layer1_cache["ts"] = 0; _layer1_cache["data"] = ""
    _layer2_cache["ts"] = 0; _layer2_cache["data"] = ""
    _layer3_cache["ts"] = 0; _layer3_cache["data"] = ""


# ---------------------------------------------------------------------------
# News cache
# ---------------------------------------------------------------------------

def get_news(days: int) -> list:
    """Return cached news, or fetch + cache if stale."""
    if _news_cache["data"] is not None and (time.time() - _news_cache["ts"]) < _NEWS_TTL:
        return _news_cache["data"]
    news = _fetch_news(days)
    _news_cache["data"] = news
    _news_cache["ts"] = time.time()
    return news


def fetch_news(days: int) -> list:
    """Fetch news via news_service and merge from all sources."""
    from backend.services.news_service import get_news as ns_get_news
    return ns_get_news(days=days)


def refresh_news(days: int) -> list:
    """Force-refresh news cache (ignores TTL). Returns fresh news list."""
    news = fetch_news(days)
    _news_cache["data"] = news
    _news_cache["ts"] = time.time()
    return news


# ---------------------------------------------------------------------------
# Layer 1 (news analysis)
# ---------------------------------------------------------------------------

def get_layer1(news: list[dict], days: int, current_price: str) -> str:
    """Layer 1 cache with 30-min TTL."""
    if _layer1_cache["data"] != "" and (time.time() - _layer1_cache["ts"]) < _LAYER1_TTL:
        return _layer1_cache["data"]
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer1 = asyncio.run(mod.generate_daily_briefing_from_news(news, current_price))
    _layer1_cache["data"] = layer1
    _layer1_cache["ts"] = time.time()
    return layer1


# ---------------------------------------------------------------------------
# Layer 2 (kline cross-validation)
# ---------------------------------------------------------------------------

def get_layer2(layer1: str, kline_data: list[dict] | None) -> str:
    """Layer 2 cache with 60-min TTL. Falls back to 'signal insufficient' if kline unavailable."""
    if _layer2_cache["data"] != "" and (time.time() - _layer2_cache["ts"]) < _LAYER2_TTL:
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


# ---------------------------------------------------------------------------
# Layer 3 (price forecast)
# ---------------------------------------------------------------------------

def get_layer3(layer1: str, layer2: str) -> str:
    """Layer 3 cache with 15-min TTL."""
    if _layer3_cache["data"] != "" and (time.time() - _layer3_cache["ts"]) < _LAYER3_TTL:
        return _layer3_cache["data"]
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer3 = asyncio.run(mod.generate_price_forecast(layer1, layer2))
    _layer3_cache["data"] = layer3
    _layer3_cache["ts"] = time.time()
    return layer3


# ---------------------------------------------------------------------------
# Three-layer pipeline
# ---------------------------------------------------------------------------

def run_three_layers(news: list[dict], days: int) -> dict:
    """Run all three layers sequentially, caching each independently."""
    if not news:
        return {"layer1": "暂无足够新闻数据生成分析。", "layer2": "", "layer3": ""}

    current_price = _fetch_current_price()

    # Layer 1 (concurrent with Kline fetch)
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

    # Layer 2
    layer2 = get_layer2(layer1, kline_data)

    # Layer 3
    layer3 = get_layer3(layer1, layer2)

    logger.info(
        f"Three-layer analysis: L1={len(layer1)} chars, "
        f"L2={len(layer2)} chars, L3={len(layer3)} chars"
    )
    return {"layer1": layer1, "layer2": layer2, "layer3": layer3}


# ---------------------------------------------------------------------------
# Confidence extraction
# ---------------------------------------------------------------------------

def extract_confidence(three_layers: dict) -> str:
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


def safe_fetch_kline() -> list[dict] | None:
    """Safely fetch Kline data, returning None on failure."""
    try:
        from backend.data.sources import binance_kline
        return binance_kline.fetch_xauusd_kline()
    except Exception:
        return None


def time_range(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"


def aggregate_kline(klines: list[dict]) -> str:
    """Simple Kline aggregation for prompts."""
    if not klines:
        return "（K线数据暂不可用）"
    closes = [float(b["close"]) for b in klines if b.get("close")]
    if not closes:
        return "（K线数据暂不可用）"
    latest = closes[-1]
    earliest = closes[0]
    change = latest - earliest
    pct = (change / earliest * 100) if earliest else 0
    direction = "上涨" if change >= 0 else "下跌"
    return (
        f"价格区间 {min(closes):.2f}–{max(closes):.2f}，"
        f"最新 {latest:.2f}，{direction} {abs(change):.2f} ({abs(pct):.2f}%)，"
        f"共 {len(klines)} 个数据点"
    )

