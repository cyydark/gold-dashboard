"""News API routes — backed by news_service (scrapers)."""
from fastapi import APIRouter, Query
from backend.services.news_service import get_news

router = APIRouter(prefix="/api", tags=["news"])

try:
    from backend.api.limiter import limiter
except ImportError:
    limiter = None


@router.get("/news")
def get_news_endpoint(days: int = Query(default=3, ge=1, le=30)):
    return {"news": get_news(days=days)}
