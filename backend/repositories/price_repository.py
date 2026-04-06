"""Price data access layer."""
import aiosqlite
from backend.config import settings


class PriceRepository:
    """Repository for price bar data."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(settings.db_path)

    async def get_latest(self, symbol: str) -> dict | None:
        """Fetch the most recent price bar for a symbol."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT ts, open, high, low, price, change, pct "
                "FROM price_bars WHERE symbol=? ORDER BY ts DESC LIMIT 1",
                (symbol,),
            )
            row = await rows.fetchone()
            return dict(row) if row else None

    async def get_history(self, symbol: str, limit: int = 2000) -> list[dict]:
        """Fetch price bars for a symbol, newest first."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute(
                "SELECT ts, open, high, low, price, volume "
                "FROM price_bars WHERE symbol=? ORDER BY ts DESC LIMIT ?",
                (symbol, limit),
            )
            return [dict(r) for r in await rows.fetchall()]

    async def save(self, symbol: str, ts: int, open_: float, high: float,
                   low: float, price: float, volume: float = 0,
                   change: float = 0, pct: float = 0) -> None:
        """Upsert a single price bar."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO price_bars (symbol, ts, open, high, low, price, volume, change, pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, ts) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    price=excluded.price, volume=excluded.volume,
                    change=excluded.change, pct=excluded.pct
            """, (symbol, ts, open_, high, low, price, volume, change, pct))
            await db.commit()

    async def save_many(self, bars: list[dict], symbol: str) -> int:
        """Batch upsert price bars in a single transaction. Returns count saved."""
        if not bars:
            return 0
        rows = [
            (symbol, b["time"], b["open"], b["high"], b["low"],
             b["close"], b.get("volume", 0), b.get("change", 0), b.get("pct", 0))
            for b in bars
        ]
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany("""
                INSERT INTO price_bars (symbol, ts, open, high, low, price, volume, change, pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, ts) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    price=excluded.price, volume=excluded.volume,
                    change=excluded.change, pct=excluded.pct
            """, rows)
            await db.commit()
        return len(rows)

    async def get_latest_usdcny(self) -> dict | None:
        """Fetch the most recent USD/CNY rate."""
        return await self.get_latest("USDCNY")

    async def clear_symbol(self, symbol: str) -> None:
        """Delete all rows for a symbol."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM price_bars WHERE symbol = ?", (symbol,))
            await db.commit()
