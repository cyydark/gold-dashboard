"""SQLite database schema setup and migrations."""
import aiosqlite
import os
from datetime import timezone, timedelta

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
                time_ago TEXT,
                published_at TEXT NOT NULL,
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
                price REAL NOT NULL,
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

        # Migration: drop redundant fetched_at column
        try:
            async with db.execute("PRAGMA table_info(news_items)") as cur:
                cols = [row[1] for row in await cur.fetchall()]
            if "fetched_at" in cols:
                await db.execute("""
                    CREATE TABLE news_items_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        title_en TEXT,
                        source TEXT,
                        url TEXT UNIQUE,
                        time_ago TEXT,
                        published_at TEXT NOT NULL,
                        hour_range TEXT
                    )
                """)
                await db.execute("""
                    INSERT INTO news_items_new(id, title, title_en, source, url, time_ago, published_at, hour_range)
                    SELECT id, title, title_en, source, url, time_ago, published_at, hour_range FROM news_items
                """)
                await db.execute("DROP TABLE news_items")
                await db.execute("ALTER TABLE news_items_new RENAME TO news_items")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at)")
                await db.commit()
        except Exception:
            pass

        # Migration: add direction column if missing
        try:
            async with db.execute("PRAGMA table_info(news_items)") as cur:
                cols = [row[1] for row in await cur.fetchall()]
            if "direction" not in cols:
                await db.execute("ALTER TABLE news_items ADD COLUMN direction TEXT")
                await db.commit()
        except Exception:
            pass

        # Migration: rename close → price
        try:
            async with db.execute("PRAGMA table_info(price_bars)") as cur:
                cols = [row[1] for row in await cur.fetchall()]
            if "close" in cols and "price" not in cols:
                await db.execute("ALTER TABLE price_bars RENAME COLUMN close TO price")
                await db.commit()
        except Exception:
            pass

        # Migration: add title_hash for title-based deduplication
        try:
            async with db.execute("PRAGMA table_info(news_items)") as cur:
                cols = [row[1] for row in await cur.fetchall()]
            if "title_hash" not in cols:
                await db.execute("ALTER TABLE news_items ADD COLUMN title_hash TEXT")
                await db.commit()
        except Exception:
            pass
