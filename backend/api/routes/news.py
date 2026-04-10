"""News API routes — reads from briefing_cache (auto-fetches on cold cache)."""
from fastapi import APIRouter, Query
from backend.services import briefing_cache as _cache

router = APIRouter(prefix="/api", tags=["news"])

try:
    from backend.api.limiter import limiter
except ImportError:
    limiter = None


@router.get("/news")
def get_news_endpoint(days: int = Query(default=3, ge=1, le=30)):
    news = _cache.get_news(days)
    return {"news": news}
