"""News API routes — reads from briefing_cache (auto-fetches on cold cache)."""
from datetime import datetime
from fastapi import APIRouter, Query
from backend.config import BEIJING_TZ
from backend.services import briefing_cache as _cache

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news")
def get_news_endpoint(days: int = Query(default=3, ge=1, le=30)):
    news = _cache.get_news(days)
    entry = _cache._news_cache.get(days)
    refreshed_at = ""
    if entry:
        refreshed_at = datetime.fromtimestamp(entry["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M")
    return {"news": news, "refreshedAt": refreshed_at}
