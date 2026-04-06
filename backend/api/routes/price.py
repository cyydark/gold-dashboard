"""Price API routes."""
from fastapi import APIRouter, Depends, Query
from backend.services.price_service import PriceService
from backend.api.dependencies import get_price_service

router = APIRouter(prefix="/api", tags=["price"])

# 前端 chart selector 符号映射
CHART_SYMBOLS: dict[str, dict[str, str]] = {
    "xau": {
        "comex":   "XAUUSD",
        "binance": "XAUUSD_BINANCE",
    },
    "au": {
        "au9999": "AU9999",
    },
}


@router.get("/prices")
async def get_prices(service: PriceService = Depends(get_price_service)):
    """Fetch current prices."""
    return await service.get_current_prices()


@router.post("/xau-source")
async def switch_xau_source(
    source: str,
    service: PriceService = Depends(get_price_service),
):
    """Switch XAUUSD data source and re-import.

    source: 'binance' | 'comex'
    """
    if source not in ("binance", "comex"):
        return {"error": "invalid source: use 'binance' or 'comex'"}
    return await service.switch_xauusd_source(source)


@router.get("/history/{symbol}")
async def get_history(symbol: str, days: int = Query(default=1, ge=1, le=30),
                      service: PriceService = Depends(get_price_service)):
    """Fetch price history from database.

    symbol: XAUUSD | XAUUSD_BINANCE | AU9999 | USDCNY
    """
    return await service.get_price_history(symbol, days)
