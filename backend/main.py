"""FastAPI main application."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.api.routes import price, news, briefing, briefing_sse, health as health_router
from backend.api.limiter import limiter
from backend.api.models import ApiResponse
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_PATH = os.environ.get("FRONTEND_PATH", str(settings.frontend_path))


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.workers.news_worker import start_news_worker
    from backend.workers.briefing_worker import start_briefing_worker, warm_news_and_ai_async

    # Warm caches in background — don't block server startup
    asyncio.create_task(warm_news_and_ai_async())

    # Start background workers
    start_news_worker()        # 15min news loop, runs immediately
    start_briefing_worker()    # waits for News, then 3h AI loop

    yield


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
app.include_router(briefing_sse.router)
app.include_router(health_router.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    with open(f"{FRONTEND_PATH}/index.html") as f:
        return f.read()


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
