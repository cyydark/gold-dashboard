"""Briefing service — AI briefing only, news served separately via /api/news."""
import logging
from datetime import datetime, timedelta

from backend.config import BEIJING_TZ

from backend.services import briefing_cache as _cache

logger = logging.getLogger(__name__)


def get_briefing(days: int = 3) -> dict:
    """Return cached AI briefing only. News is fetched separately via /api/news."""
    news = _cache.get_news(days)  # triggers fetch if cache is cold
    layer1, layer2 = _cache.get_layer(news, days)
    return {
        "weekly": {
            "layer1": layer1,
            "layer2": layer2,
            "timeRange": _cache.time_range(days),
            "newsCount": len(news),
            "generatedAt": _cache.generated_at(days),
        },
    }
