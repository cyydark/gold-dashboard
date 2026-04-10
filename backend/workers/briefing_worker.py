"""Background worker: refreshes AI layers every 3 hours.

Waits for News Worker to complete first run before starting.
AI failures retry every 60s until success, then resume 3h cycle.
"""
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

AI_INTERVAL    = 10800   # 3 hours
RETRY_INTERVAL = 60      # 60 seconds between retries on failure
BEIJING_TZ = timezone(timedelta(hours=8))

# Shared signal: News Worker sets this after each refresh completes.
# Defined HERE so both workers share the same object.
news_ready_event = threading.Event()


def _refresh_ai():
    """Fetch news, run AI analysis, update layer cache."""
    try:
        from backend.services import briefing_cache as bc
        news = bc.get_news(3)       # read cache already refreshed by News Worker
        layer1, layer2 = bc.get_layer(news, 3)
        logger.info(
            "AI refreshed: L1=%d chars, L2=%d chars at %s",
            len(layer1), len(layer2),
            datetime.now(BEIJING_TZ).isoformat(),
        )
        return True
    except Exception as e:
        logger.warning("AI worker failed: %s", e)
        return False


def _run_ai_loop():
    """AI main loop: refresh, then schedule next run or retry."""
    success = _refresh_ai()
    if success:
        threading.Timer(AI_INTERVAL, _run_ai_loop).start()
    else:
        threading.Timer(RETRY_INTERVAL, _run_ai_loop).start()


def _ai_start():
    """Wait for News, then begin 3h AI refresh loop."""
    logger.info("AI worker waiting for News Worker first refresh...")
    news_ready_event.wait()   # blocks until News Worker completes first run
    logger.info("AI worker: News ready, starting 3h loop")
    _run_ai_loop()


def start_briefing_worker():
    """Start AI worker thread. Call once from app lifespan.

    Returns immediately; worker runs in background thread.
    """
    logger.info("Starting briefing worker: AI refresh every 3h (waits for News)")
    t = threading.Thread(target=_ai_start, daemon=True)
    t.start()


async def warm_news_and_ai_async():
    """One-time startup chain: fetch news, then AI, then done.

    Called via asyncio.create_task in lifespan — does NOT block startup.
    """
    from backend.services import briefing_cache as bc
    try:
        news = await asyncio.to_thread(bc.get_news, 3)
        await asyncio.to_thread(bc.get_layer, news, 3)
        logger.info("Startup warm-up complete: news + AI cached")
    except Exception as e:
        logger.warning("Startup warm-up failed (non-fatal): %s", e)
