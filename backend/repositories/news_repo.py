"""News repository — persists scraped news items to SQLite."""
import logging
from datetime import datetime, timezone, timedelta

from backend.data.db import get_db

logger = logging.getLogger(__name__)

_NEWS_TTL_MINUTES = 10


def save_news(items: list[dict]) -> None:
    """Insert new news items, ignoring duplicates; preserve existing published_ts on conflict."""
    if not items:
        return
    conn = get_db()
    try:
        rows = [
            (
                it.get("title", ""),
                it.get("title_en", ""),
                it.get("source", ""),
                it.get("url", ""),
                it.get("published_at", ""),
                it.get("published_ts", 0),
            )
            for it in items
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO news_items
                (title, title_en, source, url, published_at, published_ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        # Restore published_ts for rows that already existed (was 0 after INSERT OR IGNORE)
        for it in items:
            if it.get("published_ts", 0) > 0:
                conn.execute(
                    "UPDATE news_items SET published_ts = ? WHERE url = ? AND published_ts = 0",
                    (it["published_ts"], it.get("url", "")),
                )
        conn.commit()
        logger.debug("Saved %d news items", len(items))
    finally:
        conn.close()


def get_recent_news(days: int = 3) -> list[dict]:
    """Return news items from the last `days` days, newest first."""
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT title, title_en, source, url, published_at, published_ts
            FROM news_items
            WHERE published_ts >= ?
            ORDER BY published_ts DESC
            """,
            (cutoff_ts,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
