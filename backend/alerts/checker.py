"""APScheduler background tasks: periodic price fetch + alert check + DB snapshot + news."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.data.sources.international import fetch_xauusd, fetch_usdcny
from backend.data.sources.international import fetch_news as _fetch_news
from backend.data.sources.domestic import fetch_au9999
from backend.alerts.engine import check_alerts
from backend.data.sources.briefing import generate_briefing_from_news, generate_daily_briefing_from_news

logger = logging.getLogger(__name__)

_shared_state = {"prices": {}, "alerts": [], "updated_at": "", "news": []}
scheduler = AsyncIOScheduler()


def get_latest_prices() -> dict:
    return _shared_state["prices"]


def get_triggered_alerts() -> list[dict]:
    return _shared_state["alerts"]


def get_cached_news() -> list[dict]:
    return _shared_state["news"]


async def _generate_briefing_scheduled():
    """每小时自动从最近1小时新闻生成简报。"""
    from backend.data.sources.international import fetch_news, BEIJING_TZ
    try:
        # 先刷新新闻确保缓存最新
        loop = asyncio.get_event_loop()
        all_news = await loop.run_in_executor(None, fetch_news)
        _shared_state["news"] = all_news
        if not all_news:
            logger.info("No news fetched, skipping briefing")
            return

        now = datetime.now(BEIJING_TZ)
        recent_window = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        hour_label = f"{recent_window.strftime('%H:%M')}~{now.strftime('%H:%M')}"

        # 过滤最近1小时内的新闻
        recent_news = []
        for n in all_news:
            pub = n.get("published", "")
            if not pub:
                continue
            try:
                pub_dt = None
                try:
                    from email.utils import parsedate_to_datetime
                    pub_dt = parsedate_to_datetime(pub).astimezone(BEIJING_TZ)
                except Exception:
                    try:
                        pub_dt = datetime.strptime(pub[:16], "%Y-%m-%d %H:%M")
                        pub_dt = pub_dt.replace(tzinfo=BEIJING_TZ)
                    except Exception:
                        pass
                if pub_dt is None:
                    continue
                if pub_dt >= recent_window:
                    recent_news.append(n)
            except Exception:
                continue

        if not recent_news:
            logger.info("No news in recent 1-hour window, skipping briefing")
            return

        await generate_briefing_from_news(recent_news, hour_label)
        logger.info(f"Briefing completed for {hour_label} with {len(recent_news)} items")
    except Exception as e:
        logger.error(f"Briefing task error: {e}")


async def _generate_daily_briefing_scheduled():
    """每日08:05（北京时间）汇总昨日全天新闻生成'上一日整体'简报。"""
    from backend.data.sources.international import BEIJING_TZ
    from backend.data.db import get_news_by_date_range
    try:
        now = datetime.now(BEIJING_TZ)
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_str = yesterday_start.strftime("%Y-%m-%d")

        yesterday_news = await get_news_by_date_range(
            start_iso=yesterday_start.isoformat(),
            end_iso=yesterday_end.isoformat(),
            limit=200,
        )
        if not yesterday_news:
            logger.info("No news found for yesterday, skipping daily briefing")
            return

        await generate_daily_briefing_from_news(yesterday_news, date_str)
        logger.info(f"Daily briefing completed for {date_str} with {len(yesterday_news)} items")
    except Exception as e:
        logger.error(f"Daily briefing task error: {e}")


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
    # Briefing from news every hour
    scheduler.add_job(
        _generate_briefing_scheduled,
        'interval', hours=1,
        id="briefing_hourly",
        next_run_time=datetime.now(timezone(timedelta(hours=8))),
    )
    # 每日08:05 北京时间生成昨日日报
    scheduler.add_job(
        _generate_daily_briefing_scheduled,
        'cron', hour=8, minute=5,
        id="briefing_daily",
        timezone=timezone(timedelta(hours=8)),
    )
    scheduler.start()
