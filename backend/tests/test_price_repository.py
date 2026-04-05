"""Tests for PriceRepository."""
import pytest
import asyncio
import aiosqlite
from backend.repositories.price_repository import PriceRepository


@pytest.fixture
def repo(tmp_path):
    db_path = str(tmp_path / "test.db")
    return PriceRepository(db_path=db_path)


@pytest.fixture
def init_db(repo):
    async def _init():
        async with aiosqlite.connect(repo.db_path) as db:
            await db.executescript("""
                CREATE TABLE price_bars (
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
                CREATE UNIQUE INDEX idx_price_bar_unique ON price_bars(symbol, ts);
            """)
            await db.commit()
    asyncio.run(_init())


@pytest.mark.asyncio
async def test_save_and_get_latest(repo, init_db):
    await repo.save(
        symbol="XAUUSD",
        ts=1700000000,
        open_=2000.0,
        high=2010.0,
        low=1990.0,
        price=2005.0,
        change=5.0,
        pct=0.25
    )
    result = await repo.get_latest("XAUUSD")
    assert result is not None
    assert result["price"] == 2005.0
    assert result["change"] == 5.0
    assert result["pct"] == 0.25


@pytest.mark.asyncio
async def test_get_latest_usdcny(repo, init_db):
    await repo.save(
        symbol="USDCNY",
        ts=1700000000,
        open_=7.2,
        high=7.25,
        low=7.18,
        price=7.23,
    )
    result = await repo.get_latest_usdcny()
    assert result is not None
    assert result["price"] == 7.23


@pytest.mark.asyncio
async def test_get_history(repo, init_db):
    for i in range(3):
        await repo.save(
            symbol="XAUUSD",
            ts=1700000000 + i * 3600,
            open_=2000.0 + i,
            high=2010.0 + i,
            low=1990.0 + i,
            price=2005.0 + i,
        )
    result = await repo.get_history("XAUUSD", limit=10)
    assert len(result) == 3
