"""Briefing repository — persists AI briefing results to SQLite."""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from backend.data.db import get_db, row_to_dict

logger = logging.getLogger(__name__)

_THREE_HOURS = 3 * 3600  # seconds


def get_recent(days: int) -> dict[str, Any] | None:
    """Return most recent briefing for `days`, or None if none exist."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM ai_briefings WHERE days = ? ORDER BY generated_at DESC LIMIT 1",
            (days,),
        ).fetchone()
        if not row:
            return None
        d = row_to_dict(row)
        d["news"] = json.loads(d["news_json"]) if d.get("news_json") else []
        del d["news_json"]
        return d
    finally:
        conn.close()


def can_generate(days: int, hours: int = 3) -> bool:
    """Return True if no fresh briefing exists within `hours` for `days`."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM ai_briefings WHERE days = ? AND generated_at > ? LIMIT 1",
            (days, cutoff_str),
        ).fetchone()
        return row is None
    finally:
        conn.close()


def save(days: int, l12: str, l3: str, news: list[dict]) -> None:
    """Upsert a briefing for `days`. Replaces any existing entry."""
    conn = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        news_json = json.dumps(news, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO ai_briefings (days, l12_content, l3_content, news_json, generated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(days) DO UPDATE SET
                l12_content   = excluded.l12_content,
                l3_content    = excluded.l3_content,
                news_json     = excluded.news_json,
                generated_at  = excluded.generated_at
            """,
            (days, l12, l3, news_json, now),
        )
        conn.commit()
        logger.info("Saved briefing for days=%d, l12=%d chars, l3=%d chars", days, len(l12), len(l3))
    finally:
        conn.close()
