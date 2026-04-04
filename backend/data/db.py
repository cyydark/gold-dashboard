"""SQLite database setup and operations — news + briefings + price bars."""
import aiosqlite
import os
import time
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "alerts.db")
BEIJING_TZ = timezone(timedelta(hours=8))


async def init_db():
    """Initialize SQLite database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                title_en TEXT,
                source TEXT,
                url TEXT UNIQUE,
                direction TEXT DEFAULT 'neutral',
                time_ago TEXT,
                published_at TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                hour_range TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at);

            CREATE TABLE IF NOT EXISTS ai_briefings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                briefing_type TEXT DEFAULT 'hourly',
                content TEXT NOT NULL,
                news_count INTEGER DEFAULT 0,
                time_range TEXT,
                generated_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS price_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                ts INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL DEFAULT 0,
                change REAL DEFAULT 0,
                pct REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_price_bar_unique
                ON price_bars(symbol, ts);

            CREATE INDEX IF NOT EXISTS idx_price_bar_ts
                ON price_bars(symbol, ts DESC);
        """)
        await db.commit()

        # Migration: add change/pct columns if missing
        for col_sql in [
            "ALTER TABLE price_bars ADD COLUMN change REAL DEFAULT 0",
            "ALTER TABLE price_bars ADD COLUMN pct REAL DEFAULT 0",
        ]:
            try:
                await db.execute(col_sql)
                await db.commit()
            except Exception:
                pass


async def get_news_items(days: int) -> list[dict]:
    """Fetch news items from DB within the last `days`, newest first by fetch time."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT title, title_en, source, url, direction, time_ago, published_at, fetched_at "
            "FROM news_items WHERE published_at >= ? ORDER BY fetched_at DESC",
            (cutoff,),
        )
        return [dict(r) for r in await rows.fetchall()]


async def save_hourly_briefing(content: str, news_count: int, time_range: str) -> int:
    """保存一条小时简报。"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO ai_briefings (briefing_type, content, news_count, time_range, generated_at) "
            "VALUES ('hourly', ?, ?, ?, ?)",
            (content, news_count, time_range, datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def save_daily_briefing(content: str, news_count: int, date_str: str) -> int:
    """保存一条日报（每日期覆盖，只存最新一条）。"""
    time_range = f"{date_str} 日报"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM ai_briefings WHERE briefing_type='daily' AND time_range=?", (time_range,))
        cursor = await db.execute(
            "INSERT INTO ai_briefings (briefing_type, content, news_count, time_range, generated_at) "
            "VALUES ('daily', ?, ?, ?, ?)",
            (content, news_count, time_range, datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_hourly_briefings(limit: int = 24) -> list[dict]:
    """获取最近 limit 条小时简报。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT id, content, news_count, time_range, generated_at "
            "FROM ai_briefings WHERE briefing_type='hourly' ORDER BY generated_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_daily_briefing() -> dict | None:
    """获取最新一条日报。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT id, content, news_count, time_range, generated_at "
            "FROM ai_briefings WHERE briefing_type='daily' ORDER BY generated_at DESC LIMIT 1",
        )
        row = await rows.fetchone()
        return dict(row) if row else None


async def get_news_by_date_range(start_iso: str, end_iso: str, limit: int = 200) -> list[dict]:
    """Fetch news items from DB within a date range."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT id, title, title_en, source, url, direction, time_ago, published_at, fetched_at "
            "FROM news_items "
            "WHERE published_at >= ? AND published_at < ? "
            "ORDER BY published_at ASC LIMIT ?",
            (start_iso, end_iso, limit),
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_news_last_hours(hours: int = 1, limit: int = 20) -> list[dict]:
    """Fetch news published within the last N hours (Beijing time)."""
    now = datetime.now(BEIJING_TZ)
    cutoff = (now - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT title, title_en, source, url, direction, time_ago, published_at, fetched_at "
            "FROM news_items WHERE published_at >= ? ORDER BY published_at DESC LIMIT ?",
            (cutoff, limit),
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_recent_news(hour_range: str | None = None, limit: int = 20) -> list[dict]:
    """Fetch recent news, optionally filtered by hour_range."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if hour_range:
            rows = await db.execute(
                "SELECT id, title, title_en, source, url, direction, time_ago, published_at, fetched_at "
                "FROM news_items WHERE hour_range = ? ORDER BY published_at DESC LIMIT ?",
                (hour_range, limit),
            )
        else:
            rows = await db.execute(
                "SELECT id, title, title_en, source, url, direction, time_ago, published_at, fetched_at "
                "FROM news_items ORDER BY fetched_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in await rows.fetchall()]


# ---------------------------------------------------------------------------
# Price bars
# ---------------------------------------------------------------------------

async def save_price_bar(symbol: str, ts: int, open_: float, high: float,
                         low: float, close: float, volume: float = 0,
                         change: float = 0, pct: float = 0) -> None:
    """Upsert a single price bar."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO price_bars (symbol, ts, open, high, low, close, volume, change, pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, ts) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                change=excluded.change, pct=excluded.pct
        """, (symbol, ts, open_, high, low, close, volume, change, pct))
        await db.commit()


async def get_price_bars(symbol: str, limit: int = 2000) -> list[dict]:
    """Fetch price bars for a symbol, newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT ts, open, high, low, close, volume "
            "FROM price_bars WHERE symbol=? ORDER BY ts DESC LIMIT ?",
            (symbol, limit),
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_latest_price_bar(symbol: str) -> dict | None:
    """Fetch the most recent price bar for a symbol."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT ts, open, high, low, close, change, pct FROM price_bars "
            "WHERE symbol=? ORDER BY ts DESC LIMIT 1",
            (symbol,),
        )
        row = await rows.fetchone()
        return dict(row) if row else None


async def save_usdcny(price: float, open_px: float | None = None,
                       high: float | None = None, low: float | None = None,
                       change: float = 0, pct: float = 0,
                       ts: int | None = None) -> None:
    """Store USD/CNY exchange rate at given timestamp."""
    if ts is None:
        ts = int(time.time())
    if open_px is None:
        open_px = price
    if high is None:
        high = price
    if low is None:
        low = price
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO price_bars (symbol, ts, open, high, low, close, volume, change, pct)
            VALUES ('USDCNY', ?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(symbol, ts) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, change=excluded.change, pct=excluded.pct
        """, (ts, open_px, high, low, price, change, pct))
        await db.commit()


async def get_latest_usdcny() -> dict | None:
    """Fetch the most recent USD/CNY rate."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT ts, open, high, low, close as price, change, pct "
            "FROM price_bars "
            "WHERE symbol='USDCNY' ORDER BY ts DESC LIMIT 1"
        )
        row = await rows.fetchone()
        return dict(row) if row else None
