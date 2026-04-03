"""Price and history API routes."""
import asyncio
from fastapi import APIRouter
from backend.data.sources.international import fetch_xauusd, fetch_usdcny, fetch_xauusd_history
from backend.alerts.checker import get_cached_news
from backend.data.sources.domestic import fetch_au9999

router = APIRouter(prefix="/api", tags=["price"])

OZ_TO_G = 31.1035
DEFAULT_CNY_RATE = 6.87


@router.get("/prices")
async def get_prices():
    """Fetch current prices for all tracked symbols."""
    loop = asyncio.get_event_loop()
    xau, au9999, usdcny = await asyncio.gather(
        loop.run_in_executor(None, fetch_xauusd),
        fetch_au9999(),
        loop.run_in_executor(None, fetch_usdcny),
    )

    result = {}
    updated = ""

    if xau:
        result["XAUUSD"] = xau
        updated = xau.get("updated_at", "")

    if au9999:
        result["AU9999"] = au9999
        if not updated:
            updated = au9999.get("updated_at", "")

    if usdcny:
        result["USDCNY"] = usdcny
        if not updated:
            updated = usdcny.get("updated_at", "")

    result["updated_at"] = updated
    return result


@router.get("/history/{symbol}")
async def get_history(symbol: str, days: int = 1):
    """Fetch price history via Google Finance batchexecute (GF fallback to yfinance).

    1 day:   5-min bars
    5 days:  15-min bars  (default — matches GF resolution)
    30+ days: daily bars
    """
    try:
        loop = asyncio.get_running_loop()
        yf_data = await loop.run_in_executor(None, fetch_xauusd_history, days)
        if not yf_data:
            return []

        if symbol == "XAUUSD":
            bars = [
                {"time": d["time"], "open": round(d["open"], 2),
                 "high": round(d["high"], 2), "low": round(d["low"], 2),
                 "close": round(d["close"], 2)}
                for d in yf_data
            ]
            x_min = yf_data[0]["time"] if yf_data else None
            x_max = yf_data[-1]["time"] if yf_data else None
            return {"bars": bars, "xMin": x_min, "xMax": x_max}

        if symbol == "AU9999":
            from backend.data.sources.international import _usdcny_cache
            cny_rate = (_usdcny_cache.get("data") or {}).get("price") or DEFAULT_CNY_RATE
            bars = [
                {"time": d["time"],
                 "open": round(d["open"] * cny_rate / OZ_TO_G, 2),
                 "high": round(d["high"] * cny_rate / OZ_TO_G, 2),
                 "low": round(d["low"] * cny_rate / OZ_TO_G, 2),
                 "close": round(d["close"] * cny_rate / OZ_TO_G, 2)}
                for d in yf_data
            ]
            x_min = yf_data[0]["time"] if yf_data else None
            x_max = yf_data[-1]["time"] if yf_data else None
            return {"bars": bars, "xMin": x_min, "xMax": x_max}
    except Exception:
        pass
    return []


@router.get("/news")
async def get_news(days: int = 1):
    """Serve cached news from DB (filtered by days), fallback to background cache."""
    from backend.data.db import get_news_items
    from datetime import datetime
    db_news = await get_news_items(days)
    if db_news:
        # published_at was stored as Beijing time; re-attach TZ then convert to ts
        from backend.data.sources.international import BEIJING_TZ
        for item in db_news:
            try:
                pub = item.get("published_at", "")
                if pub:
                    naive = datetime.fromisoformat(pub)
                    aware = naive.replace(tzinfo=BEIJING_TZ)
                    item["published_ts"] = int(aware.timestamp())
                else:
                    item["published_ts"] = None
            except Exception:
                item["published_ts"] = None
        # Sort by published_ts ascending (nulls last)
        db_news.sort(key=lambda x: x.get("published_ts") or 0)
        return {"news": db_news}
    return {"news": get_cached_news() or []}
