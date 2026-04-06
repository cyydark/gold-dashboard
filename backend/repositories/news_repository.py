"""News data access layer."""
import hashlib
import aiosqlite
from datetime import datetime, timedelta, timezone
from backend.config import settings

_direction_cache: dict[str, str] = {}


def _title_hash(title: str) -> str:
    """Normalized SHA-256 hash of a title for cross-URL deduplication."""
    normalized = title.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


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
                "SELECT id, title, title_en, source, url, time_ago, published_at, direction, title_hash "
                "FROM news_items WHERE published_at >= ? ORDER BY published_at DESC",
                (cutoff,),
            )
            return [dict(r) for r in await rows.fetchall()]

    async def save(self, title: str, title_en: str, source: str, url: str,
                   time_ago: str, published_at: str, title_hash: str = "",
                   hour_range: str = "") -> None:
        """Save a news item, dedup by URL and title_hash.

        title_hash: SHA-256 of normalized title for cross-URL dedup.
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Prefer URL dedup; fall back to title_hash dedup if URL differs
            await db.execute("""
                INSERT INTO news_items (title, title_en, source, url, time_ago, published_at, title_hash, hour_range)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title, title_en=excluded.title_en,
                    time_ago=excluded.time_ago, published_at=excluded.published_at,
                    title_hash=excluded.title_hash, hour_range=excluded.hour_range
            """, (title, title_en, source, url, time_ago, published_at, title_hash, hour_range))
            # Also try title_hash dedup for same-content, different-URL items
            if title_hash:
                await db.execute("""
                    DELETE FROM news_items
                    WHERE title_hash = ?
                      AND url != ?
                      AND id NOT IN (
                          SELECT id FROM news_items
                          WHERE title_hash = ?
                          ORDER BY published_at DESC
                          LIMIT 1
                      )
                """, (title_hash, url, title_hash))
            await db.commit()

    async def update_directions(self, updates: list[tuple[str, str]]) -> None:
        """Batch update direction field for news items. Args: list of (direction, url)."""
        if not updates:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                "UPDATE news_items SET direction=? WHERE url=?",
                updates,
            )
            await db.commit()

    async def save_many(self, items: list[dict], hour_range: str = "") -> None:
        """Batch save news items within a single transaction.

        Handles URL dedup (ON CONFLICT) and title-hash dedup.
        """
        if not items:
            return
        now_str = datetime.utcnow().isoformat()
        BEIJING_TZ = timezone(timedelta(hours=8))
        rows = []
        for item in items:
            pub = item.get("published", "")
            pub_ts = None
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(pub.replace(" ", "T"))
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=BEIJING_TZ)
                    pub_dt = pub_dt.astimezone(BEIJING_TZ)
                    pub_ts = pub_dt.isoformat()
                except Exception:
                    pass
            title_en = item.get("title_en", "")
            title = item.get("title", "")
            url = item.get("url", "")
            th = _title_hash(title_en or title)
            direction = _direction_cache.get(url, "中性")
            rows.append((
                title, title_en,
                item.get("source", ""), url,
                item.get("time_ago", ""),
                pub_ts or pub or now_str, hour_range,
                direction, th,
            ))
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany("""
                INSERT INTO news_items (title, title_en, source, url, time_ago, published_at, hour_range, direction, title_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title, title_en=excluded.title_en,
                    time_ago=excluded.time_ago, published_at=excluded.published_at,
                    hour_range=excluded.hour_range, direction=excluded.direction,
                    title_hash=excluded.title_hash
            """, rows)
            # Bulk title-hash dedup
            for row in rows:
                url, th = row[3], row[8]
                if url and th:
                    await db.execute("""
                        DELETE FROM news_items
                        WHERE title_hash = ? AND url != ?
                          AND id NOT IN (
                              SELECT id FROM news_items
                              WHERE title_hash = ?
                              ORDER BY published_at DESC LIMIT 1
                          )
                    """, (th, url, th))
            await db.commit()

    async def get_by_date_range(self, start_iso: str, end_iso: str,
                                limit: int = 200) -> list[dict]:
        """Fetch news items within a date range (Beijing time)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT id, title, title_en, source, url, time_ago, published_at, direction, title_hash "
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
                "SELECT id, title, title_en, source, url, time_ago, published_at, direction, title_hash "
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
                "SELECT id, title, title_en, source, url, time_ago, published_at, direction, title_hash "
                "FROM news_items WHERE published_at >= ? ORDER BY published_at DESC LIMIT ?",
                (cutoff, limit),
            )
            return [dict(r) for r in await rows.fetchall()]
