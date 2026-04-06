"""News API routes — backed by in-memory cache only."""
from fastapi import APIRouter, Query
from backend.services.news_service import get_news

router = APIRouter(prefix="/api", tags=["news"])

# Re-export limiter for rate limiting support in other modules
try:
    from backend.api.limiter import limiter
except ImportError:
    limiter = None


@router.get("/news")
def get_news_endpoint(days: int = Query(default=1, ge=1, le=30)):
    return {"news": get_news(days=days)}


@router.post("/news/refresh")
def refresh_news():
    """Force refresh: clear cache and re-fetch."""
    from backend.services.news_service import _cache
    _cache["data"] = []
    _cache["ts"] = 0
    return {"news": get_news(days=1)}
