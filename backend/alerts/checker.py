"""APScheduler background tasks: periodic price fetch + alert check + DB snapshot + news."""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.data.sources.international import fetch_xauusd, fetch_usdcny
from backend.data.sources.international import fetch_news as _fetch_news
from backend.data.sources.domestic import fetch_au9999
from backend.alerts.engine import check_alerts

logger = logging.getLogger(__name__)

_shared_state = {"prices": {}, "alerts": [], "updated_at": "", "news": []}
scheduler = AsyncIOScheduler()


def get_latest_prices() -> dict:
    return _shared_state["prices"]


def get_triggered_alerts() -> list[dict]:
    return _shared_state["alerts"]


def get_cached_news() -> list[dict]:
    return _shared_state["news"]


async def _refresh_news():
    """Background news refresh."""
    try:
        loop = asyncio.get_event_loop()
        news = await loop.run_in_executor(None, _fetch_news)
        _shared_state["news"] = news
        logger.info(f"News refreshed: {len(news)} items")
    except Exception as e:
        logger.warning(f"News refresh error: {e}")


async def fetch_and_check():
    """Fetch prices and run alert checks."""
    try:
        loop = asyncio.get_event_loop()

        # Run Playwright (sync) in thread pool
        xau, au9999, usdcny = await asyncio.gather(
            loop.run_in_executor(None, fetch_xauusd),
            fetch_au9999(),
            loop.run_in_executor(None, fetch_usdcny),
        )

        prices = {}
        if xau:
            prices["XAUUSD"] = xau
            _shared_state["updated_at"] = xau.get("updated_at", "")
        if au9999:
            prices["AU9999"] = au9999
        if usdcny:
            prices["USDCNY"] = usdcny

        _shared_state["prices"] = prices

        triggered = await loop.run_in_executor(None, check_alerts, prices)
        if triggered:
            _shared_state["alerts"] = triggered
            logger.info(f"Triggered {len(triggered)} alerts")
    except Exception as e:
        logger.error(f"Alert check error: {e}")


def start_scheduler(interval_sec: int = 30):
    # News: refresh every 5 min in background
    scheduler.add_job(_refresh_news, 'interval', seconds=300, id="news_refresh")
    # Price + alert check every 30 sec
    scheduler.add_job(fetch_and_check, 'interval', seconds=interval_sec, id="price_check")
    scheduler.start()
