"""Briefing API routes — backed by in-memory cache only."""
from fastapi import APIRouter, Query
from backend.services.briefing_service import get_briefing

router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings")
def get_briefings(days: int = Query(default=3, ge=1, le=30)):
    return get_briefing(days=days)


@router.post("/briefings/trigger")
def trigger_briefing():
    """Force refresh: clear cache and regenerate."""
    from backend.services.briefing_service import _cache
    _cache["data"] = None
    return get_briefing(days=3)
