"""FastAPI main application."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.data import constants as c
from backend.api.routes import price, news, briefing, sse
from backend.api.limiter import limiter
from backend.api.models import ApiResponse
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
    """Background loop: refresh all configured news sources every REFRESH_INTERVAL seconds.

    All sources are fetched concurrently; saves run in background threads via
    asyncio.to_thread (non-blocking).
    """
    import importlib
    await asyncio.sleep(30)  # Wait 30s on startup before first fetch (let caches warm up)
    while True:
        try:
            from backend.data.sources import NEWS_SOURCES

            async def fetch_and_save(module_path: str, fn_name: str):
                mod = importlib.import_module(module_path)
                fetch_fn = getattr(mod, fn_name)
                save_fn = getattr(mod, "_sync_save_news")
                news = await asyncio.to_thread(fetch_fn)
                if news:
                    # save_fn is blocking (DB write); run in background
                    asyncio.get_event_loop().run_in_executor(None, save_fn, news)

            await asyncio.gather(
                *(fetch_and_save(mp, fn) for mp, fn in NEWS_SOURCES.values()),
                return_exceptions=True,
            )
        except Exception as e:
            logger.warning(f"News refresh error: {e}")
        await asyncio.sleep(c.REFRESH_INTERVAL)


async def _price_bars_fetch_loop():
    """Background loop: fetch price data from all configured sources every REFRESH_INTERVAL seconds.

    Sources are defined in backend.data.sources.SOURCES.
    所有 symbol 并发获取，每 symbol 用 save_many 批量写入。
    """
    import importlib
    while True:
        try:
            from backend.repositories.price_repository import PriceRepository
            from backend.data.sources import SOURCES
            repo = PriceRepository()

            async def fetch_and_save(symbol: str, module_path: str, fn_name: str):
                latest = await repo.get_latest(symbol)
                last_ts = latest["ts"] if latest else None
                mod = importlib.import_module(module_path)
                fn = getattr(mod, fn_name)
                bars = await asyncio.to_thread(fn)
                if not bars:
                    return 0
                if last_ts is not None:
                    bars = [b for b in bars if b["time"] > last_ts]
                if bars:
                    saved = await repo.save_many(bars, symbol)
                    logger.info(f"Synced {saved} {symbol} bars from {module_path}")
                    return saved
                return 0

            await asyncio.gather(
                *(fetch_and_save(sym, mp, fn) for sym, (mp, fn) in SOURCES.items()),
                return_exceptions=True,
            )
        except Exception as e:
            logger.warning(f"Price sync error: {e}")

        await asyncio.sleep(c.REFRESH_INTERVAL)


app = FastAPI(title="Gold Dashboard", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content=ApiResponse.error("Rate limit exceeded. Please slow down.", code="RATE_LIMITED"),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.warning(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ApiResponse.error("Internal server error", code="INTERNAL_ERROR"),
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
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
