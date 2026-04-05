"""Price and history API routes."""
import asyncio
from datetime import timedelta

from dotenv import load_dotenv
from fastapi import APIRouter
from backend.data.db import get_price_bars, get_latest_price_bar

load_dotenv()

router = APIRouter(prefix="/api", tags=["price"])


@router.get("/prices")
async def get_prices():
    """Fetch current prices from latest price_bars rows."""
    from backend.data.db import get_latest_price_bar
    from datetime import datetime, timezone, timedelta

    BEIJING_TZ = timezone(timedelta(hours=8))

    xau_bar = await get_latest_price_bar("XAUUSD")
    au_bar = await get_latest_price_bar("AU9999")
    fx_bar = await get_latest_price_bar("USDCNY")

    result = {}

    if xau_bar:
        result["XAUUSD"] = {
            "symbol": "XAUUSD",
            "name": "国际黄金 XAU/USD",
            "price": round(xau_bar["price"], 2),
            "change": round(xau_bar.get("change", 0), 2),
            "pct": round(xau_bar.get("pct", 0), 2),
            "open": round(xau_bar["open"], 2),
            "high": round(xau_bar["high"], 2),
            "low": round(xau_bar["low"], 2),
            "unit": "USD/oz",
            "updated_at": datetime.fromtimestamp(xau_bar["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
        }

    if au_bar:
        result["AU9999"] = {
            "symbol": "AU9999",
            "name": "国内黄金 AU9999",
            "price": round(au_bar["price"], 2),
            "change": round(au_bar.get("change", 0), 2),
            "pct": round(au_bar.get("pct", 0), 2),
            "open": round(au_bar["open"], 2),
            "high": round(au_bar["high"], 2),
            "low": round(au_bar["low"], 2),
            "unit": "CNY/g",
            "updated_at": datetime.fromtimestamp(au_bar["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
        }

    if fx_bar:
        result["USDCNY"] = {
            "symbol": "USDCNY",
            "name": "人民币兑美元 CNY/USD",
            "price": round(fx_bar["price"], 4),
            "change": round(fx_bar.get("change", 0), 4),
            "pct": round(fx_bar.get("pct", 0), 4),
            "open": round(fx_bar["open"], 4),
            "high": round(fx_bar["high"], 4),
            "low": round(fx_bar["low"], 4),
            "unit": "CNY/USD",
            "updated_at": datetime.fromtimestamp(fx_bar["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
        }

    return result


@router.get("/history/{symbol}")
async def get_history(symbol: str, days: int = 1):
    """Fetch price history from database (1m bars, aggregated from DB)."""
    symbol_map = {"XAUUSD": "XAUUSD", "AU9999": "AU9999"}
    db_symbol = symbol_map.get(symbol)
    if not db_symbol:
        return []

    rows = await get_price_bars(db_symbol, limit=2000)
    if not rows:
        return []

    # rows are newest-first; reverse for chart (oldest→newest)
    rows = list(reversed(rows))
    bars = [
        {"time": r["ts"], "open": round(r["open"], 2),
         "high": round(r["high"], 2), "low": round(r["low"], 2),
         "close": round(r["price"], 2)}
        for r in rows
    ]
    return {"bars": bars, "xMin": bars[0]["time"], "xMax": bars[-1]["time"]}


@router.get("/news")
async def get_news(days: int = 1):
    """Serve news from DB (filtered by days)."""
    from backend.data.db import get_news_items
    from backend.data.sources.futu import BEIJING_TZ
    from datetime import datetime

    db_news = await get_news_items(days)
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

    db_news.sort(key=lambda x: x.get("published_ts") or 0, reverse=True)
    return {"news": db_news}


@router.post("/news/refresh")
async def refresh_news():
    """手动抓取新闻并入库（富途 + Bernama）。"""
    from backend.data.sources.futu import fetch_futu_news, _sync_save_news as futu_save
    from backend.data.sources.bernama import fetch_bernama_gold_news, _sync_save_news as bernama_save
    loop = asyncio.get_event_loop()
    futu_news = await loop.run_in_executor(None, fetch_futu_news)
    bernama_news = await loop.run_in_executor(None, fetch_bernama_gold_news)
    total = len(futu_news) + len(bernama_news)
    if futu_news:
        await asyncio.to_thread(futu_save, futu_news)
    if bernama_news:
        await asyncio.to_thread(bernama_save, bernama_news)
    return {"count": total, "message": f"抓取到 {total} 条新闻（Futu: {len(futu_news)}, Bernama: {len(bernama_news)}）已入库"}


@router.get("/briefings")
async def get_briefings(limit: int = 24):
    """返回日报 + 近12小时简报 + 近1小时新闻。"""
    from backend.data.db import get_hourly_briefings, get_daily_briefing, get_news_last_hours
    from backend.data.sources.futu import BEIJING_TZ
    from datetime import datetime
    hourly = await get_hourly_briefings(limit)
    daily = await get_daily_briefing()
    news = await get_news_last_hours(hours=1, limit=20)
    now = datetime.now(BEIJING_TZ)
    one_hour_ago = now - timedelta(hours=1)
    time_window = f"{one_hour_ago.strftime('%H:%M')}~{now.strftime('%H:%M')}"
    return {"daily": daily, "hourly": hourly, "news": news, "time_window": time_window}


@router.post("/briefings/trigger")
async def trigger_briefing():
    """手动触发简报生成（调用自动逻辑）。"""
    from backend.alerts.checker import _generate_briefing_scheduled
    await _generate_briefing_scheduled()
    return {"status": "done"}
