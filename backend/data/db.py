"""Database connection and schema initialization."""
import sqlite3
from pathlib import Path
from typing import Any

from backend.config import settings


def get_db() -> sqlite3.Connection:
    """Return a raw connection to the SQLite database."""
    conn = sqlite3.connect(str(settings.db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create or migrate table schemas."""
    conn = get_db()
    try:
        # ── ai_briefings ──────────────────────────────────────────────────
        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_briefings'"
        )
        row = cur.fetchone()
        if not row or "l12_content" not in (row[0] or ""):
            conn.execute("DROP TABLE IF EXISTS ai_briefings")
            conn.execute("""
                CREATE TABLE ai_briefings (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    days            INTEGER NOT NULL UNIQUE,
                    l12_content     TEXT,
                    l3_content      TEXT,
                    news_json       TEXT,
                    generated_at    TEXT NOT NULL,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # ── news_items ───────────────────────────────────────────────────
        # Add published_ts column if missing (needed for time-range filtering)
        try:
            conn.execute("ALTER TABLE news_items ADD COLUMN published_ts INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists

        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


# Initialize on module load
init_db()
