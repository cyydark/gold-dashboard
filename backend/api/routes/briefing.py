"""Briefing API routes — backed by in-memory cache only."""
from fastapi import APIRouter, Query
from backend.services.briefing_service import get_briefing, refresh_news, refresh_briefing_only

router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings")
def get_briefings(days: int = Query(default=3, ge=1, le=30)):
    return get_briefing(days=days)


@router.post("/briefings/news/refresh")
def refresh_news_endpoint(days: int = Query(default=3, ge=1, le=30)):
    """Force refresh news and regenerate briefing."""
    return refresh_news(days=days)


@router.post("/briefings/briefing/refresh")
def refresh_briefing_endpoint(days: int = Query(default=3, ge=1, le=30)):
    """Force regenerate AI briefing only, keep existing news cache."""
    return refresh_briefing_only(days=days)
