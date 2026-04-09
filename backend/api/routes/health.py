"""Health check routes — verify each data source is reachable."""
import asyncio
import time
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


async def _check(name: str, coro) -> dict[str, Any]:
    """Run a coroutine with timeout, return status dict."""
    try:
        start = time.perf_counter()
        await asyncio.wait_for(coro, timeout=8.0)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        return {"name": name, "ok": True, "latency_ms": latency_ms}
    except asyncio.TimeoutError:
        return {"name": name, "ok": False, "latency_ms": None, "error": "timeout (>8s)"}
    except Exception as e:
        return {"name": name, "ok": False, "latency_ms": None, "error": str(e)[:120]}


# ---------------------------------------------------------------------------
# Price data source checks
# ---------------------------------------------------------------------------

async def _check_binance_ticker():
    from backend.data.sources import binance_kline
    binance_kline._fetch_ticker()


async def _check_sina_xau():
    from backend.data.sources import sina_xau
    sina_xau.fetch_xauusd_realtime()


async def _check_eastmoney_au():
    from backend.data.sources import eastmoney_au9999_price
    eastmoney_au9999_price.fetch_au9999_realtime()


async def _check_sina_au():
    from backend.data.sources import sina_au9999
    sina_au9999.fetch_au9999_realtime()


async def _check_yfinance():
    from backend.data.sources import yfinance_fx
    yfinance_fx.fetch_usdcny()


async def _check_sina_fx():
    from backend.data.sources import sina_fx
    sina_fx.fetch_usdcny()


# ---------------------------------------------------------------------------
# News source checks
# ---------------------------------------------------------------------------

async def _check_aastocks():
    from backend.data.sources import aastocks
    aastocks.fetch_aastocks_news()


async def _check_futu():
    from backend.data.sources import futu
    futu.fetch_futu_news()


async def _check_bernama():
    from backend.data.sources import bernama
    bernama.fetch_bernama_gold_news()


async def _check_cnbc():
    from backend.data.sources import cnbc
    cnbc.fetch_cnbc_news()


async def _check_local_news():
    from backend.data.sources import local_news
    local_news.fetch_local_news()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/sources")
async def health_sources():
    """
    Check all data sources in parallel.
    Returns a list of {name, ok, latency_ms, error?} objects.
    """
    checks = {
        # Price sources
        "binance_ticker":   _check_binance_ticker(),
        "sina_xau":         _check_sina_xau(),
        "eastmoney_au":     _check_eastmoney_au(),
        "sina_au":          _check_sina_au(),
        "yfinance_fx":      _check_yfinance(),
        "sina_fx":          _check_sina_fx(),
        # News sources
        "aastocks":         _check_aastocks(),
        "futu":             _check_futu(),
        "bernama":          _check_bernama(),
        "cnbc":             _check_cnbc(),
        "local_news":       _check_local_news(),
    }

    results = await asyncio.gather(*checks.values(), return_exceptions=True)

    sources = [
        r if not isinstance(r, Exception) else {"name": name, "ok": False, "latency_ms": None, "error": str(r)[:120]}
        for name, r in zip(checks.keys(), results)
    ]

    all_ok = all(s.get("ok", False) for s in sources)
    return {
        "status": "ok" if all_ok else "degraded",
        "sources": sources,
    }
