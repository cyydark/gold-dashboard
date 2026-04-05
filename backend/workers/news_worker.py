"""News fetch worker - independent background process."""
import asyncio
import importlib
import logging
import threading
from backend.config import settings
from backend.data.sources import NEWS_SOURCES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_news():
    """Fetch news from all configured sources."""
    for name, (module_path, fn_name) in NEWS_SOURCES.items():
        try:
            mod = importlib.import_module(module_path)
            fetch_fn = getattr(mod, fn_name)
            save_fn = getattr(mod, "_sync_save_news")
            news = await asyncio.to_thread(fetch_fn)
            if news:
                threading.Thread(target=save_fn, args=(news,), daemon=True).start()
                logger.info(f"Fetched {len(news)} news from {name}")
        except Exception as e:
            logger.warning(f"News fetch error ({name}): {e}")


async def run_news_fetch():
    """Run news fetch once."""
    await fetch_news()


async def run_worker():
    """Run news fetch worker continuously."""
    while True:
        try:
            await fetch_news()
        except Exception as e:
            logger.warning(f"News fetch error: {e}")
        await asyncio.sleep(settings.news_refresh_interval)


if __name__ == "__main__":
    asyncio.run(run_worker())
