"""Price and history API routes."""
import asyncio
import os

from dotenv import load_dotenv
from fastapi import APIRouter
from backend.data.sources.international import fetch_xauusd, fetch_usdcny, fetch_xauusd_history
from backend.data.sources.domestic import fetch_au9999, fetch_au9999_history
from backend.alerts.checker import get_cached_news

load_dotenv()

router = APIRouter(prefix="/api", tags=["price"])

DEFAULT_CNY_RATE = float(os.environ.get("DEFAULT_CNY_RATE", "6.87"))


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
    """Fetch price history.

    XAUUSD: Binance XAUT/USDT klines
    AU9999: Shanghai Gold Exchange daily bars
    """
    try:
        loop = asyncio.get_running_loop()

        if symbol == "XAUUSD":
            yf_data = await loop.run_in_executor(None, fetch_xauusd_history, days)
            if not yf_data:
                return []
            bars = [
                {"time": d["time"], "open": round(d["open"], 2),
                 "high": round(d["high"], 2), "low": round(d["low"], 2),
                 "close": round(d["close"], 2)}
                for d in yf_data
            ]
            return {"bars": bars, "xMin": yf_data[0]["time"], "xMax": yf_data[-1]["time"]}

        if symbol == "AU9999":
            sge_data = await loop.run_in_executor(None, fetch_au9999_history, days)
            if not sge_data:
                return []
            bars = [
                {"time": d["time"], "open": round(d["open"], 2),
                 "high": round(d["high"], 2), "low": round(d["low"], 2),
                 "close": round(d["close"], 2)}
                for d in sge_data
            ]
            return {"bars": bars, "xMin": sge_data[0]["time"], "xMax": sge_data[-1]["time"]}
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
        # Sort by published_ts descending (newest first, nulls last)
        db_news.sort(key=lambda x: x.get("published_ts") or 0, reverse=True)
        return {"news": db_news}
    cached = get_cached_news() or []
    # Sort cached news descending (newest first)
    cached.sort(key=lambda x: x.get("published_ts") or 0, reverse=True)
    return {"news": cached}


@router.get("/briefings")
async def get_briefings(limit: int = 24):
    """返回最近简报 + 对应时段的新闻（无匹配时降级返回最近新闻）。"""
    from backend.data.db import get_recent_briefings, get_recent_news
    briefings = await get_recent_briefings(limit)
    latest_hour = briefings[0]["time_range"] if briefings else None
    news = await get_recent_news(hour_range=latest_hour, limit=20)
    # hour_range 格式可能与存储的 news.hour_range 不完全匹配，降级取最近新闻
    if not news and latest_hour:
        news = await get_recent_news(limit=20)
    return {"briefings": briefings, "news": news}


@router.post("/briefings/trigger")
async def trigger_briefing():
    """手动触发简报生成（调用自动逻辑）。"""
    from backend.alerts.checker import _generate_briefing_scheduled
    await _generate_briefing_scheduled()
    return {"status": "done"}
