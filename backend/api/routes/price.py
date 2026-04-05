"""Price API routes."""
from fastapi import APIRouter, Depends
from backend.services.price_service import PriceService
from backend.api.dependencies import get_price_service

router = APIRouter(prefix="/api", tags=["price"])


@router.get("/prices")
async def get_prices(service: PriceService = Depends(get_price_service)):
    """Fetch current prices."""
    return await service.get_current_prices()


@router.get("/history/{symbol}")
async def get_history(symbol: str, days: int = 1,
                      service: PriceService = Depends(get_price_service)):
    """Fetch price history from database."""
    return await service.get_price_history(symbol, days)
