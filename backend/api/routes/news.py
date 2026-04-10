"""News API routes — fetches news on demand and writes to briefing_cache."""
from fastapi import APIRouter, Query
from backend.services.news_service import get_news as ns_get_news
from backend.services import briefing_cache as _cache

router = APIRouter(prefix="/api", tags=["news"])

try:
    from backend.api.limiter import limiter
except ImportError:
    limiter = None


@router.get("/news")
def get_news_endpoint(days: int = Query(default=3, ge=1, le=30)):
    news = ns_get_news(days=days)
    _cache.set_news(days, news)
    return {"news": news}
