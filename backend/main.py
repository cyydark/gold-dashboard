"""FastAPI main application."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import price, alert, sse
from backend.data.db import init_db
from backend.alerts.checker import start_scheduler, get_triggered_alerts, get_cached_news
import asyncio
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Frontend static files path — set via env var or default to sibling frontend/ dir
FRONTEND_PATH = os.environ.get("FRONTEND_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Pre-fetch news immediately so first request is fast
    from backend.alerts.checker import _refresh_news
    asyncio.create_task(_refresh_news())

    start_scheduler(interval_sec=30)
    logger.info("Gold Dashboard started")
    yield
    # Shutdown handled by scheduler.shutdown()


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
