"""APScheduler background tasks: periodic price fetch + news refresh."""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.data.sources.international import fetch_xauusd, fetch_usdcny
from backend.data.sources.international import fetch_news as _fetch_news
from backend.data.sources.domestic import fetch_au9999

logger = logging.getLogger(__name__)

_shared_state = {"prices": {}, "updated_at": "", "news": []}
scheduler = AsyncIOScheduler()


def get_latest_prices() -> dict:
    return _shared_state["prices"]


def get_cached_news() -> list[dict]:
    return _shared_state["news"]


async def _refresh_news():
    """Background news refresh via RSS."""
    try:
        loop = asyncio.get_event_loop()
        news = await loop.run_in_executor(None, _fetch_news)
        _shared_state["news"] = news
        logger.info(f"News refreshed: {len(news)} items")
    except Exception as e:
        logger.warning(f"News refresh error: {e}")


async def fetch_prices():
    """Fetch current prices (runs every 30s)."""
    try:
        loop = asyncio.get_event_loop()
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
    except Exception as e:
        logger.warning(f"Price fetch error: {e}")


def start_scheduler(interval_sec: int = 30):
    # News: refresh every 5 min in background
    scheduler.add_job(_refresh_news, 'interval', seconds=300, id="news_refresh")
    # Price fetch every 30 sec
    scheduler.add_job(fetch_prices, 'interval', seconds=interval_sec, id="price_fetch")
    scheduler.start()
