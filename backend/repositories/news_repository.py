"""News data access layer."""
import aiosqlite
from datetime import datetime, timedelta, timezone
from backend.config import settings


class NewsRepository:
    """Repository for news items."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(settings.db_path)

    async def get_by_days(self, days: int) -> list[dict]:
        """Fetch news items from DB within the last N days, newest first."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT title, title_en, source, url, time_ago, published_at "
                "FROM news_items WHERE published_at >= ? ORDER BY published_at DESC",
                (cutoff,),
            )
            return [dict(r) for r in await rows.fetchall()]

    async def save(self, title: str, title_en: str, source: str, url: str,
                   time_ago: str, published_at: str, hour_range: str = "") -> None:
        """Save a news item to DB."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO news_items (title, title_en, source, url, time_ago, published_at, hour_range)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title, title_en=excluded.title_en,
                    time_ago=excluded.time_ago, published_at=excluded.published_at,
                    hour_range=excluded.hour_range
            """, (title, title_en, source, url, time_ago, published_at, hour_range))
            await db.commit()

    async def get_by_date_range(self, start_iso: str, end_iso: str,
                                limit: int = 200) -> list[dict]:
        """Fetch news items within a date range (Beijing time)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT id, title, title_en, source, url, time_ago, published_at "
                "FROM news_items "
                "WHERE date(published_at, '-8 hours') >= date(?) "
                "  AND date(published_at, '-8 hours') <  date(?) "
                "ORDER BY published_at ASC LIMIT ?",
                (start_iso, end_iso, limit),
            )
            return [dict(r) for r in await rows.fetchall()]

    async def get_in_range(self, start_iso: str, end_iso: str,
                           limit: int = 100) -> list[dict]:
        """Fetch news items within a UTC timestamp range, newest first."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT title, title_en, source, url, time_ago, published_at "
                "FROM news_items WHERE published_at >= ? AND published_at < ? "
                "ORDER BY published_at DESC LIMIT ?",
                (start_iso, end_iso, limit),
            )
            return [dict(r) for r in await rows.fetchall()]

    async def get_last_hours(self, hours: int, limit: int = 20) -> list[dict]:
        """Fetch news published within the last N hours (Beijing time)."""
        BEIJING_TZ = timezone(timedelta(hours=8))
        now = datetime.now(BEIJING_TZ)
        cutoff = (now - timedelta(hours=hours)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT title, title_en, source, url, time_ago, published_at "
                "FROM news_items WHERE published_at >= ? ORDER BY published_at DESC LIMIT ?",
                (cutoff, limit),
            )
            return [dict(r) for r in await rows.fetchall()]
