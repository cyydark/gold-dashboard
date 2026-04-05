"""Price business logic service."""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from backend.repositories.price_repository import PriceRepository
from backend.data.sources.binance_kline import fetch_xauusd_realtime


class PriceService:
    """Service for price-related business logic."""

    def __init__(self, repository: PriceRepository = None):
        self.repository = repository or PriceRepository()

    async def get_current_prices(self) -> dict:
        """Fetch current prices for all symbols.

        Returns dict with XAUUSD, AU9999, USDCNY if available.
        """
        BEIJING_TZ = timezone(timedelta(hours=8))
        now_ts = int(time.time())
        result = {}

        # XAUUSD: 实时 ticker
        xau_rt = await asyncio.to_thread(fetch_xauusd_realtime)
        if xau_rt:
            result["XAUUSD"] = {
                "symbol": "XAUUSD",
                "name": "国际黄金 XAU/USD",
                "price": xau_rt["price"],
                "change": xau_rt["change"],
                "pct": xau_rt["pct"],
                "open": xau_rt["open"],
                "high": xau_rt["high"],
                "low": xau_rt["low"],
                "unit": "USD/oz",
                "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
            }

        # AU9999 / USDCNY: 从 DB 读
        au_bar = await self.repository.get_latest("AU9999")
        fx_bar = await self.repository.get_latest_usdcny()

        if au_bar:
            result["AU9999"] = {
                "symbol": "AU9999",
                "name": "国内黄金 AU9999",
                "price": round(au_bar["price"], 2),
                "change": round(au_bar.get("change", 0), 2),
                "pct": round(au_bar.get("pct", 0), 2),
                "open": round(au_bar["open"], 2),
                "high": round(au_bar["high"], 2),
                "low": round(au_bar["low"], 2),
                "unit": "CNY/g",
                "updated_at": datetime.fromtimestamp(au_bar["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
            }

        if fx_bar:
            result["USDCNY"] = {
                "symbol": "USDCNY",
                "name": "人民币兑美元 CNY/USD",
                "price": round(fx_bar["price"], 4),
                "change": round(fx_bar.get("change", 0), 4),
                "pct": round(fx_bar.get("pct", 0), 4),
                "open": round(fx_bar.get("open", fx_bar["price"]), 4),
                "high": round(fx_bar.get("high", fx_bar["price"]), 4),
                "low": round(fx_bar.get("low", fx_bar["price"]), 4),
                "unit": "CNY/USD",
                "updated_at": datetime.fromtimestamp(fx_bar["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
            }

        return result

    async def get_price_history(self, symbol: str, days: int = 1) -> dict:
        """Fetch price history from database.

        Args:
            symbol: Symbol name (XAUUSD, AU9999)
            days: Number of days (unused, kept for API compatibility)

        Returns:
            dict with 'bars', 'xMin', 'xMax'
        """
        symbol_map = {"XAUUSD": "XAUUSD", "AU9999": "AU9999"}
        db_symbol = symbol_map.get(symbol)
        if not db_symbol:
            return {"bars": [], "xMin": 0, "xMax": 0}

        rows = await self.repository.get_history(db_symbol, limit=2000)
        if not rows:
            return {"bars": [], "xMin": 0, "xMax": 0}

        # rows are newest-first; reverse for chart (oldest→newest)
        rows = list(reversed(rows))
        bars = [
            {
                "time": r["ts"],
                "open": round(r["open"], 2),
                "high": round(r["high"], 2),
                "low": round(r["low"], 2),
                "close": round(r["price"], 2),
            }
            for r in rows
        ]
        return {"bars": bars, "xMin": bars[0]["time"], "xMax": bars[-1]["time"]}

    async def get_latest_price(self, symbol: str) -> dict | None:
        """Get the latest price for a single symbol."""
        return await self.repository.get_latest(symbol)
