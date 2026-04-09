"""Briefing API routes — in-memory cache only."""
from fastapi import APIRouter, Query
from backend.services.briefing_service import get_briefing

router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings")
def get_briefings(days: int = Query(default=3, ge=1, le=30)):
    return get_briefing(days=days)
