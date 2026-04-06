"""Briefing generation task — called by /briefings/trigger endpoint."""
import asyncio
import logging
from datetime import datetime, timedelta

from backend.data import constants as c

logger = logging.getLogger(__name__)
async def _generate_briefing_scheduled():
    """每小时01分触发AI简报生成（分析上一小时新闻，来自DB全量来源）。"""
    from backend.repositories.news_repository import NewsRepository
    from backend.data.sources.futu import fetch_and_save_news, BEIJING_TZ
    from backend.data.sources.briefing import generate_briefing_from_news
    try:
        news_repo = NewsRepository()
        now = datetime.now(BEIJING_TZ)
        this_hour_start = now.replace(minute=0, second=0, microsecond=0)
        last_hour_start = this_hour_start - timedelta(hours=1)
        hour_label = f"{last_hour_start.strftime('%H:%M')}~{(this_hour_start - timedelta(minutes=1)).strftime('%H:%M')}"

        # 先触发一次新闻刷新并等待完成，确保上一小时数据已入库
        await asyncio.to_thread(fetch_and_save_news)

        # 从 DB 查全量来源的上一小时新闻
        recent_news = await news_repo.get_in_range(
            start_iso=last_hour_start.isoformat(),
            end_iso=this_hour_start.isoformat(),
            limit=c.NEWS_LIMIT_RECENT,
        )

        if not recent_news:
            logger.info("No news in recent 1-hour window, skipping briefing")
            return

        await generate_briefing_from_news(recent_news, hour_label)
        logger.info(f"Hourly briefing completed for {hour_label} with {len(recent_news)} items")

        if now.hour == c.DAILY_BRIEFING_HOUR:
            await _generate_daily_briefing_scheduled()
    except Exception as e:
        logger.error(f"Briefing task error: {e}")


async def _generate_daily_briefing_scheduled():
    """每日08时（北京时间08:05前后）汇总近7天新闻生成'近7日综合'简报。"""
    from backend.repositories.news_repository import NewsRepository
    from backend.data.sources.futu import BEIJING_TZ, fetch_and_save_news
    from backend.data.sources.briefing import generate_daily_briefing_from_news
    try:
        news_repo = NewsRepository()
        now = datetime.now(BEIJING_TZ)

        # 主动触发一次新闻获取+写入，等待完成后再查 DB
        await asyncio.to_thread(fetch_and_save_news)

        # 近7天新闻
        recent_news = await news_repo.get_by_days(7)
        if not recent_news:
            logger.warning("No news found in last 7 days, skipping daily briefing")
            return

        # 标注近7日
        date_str = "近7日"
        await generate_daily_briefing_from_news(recent_news, date_str)
        logger.info(f"Daily briefing completed ({date_str}) with {len(recent_news)} items")
    except Exception as e:
        logger.error(f"Daily briefing task error: {e}")
