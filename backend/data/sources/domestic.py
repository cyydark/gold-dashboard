"""Domestic gold (AU9999) — delegates to eastmoney_au data source."""
import asyncio
from backend.data.sources.eastmoney_au import fetch_au9999 as _fetch


async def fetch_au9999():
    """Async wrapper around the sync eastmoney_au fetcher."""
    return await asyncio.to_thread(_fetch)


__all__ = ["fetch_au9999"]
