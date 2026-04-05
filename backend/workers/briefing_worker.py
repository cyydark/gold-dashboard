"""Briefing generation worker - independent background process."""
import asyncio
import logging
from datetime import datetime, timedelta
from backend.config import settings
from backend.alerts.checker import _generate_briefing_scheduled

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def generate_briefing():
    """Generate briefing once."""
    await _generate_briefing_scheduled()


async def run_worker():
    """Run briefing generation worker continuously.

    Triggers at minute 1 of each hour.
    """
    while True:
        now = datetime.now()
        next_hour = now.replace(minute=1, second=0, microsecond=0)
        if now.minute >= 1:
            next_hour = next_hour + timedelta(hours=1)
        wait = (next_hour - now).total_seconds()
        await asyncio.sleep(max(wait, 0))

        try:
            await generate_briefing()
        except Exception as e:
            logger.warning(f"Briefing generation error: {e}")

        # Sleep until next hour trigger
        await asyncio.sleep(settings.briefing_interval)


if __name__ == "__main__":
    asyncio.run(run_worker())
