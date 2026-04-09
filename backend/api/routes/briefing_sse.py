"""Briefing endpoint — reads from in-memory cache, returns JSON."""
from fastapi import APIRouter, Query
from backend.services.briefing_service import get_briefing

router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings/stream")
def get_briefing_stream(days: int = Query(default=3, ge=1, le=30)):
    """读取 in-memory 缓存，返回 JSON。"""
    return get_briefing(days=days)
