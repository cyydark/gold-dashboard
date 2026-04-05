"""Briefing data access layer."""
import aiosqlite
from datetime import datetime
from backend.config import settings


class BriefingRepository:
    """Repository for AI briefings."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(settings.db_path)

    async def save_hourly(self, content: str, news_count: int, time_range: str) -> int:
        """Save an hourly briefing."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO ai_briefings (briefing_type, content, news_count, time_range, generated_at) "
                "VALUES ('hourly', ?, ?, ?, ?)",
                (content, news_count, time_range, datetime.utcnow().isoformat()),
            )
            await db.commit()
            return cursor.lastrowid

    async def save_daily(self, content: str, news_count: int, date_str: str) -> int:
        """Save a daily briefing (one per day, latest overwrites)."""
        time_range = f"{date_str} 日报"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM ai_briefings WHERE briefing_type='daily' AND time_range=?",
                (time_range,)
            )
            cursor = await db.execute(
                "INSERT INTO ai_briefings (briefing_type, content, news_count, time_range, generated_at) "
                "VALUES ('daily', ?, ?, ?, ?)",
                (content, news_count, time_range, datetime.utcnow().isoformat()),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_hourly(self, limit: int = 24) -> list[dict]:
        """Fetch the most recent N hourly briefings."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT id, content, news_count, time_range, generated_at "
                "FROM ai_briefings WHERE briefing_type='hourly' "
                "ORDER BY generated_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in await rows.fetchall()]

    async def get_daily(self) -> dict | None:
        """Fetch the most recent daily briefing."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT id, content, news_count, time_range, generated_at "
                "FROM ai_briefings WHERE briefing_type='daily' "
                "ORDER BY generated_at DESC LIMIT 1",
            )
            row = await rows.fetchone()
            return dict(row) if row else None
