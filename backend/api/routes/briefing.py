"""Briefing API routes — backed by in-memory cache only."""
from fastapi import APIRouter, Query
from backend.services.briefing_service import (
    get_briefing,
    refresh_news,
    refresh_briefing_only,
    get_layer1,
    get_layer2,
    get_layer3,
)

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


# Individual layer endpoints for progressive loading
@router.get("/briefings/layer1")
def get_layer1_endpoint(days: int = Query(default=3, ge=1, le=30)):
    """Layer 1: news analysis (cached 30 min). Fast — no Kline fetch."""
    return get_layer1(days=days)


@router.get("/briefings/layer2")
def get_layer2_endpoint(days: int = Query(default=3, ge=1, le=30)):
    """Layer 2: kline cross-validation (cached 60 min). Medium speed."""
    return get_layer2(days=days)


@router.get("/briefings/layer3")
def get_layer3_endpoint(days: int = Query(default=3, ge=1, le=30)):
    """Layer 3: price forecast (cached 15 min). Slowest — runs all three layers."""
    return get_layer3(days=days)
