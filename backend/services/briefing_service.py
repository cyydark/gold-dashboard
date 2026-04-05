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

    async def get_briefings(self, limit: int = 7) -> dict:
        """Get weekly briefing + all recent news.

        Args:
            limit: Number of days to look back for news (default 7)

        Returns:
            dict with weekly (based on 7 days), news list, and news_count
        """
        weekly = await self.briefing_repo.get_daily()
        # Get all news from the last N days, sorted by published_at desc
        news = await self.news_repo.get_by_days(limit)

        # Add published_ts to each news item
        for item in news:
            try:
                pub = item.get("published_at", "")
                if pub:
                    naive = datetime.fromisoformat(pub)
                    aware = naive.replace(tzinfo=BEIJING_TZ)
                    item["published_ts"] = int(aware.timestamp())
                else:
                    item["published_ts"] = None
            except Exception:
                item["published_ts"] = None

        news.sort(key=lambda x: x.get("published_ts") or 0, reverse=True)

        return {
            "weekly": weekly,
            "news": news,
            "news_count": len(news),
            "days": limit,
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
