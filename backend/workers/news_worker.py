"""Background worker: periodically saves news to SQLite every 15 minutes."""
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

INTERVAL_MINUTES = 15  # 15 minutes


def _save_once():
    """Fetch from sources and save to DB (runs in thread)."""
    try:
        from backend.services.news_service import _fetch_news_from_sources, _filter_by_days
        items = _fetch_news_from_sources()
        items = _filter_by_days(items, days=3)
        from backend.repositories.news_repo import save_news
        save_news(items)
        logger.info("News worker saved %d items at %s", len(items), datetime.now(timezone.utc).isoformat())
    except Exception as e:
        logger.warning("News worker failed: %s", e)


def _run_periodic():
    _save_once()
    t = threading.Timer(INTERVAL_MINUTES * 60, _run_periodic)
    t.daemon = True
    t.start()


def start_news_worker():
    """Start the periodic news saver. Call once from app lifespan."""
    logger.info("Starting news worker (interval=%d min)", INTERVAL_MINUTES)
    t = threading.Timer(INTERVAL_MINUTES * 60, _run_periodic)
    t.daemon = True
    t.start()
