"""FastAPI main application."""
import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.data import constants as c
from backend.api.routes import price, news, briefing, sse
from backend.data.db import init_db
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_PATH = os.environ.get("FRONTEND_PATH", str(settings.frontend_path))


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
        await asyncio.sleep(c.BRIEFING_LOOP_SLEEP)


async def _news_refresh_loop():
    """Background loop: refresh all configured news sources every 5 minutes."""
    import importlib
    while True:
        try:
            from backend.data.sources import NEWS_SOURCES
            for name, (module_path, fn_name) in NEWS_SOURCES.items():
                mod = importlib.import_module(module_path)
                fetch_fn = getattr(mod, fn_name)
                save_fn = getattr(mod, "_sync_save_news")
                news = await asyncio.to_thread(fetch_fn)
                if news:
                    threading.Thread(target=save_fn, args=(news,), daemon=True).start()
        except Exception as e:
            logger.warning(f"News refresh error: {e}")
        await asyncio.sleep(c.REFRESH_INTERVAL)


async def _price_bars_fetch_loop():
    """Background loop: fetch data from configured sources every 5 minutes.

    Sources are defined in backend.data.sources.SOURCES.
    Adding/switching a source only requires updating that config dict.
    """
    import importlib

    while True:
        try:
            from backend.repositories.price_repository import PriceRepository
            from backend.data.sources import SOURCES
            repo = PriceRepository()

            for symbol, (module_path, fn_name) in SOURCES.items():
                mod = importlib.import_module(module_path)
                fn = getattr(mod, fn_name)
                bars = await asyncio.to_thread(fn)
                if bars:
                    for b in bars:
                        await repo.save(
                            symbol=symbol,
                            ts=b["time"],
                            open_=b["open"],
                            high=b["high"],
                            low=b["low"],
                            price=b["close"],
                            change=b.get("change", 0),
                            pct=b.get("pct", 0),
                        )
                    logger.info(f"Synced {len(bars)} {symbol} bars from {module_path}")
        except Exception as e:
            logger.warning(f"Price sync error: {e}")

        await asyncio.sleep(c.REFRESH_INTERVAL)


app = FastAPI(title="Gold Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")

app.include_router(price.router)
app.include_router(news.router)
app.include_router(briefing.router)
app.include_router(sse.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    with open(f"{FRONTEND_PATH}/index.html") as f:
        return f.read()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
