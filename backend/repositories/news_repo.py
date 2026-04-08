"""News repository — persists scraped news items to SQLite."""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from backend.data.db import get_db

logger = logging.getLogger(__name__)

_NEWS_TTL_MINUTES = 10


def save_news(items: list[dict]) -> None:
    """Insert or replace news items by URL. Drops duplicates silently."""
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
            INSERT OR REPLACE INTO news_items
                (title, title_en, source, url, published_at, published_ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
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
