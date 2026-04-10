"""Background worker: refreshes news in-memory cache every 15 minutes."""
import logging
import threading
from datetime import datetime, timezone, timedelta

# news_ready_event is defined in briefing_worker.py — import it so both workers
# share the same threading.Event object for the News → AI startup signal.
from backend.workers.briefing_worker import news_ready_event

logger = logging.getLogger(__name__)

NEWS_INTERVAL = 900    # 15 minutes
BEIJING_TZ = timezone(timedelta(hours=8))


def _refresh_news():
    """Fetch news and update in-memory cache."""
    try:
        from backend.services import briefing_cache as bc
        news = bc.get_news(3)   # auto-fetches if cache is cold; TTL handled inside
        logger.info(
            "News refreshed: %d items at %s",
            len(news),
            datetime.now(BEIJING_TZ).isoformat(),
        )
        # Signal that news refresh is complete (used by AI Worker as startup gate)
        news_ready_event.set()
        return news
    except Exception as e:
        logger.warning("News worker failed: %s", e)
        return None


def _run_news_loop():
    news = _refresh_news()
    threading.Timer(NEWS_INTERVAL, _run_news_loop).start()


def start_news_worker():
    """Start the news worker. Call once from app lifespan."""
    logger.info("Starting news worker: refresh every %ds", NEWS_INTERVAL)
    # First run immediately on startup, then loop
    threading.Timer(0, _run_news_loop).start()
