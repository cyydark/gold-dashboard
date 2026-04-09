"""Briefing service — news scrapers + AI briefing, in-memory cache.

Three independent layer caches with separate TTLs:
  - News cache: 10 min
  - Layer 1 (news briefing): 30 min
  - Layer 2 (cross-validation): 60 min
  - Layer 3 (price forecast): 15 min
"""
import asyncio
import json
import logging
import os
import time
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Environment keys to NEVER pass to subprocess (secrets / credentials)
_SENSITIVE_PATTERNS = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL",
    "API_KEY", "APIKEY", "OPENAI", "ANTHROPIC", "CLAUDE",
)
_SAFE_ENV_KEYS = frozenset({
    "PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL",
    "TMPDIR", "TEMP", "TMP", "PWD", "OLDPWD",
    "CLAUDE_CFG_DIR",   # claude CLI config dir
    "CLAUDE_API_KEY",   # explicitly allowed (claude CLI reads it)
})


def _safe_env() -> dict:
    """Return filtered os.environ, excluding secrets and allowing safe vars."""
    result = {}
    for k, v in os.environ.items():
        # Always include if in allow-list
        if k in _SAFE_ENV_KEYS:
            result[k] = v
            continue
        # Always exclude if matches a sensitive pattern
        for pat in _SENSITIVE_PATTERNS:
            if pat in k.upper():
                break
        else:
            result[k] = v
    return result

_NEWS_TTL = 600          # 10 minutes
_LAYER1_TTL = 1800      # 30 minutes
_LAYER2_TTL = 3600      # 60 minutes
_LAYER3_TTL = 900       # 15 minutes

_news_cache: dict = {"ts": 0, "data": None}
_layer1_cache: dict = {"ts": 0, "data": ""}
_layer2_cache: dict = {"ts": 0, "data": ""}
_layer3_cache: dict = {"ts": 0, "data": ""}


def get_layer1(days: int = 3) -> dict:
    """Return Layer 1 (news analysis) independently. Cached 30 min."""
    news = _get_news(days)
    current_price = _fetch_current_price()
    layer1 = _get_layer1(news, days, current_price)
    return {"layer": "layer1", "content": layer1, "news": news, "news_count": len(news)}


def get_layer2(days: int = 3) -> dict:
    """Return Layer 2 (kline validation). Cached 60 min."""
    news = _get_news(days)
    three_layers = _run_three_layers(news, days)
    return {"layer": "layer2", "content": three_layers["layer2"]}


def get_layer3(days: int = 3) -> dict:
    """Return Layer 3 (price forecast). Cached 15 min."""
    news = _get_news(days)
    three_layers = _run_three_layers(news, days)
    return {
        "layer": "layer3",
        "content": three_layers["layer3"],
        "time_range": _time_range(days),
    }


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
# Streaming briefing (SSE)
# ---------------------------------------------------------------------------

def _safe_fetch_kline() -> list[dict] | None:
    try:
        from backend.data.sources import binance_kline
        return binance_kline.fetch_xauusd_kline()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _time_range(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"


async def _read_stream_tokens(stdout: asyncio.StreamReader) -> AsyncGenerator[str, None]:
    """从流式 stdout 逐行解析，yield text chunk。"""
    async for line in stdout:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line.decode("utf-8"))
        except Exception:
            continue
        # 兼容两种格式
        result = data.get("result")
        if result and isinstance(result, dict):
            text = result.get("text")
            if text:
                yield text
                continue
        msg = data.get("message", {})
        if isinstance(msg, dict):
            for item in msg.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    t = item.get("text", "")
                    if t:
                        yield t


async def briefing_stream(days: int) -> AsyncGenerator[dict, None]:
    """流式生成 briefing 事件。固定 3 小时间隔，结果持久化到数据库。

    Yields:
        {"type": "token", "block": "l12"|"l3", "chunk": str}
        {"type": "block-done", "block": "l12"|"l3"}
        {"type": "done", "blocks": {"l12": str, "l3": str}, "news": list}
        {"type": "cached", "blocks": {"l12": str, "l3": str}}
    """
    # 数据库缓存命中（3小时间隔）
    from backend.repositories.briefing_repo import can_generate, get_recent, save
    if not can_generate(days):
        cached = get_recent(days)
        if cached:
            yield {"type": "cached", "blocks": {"l12": cached["l12_content"], "l3": cached["l3_content"]}}
            return

    # 并发拉取 Kline + 价格（新闻由前端独立 REST 接口加载）
    from backend.services.news_service import get_news as ns_get_news
    news, kline_data, current_price = await asyncio.gather(
        asyncio.to_thread(lambda: ns_get_news(days=days)),
        asyncio.to_thread(lambda: _safe_fetch_kline()),
        asyncio.to_thread(_fetch_current_price),
    )

    kline_summary = (
        "（K线数据暂不可用）"
        if not kline_data
        else _aggregate_kline(kline_data)
    )

    from backend.data.sources.briefing import build_l12_prompt, build_l3_prompt

    l12_prompt = build_l12_prompt(news, current_price, kline_summary)

    l12_proc = await asyncio.create_subprocess_exec(
        "claude", "-p", l12_prompt,
        "--output-format", "stream-json", "--verbose",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=_safe_env(),
    )

    l12_full = ""
    l3_full = ""

    try:
        # 1. L12 stream
        try:
            async for chunk in _read_stream_tokens(l12_proc.stdout):
                l12_full += chunk
                yield {"type": "token", "block": "l12", "chunk": chunk}
            yield {"type": "block-done", "block": "l12"}
        finally:
            await l12_proc.wait()
    except Exception:
        l12_proc.terminate()
        raise

    # 2. L3: price forecast (L12 as context)
    l3_prompt = build_l3_prompt(l12_full)
    l3_proc = await asyncio.create_subprocess_exec(
        "claude", "-p", l3_prompt,
        "--output-format", "stream-json", "--verbose",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=_safe_env(),
    )
    try:
        async for chunk in _read_stream_tokens(l3_proc.stdout):
            l3_full += chunk
            yield {"type": "token", "block": "l3", "chunk": chunk}
        yield {"type": "block-done", "block": "l3"}
    except Exception:
        l3_proc.terminate()
        raise
    finally:
        await l3_proc.wait()

    # 持久化到数据库
    save(days, l12_full, l3_full, news)
    yield {"type": "done", "blocks": {"l12": l12_full, "l3": l3_full}, "news": news}


def _aggregate_kline(klines: list[dict]) -> str:
    """简单聚合 K线 数据为一段文字（用于 prompt）。"""
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

