"""Briefing business logic service."""
from datetime import datetime, timedelta
from backend.repositories.briefing_repository import BriefingRepository
from backend.repositories.news_repository import NewsRepository
from backend.data.sources.futu import BEIJING_TZ


class BriefingService:
    """Service for briefing-related business logic."""

    def __init__(self,
                 briefing_repo: BriefingRepository = None,
                 news_repo: NewsRepository = None):
        self.briefing_repo = briefing_repo or BriefingRepository()
        self.news_repo = news_repo or NewsRepository()

    async def get_briefings(self, limit: int = 24) -> dict:
        """Get daily briefing + hourly briefings + recent news.

        Args:
            limit: Maximum number of hourly briefings to return

        Returns:
            dict with daily, hourly, news, and time_window
        """
        hourly = await self.briefing_repo.get_hourly(limit)
        daily = await self.briefing_repo.get_daily()
        news = await self.news_repo.get_last_hours(hours=1, limit=20)

        now = datetime.now(BEIJING_TZ)
        one_hour_ago = now - timedelta(hours=1)
        time_window = f"{one_hour_ago.strftime('%H:%M')}~{now.strftime('%H:%M')}"

        return {
            "daily": daily,
            "hourly": hourly,
            "news": news,
            "time_window": time_window,
        }

    async def trigger_briefing_generation(self) -> None:
        """Trigger briefing generation (delegates to checker module)."""
        from backend.alerts.checker import _generate_briefing_scheduled
        await _generate_briefing_scheduled()

    async def get_hourly_briefings(self, limit: int = 24) -> list[dict]:
        """Get hourly briefings."""
        return await self.briefing_repo.get_hourly(limit)

    async def get_daily_briefing(self) -> dict | None:
        """Get daily briefing."""
        return await self.briefing_repo.get_daily()
