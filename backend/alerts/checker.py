"""Briefing generation task — called by /briefings/trigger endpoint."""
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def _generate_briefing_scheduled():
    """每小时自动从最近1小时新闻生成简报。"""
    from backend.data.sources.international import fetch_news, BEIJING_TZ
    from backend.data.sources.briefing import generate_briefing_from_news
    try:
        loop = asyncio.get_event_loop()
        all_news = await loop.run_in_executor(None, fetch_news)
        if not all_news:
            logger.info("No news fetched, skipping briefing")
            return

        now = datetime.now(BEIJING_TZ)
        recent_window = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        hour_label = f"{recent_window.strftime('%H:%M')}~{now.strftime('%H:%M')}"

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
        logger.info(f"Hourly briefing completed for {hour_label} with {len(recent_news)} items")

        if now.hour == 0:
            await _generate_daily_briefing_scheduled()
    except Exception as e:
        logger.error(f"Briefing task error: {e}")


async def _generate_daily_briefing_scheduled():
    """每日午夜（北京时间00时）汇总昨日全天新闻生成'上一日整体'简报。"""
    from backend.data.sources.international import BEIJING_TZ
    from backend.data.db import get_news_by_date_range
    from backend.data.sources.briefing import generate_daily_briefing_from_news
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
