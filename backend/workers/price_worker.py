"""Price sync worker - independent background process."""
import asyncio
import importlib
import logging
from backend.config import settings
from backend.repositories.price_repository import PriceRepository
from backend.data.sources import SOURCES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def sync_prices():
    """Sync price data from all configured sources."""
    repository = PriceRepository()

    for symbol, (module_path, fn_name) in SOURCES.items():
        mod = importlib.import_module(module_path)
        fn = getattr(mod, fn_name)
        bars = await asyncio.to_thread(fn)
        if bars:
            for b in bars:
                await repository.save(
                    symbol=symbol,
                    ts=b["time"],
                    open_=b["open"],
                    high=b["high"],
                    low=b["low"],
                    price=b["close"],
                    change=b.get("change", 0),
                    pct=b.get("pct", 0),
                )
            logger.info(f"Synced {len(bars)} {symbol} bars from {module_path}")


async def run_price_sync():
    """Run price sync once."""
    await sync_prices()


async def run_worker():
    """Run price sync worker continuously."""
    while True:
        try:
            await sync_prices()
        except Exception as e:
            logger.warning(f"Price sync error: {e}")
        await asyncio.sleep(settings.price_sync_interval)


if __name__ == "__main__":
    asyncio.run(run_worker())
