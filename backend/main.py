"""FastAPI main application."""
import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import price, sse, rss
from backend.data.db import init_db
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_PATH = os.environ.get("FRONTEND_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(_news_refresh_loop())
    asyncio.create_task(_price_bars_fetch_loop())
    asyncio.create_task(_briefing_loop())
    logger.info("Gold Dashboard started")
    yield


async def _briefing_loop():
    """每小时01分触发AI简报生成（分析上一小时新闻）。"""
    from datetime import datetime, timedelta
    from backend.alerts.checker import _generate_briefing_scheduled
    while True:
        now = datetime.now()
        next_hour = now.replace(minute=1, second=0, microsecond=0)
        if now.minute >= 1:
            next_hour = next_hour + timedelta(hours=1)
        wait = (next_hour - now).total_seconds()
        await asyncio.sleep(max(wait, 0))
        try:
            await _generate_briefing_scheduled()
        except Exception as e:
            logger.warning(f"Briefing loop error: {e}")
        await asyncio.sleep(3600)


async def _news_refresh_loop():
    """Background loop: refresh Futu news every 5 minutes."""
    from backend.data.sources.futu import fetch_futu_news, _sync_save_news
    while True:
        try:
            news = await asyncio.to_thread(fetch_futu_news)
            if news:
                threading.Thread(target=_sync_save_news, args=(news,), daemon=True).start()
        except Exception:
            pass
        await asyncio.sleep(300)


async def _price_bars_fetch_loop():
    """Background loop: fetch current price every 1 minute and store as 1m bar with full OHLC."""
    from backend.data.db import save_price_bar, save_usdcny
    from backend.data.sources.binance import fetch_xauusd
    from backend.data.sources.erapi import fetch_usdcny
    from backend.data.sources.domestic import fetch_au9999

    while True:
        bar_ts = int(time.time()) // 60 * 60  # 1分钟时间戳
        try:
            xau = await asyncio.to_thread(fetch_xauusd)
            if xau:
                await save_price_bar(
                    symbol="XAUUSD",
                    ts=bar_ts,
                    open_=xau["open"],
                    high=xau["high"],
                    low=xau["low"],
                    close=xau["price"],
                )
                logger.info(f"Stored XAUUSD bar at {bar_ts}")
        except Exception as e:
            logger.warning(f"XAUUSD bar error: {e}")

        try:
            au = await fetch_au9999()
            if au:
                await save_price_bar(
                    symbol="AU9999",
                    ts=bar_ts,
                    open_=au["open"],
                    high=au["high"],
                    low=au["low"],
                    close=au["price"],
                )
                logger.info(f"Stored AU9999 bar at {bar_ts}")
        except Exception as e:
            logger.warning(f"AU9999 bar error: {e}")

        try:
            fx = await asyncio.to_thread(fetch_usdcny)
            if fx:
                await save_usdcny(price=fx["price"], ts=bar_ts)
                logger.info(f"Stored USDCNY bar at {bar_ts}")
        except Exception as e:
            logger.warning(f"USDCNY bar error: {e}")

        await asyncio.sleep(60)


app = FastAPI(title="Gold Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")

app.include_router(price.router)
app.include_router(sse.router)
app.include_router(rss.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    with open(f"{FRONTEND_PATH}/index.html") as f:
        return f.read()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
