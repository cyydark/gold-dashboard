"""Three-layer briefing cache — extracted from briefing_service.py.

Handles all in-memory cache management (news + L1/L2 layers).
briefing_service.py imports from here for the caching logic.
"""
import asyncio
import importlib
import logging
import threading
import time

logger = logging.getLogger(__name__)

_NEWS_TTL = 1800        # 30 minutes — news cache TTL
_LAYER_TTL = 10800      # 3 hours — L1+L2 layer cache TTL

_news_cache: dict[int, dict] = {}
_layer_cache: dict[int, dict] = {}
_news_refresh_locks: dict[int, threading.Lock] = {}


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

def bust_cache(days: int) -> None:
    """Clear cached news and layers for a specific days value."""
    _news_cache.pop(days, None)
    _layer_cache.pop(days, None)
    _news_refresh_locks.pop(days, None)


def bust_all_caches() -> None:
    """Clear all caches to force regeneration on next call."""
    _news_cache.clear()
    _layer_cache.clear()
    _news_refresh_locks.clear()


# ---------------------------------------------------------------------------
# News cache
# ---------------------------------------------------------------------------

def get_news(days: int) -> list:
    """Return cached news, auto-fetch + write cache if cold or empty.

    Uses a per-days lock so concurrent callers share one fetch.
    """
    entry = _news_cache.get(days)
    if entry and (time.time() - entry["ts"]) < _NEWS_TTL:
        return entry["data"]

    lock = _news_refresh_locks.setdefault(days, threading.Lock())
    with lock:
        # Re-check after acquiring lock — another thread may have just populated it
        entry = _news_cache.get(days)
        if entry and (time.time() - entry["ts"]) < _NEWS_TTL:
            return entry["data"]
        news = _fetch_news(days)
        _news_cache[days] = {"ts": time.time(), "data": news}
        return news


def set_news(days: int, news: list) -> None:
    """Explicitly write news into cache. Called by /api/news for pre-warming."""
    _news_cache[days] = {"ts": time.time(), "data": news}


def _fetch_news(days: int) -> list:
    """Fetch news via news_service."""
    from backend.services.news_service import get_news as ns_get_news
    return ns_get_news(days=days)


# ---------------------------------------------------------------------------
# Layer 1 + Layer 2 (merged into single AI call)
# ---------------------------------------------------------------------------

def parse_layer_response(raw: str, days: int) -> tuple[str, str]:
    """Parse single AI response into layer1 and layer2 by splitting on 【金价预期】."""
    marker = "【金价预期】"
    idx = raw.find(marker)
    if idx > 0:
        before = raw[:idx].strip()
        after = raw[idx:].strip()
        # Remove --- and blank lines before the next section marker
        lines = before.splitlines()
        while lines and lines[-1].strip() in ("---", "* * *", "***", ""):
            lines.pop()
        return "\n".join(lines).strip(), after
    # Fallback: no marker found, treat all as layer1
    return raw.strip(), ""


def get_layer(news: list[dict], days: int) -> tuple[str, str]:
    """Get or generate Layer1 + Layer2. Both share 3h TTL.

    L1: 新闻 + K线 → 分析结论（新闻与走势是否吻合）
    L2: 从同一响应中解析金价预期
    """
    entry = _layer_cache.get(days)
    if entry and (time.time() - entry["ts"]) < _LAYER_TTL:
        return entry["layer1"], entry["layer2"]

    current_price = _fetch_current_price()

    def _fetch_kline():
        from backend.data.sources import binance_kline
        return binance_kline.fetch_xauusd_kline()

    async def _gen():
        mod = importlib.import_module("backend.data.sources.briefing")
        kline = await asyncio.to_thread(_fetch_kline)
        kline_summary = aggregate_kline(kline)

        # 一次调用：新闻 + K线 → 分析结论 + 金价预期
        prompt = mod.DAILY_PROMPT_TEMPLATE.format(
            news_count=len(news),
            news_list=mod._build_news_list(news),
            current_price=current_price,
            kline_summary=kline_summary,
        )
        raw = await mod.call_claude_cli_async(prompt)
        if not raw:
            return (
                f"近{days}日共{len(news)}条新闻，AI 分析生成失败。",
                "金价预期生成失败。",
            )
        layer1, layer2 = parse_layer_response(raw, days)
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
    from datetime import datetime, timedelta
    from backend.config import BEIJING_TZ
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"


def generated_at(days: int) -> str:
    """Return human-readable timestamp of when layer cache was last updated."""
    entry = _layer_cache.get(days)
    if not entry:
        return ""
    from datetime import datetime
    from backend.config import BEIJING_TZ
    return datetime.fromtimestamp(entry["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M")
