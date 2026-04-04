"""SQLite database setup and operations — news + alert rules only."""
import aiosqlite
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "alerts.db")


async def init_db():
    """Initialize SQLite database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                high_price REAL,
                low_price REAL,
                condition TEXT DEFAULT 'cross',
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                price REAL,
                direction TEXT,
                triggered_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                title_en TEXT,
                source TEXT,
                url TEXT UNIQUE,
                direction TEXT DEFAULT 'neutral',
                time_ago TEXT,
                published_at TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at);

            CREATE TABLE IF NOT EXISTS ai_briefings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                news_count INTEGER DEFAULT 0,
                news_titles TEXT,
                time_range TEXT,
                generated_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()


async def get_all_rules() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT * FROM alert_rules WHERE active = 1 ORDER BY created_at DESC"
        )
        return [dict(r) for r in await rows.fetchall()]


async def add_rule(symbol: str, high_price: float | None, low_price: float | None,
                   condition: str = "cross") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO alert_rules (symbol, high_price, low_price, condition) VALUES (?, ?, ?, ?)",
            (symbol, high_price, low_price, condition),
        )
        await db.commit()
        return cursor.lastrowid


async def delete_rule(rule_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE alert_rules SET active = 0 WHERE id = ?", (rule_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def log_alert(symbol: str, price: float, direction: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO alert_history (symbol, price, direction) VALUES (?, ?, ?)",
            (symbol, price, direction),
        )
        await db.commit()


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


async def save_briefing(content: str, news_count: int, news_titles: list[str], time_range: str) -> int:
    """保存一条 AI 简报到数据库，返回新记录 ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO ai_briefings (content, news_count, news_titles, time_range, generated_at) VALUES (?, ?, ?, ?, ?)",
            (content, news_count, json.dumps(news_titles, ensure_ascii=False), time_range, datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_recent_briefings(limit: int = 24) -> list[dict]:
    """获取最近 limit 条简报，按时间倒序（最新在前）."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT id, content, news_count, news_titles, time_range, generated_at, created_at "
            "FROM ai_briefings ORDER BY generated_at DESC LIMIT ?",
            (limit,),
        )
        results = []
        for r in await rows.fetchall():
            d = dict(r)
            if d.get("news_titles"):
                try:
                    d["news_titles"] = json.loads(d["news_titles"])
                except Exception:
                    d["news_titles"] = []
            results.append(d)
        return results

