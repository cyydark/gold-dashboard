"""Background worker: refreshes news (30min) and AI layers (3h) in-memory."""
import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

NEWS_INTERVAL = 1800    # 30 minutes
AI_INTERVAL = 10800   # 3 hours


def _refresh_news():
    try:
        from backend.services import briefing_cache as bc
        news = bc._fetch_news(3)
        bc._news_cache[3] = {"ts": time.time(), "data": news}
        logger.info("News cache refreshed: %d items", len(news))
    except Exception as e:
        logger.warning("News worker failed: %s", e)


def _refresh_ai():
    try:
        from backend.services import briefing_cache as bc
        news = bc.get_news(3)
        layer1, layer2 = bc.get_layer(news, 3)
        logger.info("AI layers refreshed: L1=%d chars, L2=%d chars", len(layer1), len(layer2))
    except Exception as e:
        logger.warning("AI worker failed: %s", e)


def _run_news_loop():
    _refresh_news()
    threading.Timer(NEWS_INTERVAL, _run_news_loop).start()


def _run_ai_loop():
    _refresh_ai()
    threading.Timer(AI_INTERVAL, _run_ai_loop).start()


def start_news_worker():
    logger.info("Starting worker: news=30min, AI=3h")
    threading.Timer(NEWS_INTERVAL, _run_news_loop).start()
    threading.Timer(AI_INTERVAL, _run_ai_loop).start()
