"""News business logic service."""
import asyncio
import importlib
from datetime import datetime, timezone, timedelta
from backend.repositories.news_repository import NewsRepository
from backend.data.sources import NEWS_SOURCES

BEIJING_TZ = timezone(timedelta(hours=8))


class NewsService:
    """Service for news-related business logic."""

    def __init__(self, repository: NewsRepository = None):
        self.repository = repository or NewsRepository()

    async def get_news(self, days: int = 1) -> list[dict]:
        """Fetch news items from DB, enriched with timestamps.

        Args:
            days: Number of days to look back

        Returns:
            List of news items with published_ts added
        """
        db_news = await self.repository.get_by_days(days)

        for item in db_news:
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

        db_news.sort(key=lambda x: x.get("published_ts") or 0, reverse=True)
        return db_news

    async def refresh_news(self) -> dict:
        """Fetch news from all configured sources and save to DB.

        Returns:
            dict with total count and per-source counts
        """
        loop = asyncio.get_event_loop()
        results: dict[str, int] = {}

        for name, (module_path, fn_name) in NEWS_SOURCES.items():
            mod = importlib.import_module(module_path)
            fetch_fn = getattr(mod, fn_name)
            save_fn = getattr(mod, "_sync_save_news")
            news = await loop.run_in_executor(None, fetch_fn)
            if news:
                await asyncio.to_thread(save_fn, news)
            results[name] = len(news) if news else 0

        total = sum(results.values())
        detail = ", ".join(f"{name}: {count}" for name, count in results.items())
        return {"count": total, "message": f"抓取到 {total} 条新闻（{detail}）已入库"}

    async def get_news_in_range(self, start_iso: str, end_iso: str,
                                 limit: int = 100) -> list[dict]:
        """Fetch news within a timestamp range."""
        return await self.repository.get_in_range(start_iso, end_iso, limit)

    async def get_news_last_hours(self, hours: int = 1, limit: int = 20) -> list[dict]:
        """Fetch news published within the last N hours."""
        return await self.repository.get_last_hours(hours, limit)
