"""Three-layer briefing cache — extracted from briefing_service.py.

Handles all in-memory cache management (news + L1/L2 layers).
briefing_service.py imports from here for the caching logic.
"""
import asyncio
import importlib
import logging
import time

logger = logging.getLogger(__name__)

_NEWS_TTL = 1800        # 30 minutes — news cache TTL
_LAYER_TTL = 10800      # 3 hours — L1+L2 layer cache TTL

_news_cache: dict[int, dict] = {}
_layer_cache: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

def bust_cache(days: int) -> None:
    """Clear cached news and layers for a specific days value."""
    _news_cache.pop(days, None)
    _layer_cache.pop(days, None)


def bust_all_caches() -> None:
    """Clear all caches to force regeneration on next call."""
    _news_cache.clear()
    _layer_cache.clear()


# ---------------------------------------------------------------------------
# News cache
# ---------------------------------------------------------------------------

def get_news(days: int) -> list:
    """Return cached news, or fetch + cache if stale."""
    entry = _news_cache.get(days)
    if entry and (time.time() - entry["ts"]) < _NEWS_TTL:
        return entry["data"]
    news = _fetch_news(days)
    _news_cache[days] = {"ts": time.time(), "data": news}
    return news


def _fetch_news(days: int) -> list:
    """Fetch news via news_service."""
    from backend.services.news_service import get_news as ns_get_news
    return ns_get_news(days=days)


# ---------------------------------------------------------------------------
# Layer 1 + Layer 2 (generated together, shared 3h TTL)
# ---------------------------------------------------------------------------

def get_layer(news: list[dict], days: int) -> tuple[str, str]:
    """Get or generate Layer1 + Layer2 for given days. Both share 3h TTL."""
    entry = _layer_cache.get(days)
    if entry and (time.time() - entry["ts"]) < _LAYER_TTL:
        return entry["layer1"], entry["layer2"]

    current_price = _fetch_current_price()

    def _fetch_kline():
        from backend.data.sources import binance_kline
        return binance_kline.fetch_xauusd_kline()

    def _get_kline_summary(kline):
        if not kline:
            return "（K线数据暂不可用）"
        closes = [float(b["close"]) for b in kline if b.get("close")]
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
            f"共 {len(closes)} 个数据点"
        )

    async def _gen():
        mod = importlib.import_module("backend.data.sources.briefing")
        kline = await asyncio.to_thread(_fetch_kline)
        kline_summary = _get_kline_summary(kline)

        # Build L12 prompt with kline_summary injected
        prompt = mod.DAILY_PROMPT_TEMPLATE.format(
            news_count=len(news),
            news_list=mod._build_news_list(news),
            current_price=current_price,
            kline_summary=kline_summary,
        )
        layer1 = await mod.call_claude_cli_async(prompt)

        if not layer1:
            layer1 = f"近{days}日共{len(news)}条新闻，AI 分析生成失败。"

        # L2 from build_l3_prompt (which is actually the forecast prompt)
        l3_prompt = mod.build_l3_prompt(layer1)
        layer2 = await mod.call_claude_cli_async(l3_prompt)
        if not layer2:
            layer2 = "金价预期生成失败。"

        return layer1, layer2

    layer1, layer2 = asyncio.run(_gen())
    _layer_cache[days] = {"ts": time.time(), "layer1": layer1, "layer2": layer2}
    logger.info("Layer cache miss+regen: days=%d, L1=%d chars, L2=%d chars", days, len(layer1), len(layer2))
    return layer1, layer2


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


def time_range(days: int) -> str:
    """Return a human-readable time range string for the past N days (Beijing timezone)."""
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"
