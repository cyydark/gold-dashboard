"""Dependency injection container for API layer."""
from functools import lru_cache
from backend.repositories.price_repository import PriceRepository
from backend.repositories.news_repository import NewsRepository
from backend.repositories.briefing_repository import BriefingRepository
from backend.services.price_service import PriceService
from backend.services.news_service import NewsService
from backend.services.briefing_service import BriefingService


@lru_cache
def get_price_repository() -> PriceRepository:
    """Get PriceRepository instance (singleton per request)."""
    return PriceRepository()


@lru_cache
def get_news_repository() -> NewsRepository:
    """Get NewsRepository instance (singleton per request)."""
    return NewsRepository()


@lru_cache
def get_briefing_repository() -> BriefingRepository:
    """Get BriefingRepository instance (singleton per request)."""
    return BriefingRepository()


@lru_cache
def get_price_service() -> PriceService:
    """Get PriceService instance."""
    return PriceService(repository=get_price_repository())


@lru_cache
def get_news_service() -> NewsService:
    """Get NewsService instance."""
    return NewsService(repository=get_news_repository())


@lru_cache
def get_briefing_service() -> BriefingService:
    """Get BriefingService instance."""
    return BriefingService(
        briefing_repo=get_briefing_repository(),
        news_repo=get_news_repository(),
    )
