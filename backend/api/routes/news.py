"""News API routes."""
from fastapi import APIRouter, Depends
from backend.services.news_service import NewsService
from backend.api.dependencies import get_news_service

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news")
async def get_news(days: int = 1,
                   service: NewsService = Depends(get_news_service)):
    """Serve news from DB (filtered by days)."""
    db_news = await service.get_news(days)
    return {"news": db_news}


@router.post("/news/refresh")
async def refresh_news(service: NewsService = Depends(get_news_service)):
    """Manually refresh news from all sources."""
    return await service.refresh_news()
