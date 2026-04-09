"""Briefing service — news + AI briefing, in-memory only."""
import logging
from datetime import datetime, timezone, timedelta

from backend.services import briefing_cache as _cache

logger = logging.getLogger(__name__)
BEIJING_TZ = timezone(timedelta(hours=8))


def get_briefing(days: int = 3) -> dict:
    """Return cached briefing + news. News from in-memory, AI from in-memory."""
    news = _cache.get_news(days)
    layer1, layer2 = _cache.get_layer(news, days)
    return {
        "weekly": {
            "layer1": layer1,
            "layer2": layer2,
            "time_range": _cache.time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }
