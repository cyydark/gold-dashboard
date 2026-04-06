"""News API routes."""
from fastapi import APIRouter, Depends, Request, Query
from backend.services.news_service import NewsService
from backend.api.dependencies import get_news_service
from backend.api.limiter import limiter  # noqa: F401 (re-exported for slowapi)

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news")
async def get_news(days: int = Query(default=1, ge=1, le=30),
                   service: NewsService = Depends(get_news_service)):
    """Serve news from DB (filtered by days)."""
    db_news = await service.get_news(days)
    return {"news": db_news}


@router.post("/news/refresh")
@limiter.limit("5/minute")
async def refresh_news(request: Request,
                       service: NewsService = Depends(get_news_service)):
    """Manually refresh news from all sources (rate limited: 5/min)."""
    return await service.refresh_news()
