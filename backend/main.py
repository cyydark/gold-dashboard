"""FastAPI main application."""
import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import price, alert, sse
from backend.data.db import init_db
from backend.alerts.checker import start_scheduler, get_triggered_alerts, get_cached_news
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_PATH = os.environ.get("FRONTEND_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Launch each prewarm in its own thread — Playwright spawns a separate
    # Chrome process per thread, so all 3 windows run truly in parallel.
    # Server accepts requests immediately; full prewarm completes in ~17s
    # (1 window time) instead of ~51s (3 × sequential).
    def thread(fn, *args):
        t = threading.Thread(target=fn, args=args, daemon=True)
        t.start()
        return t

    # All 3 windows via yfinance — no Playwright, no Google Finance
    def prewarm_1d():
        from backend.data.sources.international import fetch_xauusd_history
        fetch_xauusd_history(1)
        logger.info("1-day history prewarmed")

    def prewarm_5d():
        from backend.data.sources.international import fetch_xauusd_history
        fetch_xauusd_history(5)
        logger.info("5-day history prewarmed")

    def prewarm_30d():
        from backend.data.sources.international import fetch_xauusd_history
        fetch_xauusd_history(30)
        logger.info("30-day history prewarmed")

    async def prewarm_news():
        from backend.alerts.checker import _refresh_news
        await _refresh_news()

    thread(prewarm_1d)
    thread(prewarm_5d)
    thread(prewarm_30d)
    asyncio.create_task(prewarm_news())

    start_scheduler(interval_sec=30)
    logger.info("Gold Dashboard started")
    yield


app = FastAPI(title="Gold Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")

# Include routers
app.include_router(price.router)
app.include_router(alert.router)
app.include_router(sse.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    with open(f"{FRONTEND_PATH}/index.html") as f:
        return f.read()


@app.get("/api/alerts/triggered")
async def get_triggered():
    """Return currently triggered alerts."""
    return get_triggered_alerts()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
