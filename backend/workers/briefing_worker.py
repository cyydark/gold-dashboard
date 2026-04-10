"""Background worker: refreshes AI layers (3h) in-memory.

News is NOT refreshed here — /api/news (on-demand) or ns_get_news() TTL handles that.
"""
import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AI_INTERVAL = 10800   # 3 hours


def _refresh_ai():
    try:
        from backend.services import briefing_cache as bc
        news = bc.get_news(3)  # auto-fetches if cache is cold
        layer1, layer2 = bc.get_layer(news, 3)
        logger.info("AI layers refreshed: L1=%d chars, L2=%d chars", len(layer1), len(layer2))
    except Exception as e:
        logger.warning("AI worker failed: %s", e)


def _run_ai_loop():
    _refresh_ai()
    threading.Timer(AI_INTERVAL, _run_ai_loop).start()


def start_briefing_worker():
    """Start the background worker. Call once from app lifespan."""
    logger.info("Starting briefing worker: AI refresh every 3h")
    threading.Timer(AI_INTERVAL, _run_ai_loop).start()
