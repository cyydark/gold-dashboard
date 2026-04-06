"""Dependency injection container for API layer.

DB layer removed: repository factory functions deleted.
"""
from functools import lru_cache
from backend.services.price_service import PriceService
from backend.services.news_service import NewsService


@lru_cache
def get_price_service() -> PriceService:
    """Get PriceService instance (no DB, stateless REST-only)."""
    return PriceService()


@lru_cache
def get_news_service() -> NewsService:
    """Get NewsService instance (no DB, in-memory cache)."""
    return NewsService()
