"""Price business logic service — stateless REST-only.

DB layer removed; all price data comes from REST sources (browse routes/price.py
for the actual API endpoints, which call source modules directly).
"""
import asyncio
import time
from datetime import datetime, timedelta
from backend.config import BEIJING_TZ


class PriceService:
    """Service for price-related business logic (REST-only, no DB)."""

    async def get_current_prices(self) -> dict:
        """Fetch current prices for all symbols from REST sources.

        Returns dict with XAUUSD, AU9999, USDCNY if available.
        """
        from backend.data.sources.binance_kline import fetch_xauusd_realtime
        from backend.data.sources.sina_au9999 import fetch_au9999_realtime
        from backend.data.sources.yfinance_fx import fetch_usdcny

        now_ts = int(time.time())
        result = {}

        # XAUUSD: realtime ticker via Binance
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

        # AU9999: realtime via Sina
        au_rt = await asyncio.to_thread(fetch_au9999_realtime)
        if au_rt:
            result["AU9999"] = {
                "symbol": "AU9999",
                "name": "国内黄金 AU9999",
                "price": round(au_rt["price"], 2),
                "change": round(au_rt.get("change", 0), 2),
                "pct": round(au_rt.get("pct", 0), 2),
                "open": round(au_rt["open"], 2),
                "high": round(au_rt["high"], 2),
                "low": round(au_rt["low"], 2),
                "unit": "CNY/g",
                "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
            }

        # USDCNY: latest bar via yfinance
        fx_bars = await asyncio.to_thread(fetch_usdcny)
        if fx_bars:
            fx_bar = fx_bars[-1]
            result["USDCNY"] = {
                "symbol": "USDCNY",
                "name": "人民币兑美元 CNY/USD",
                "price": round(fx_bar["close"], 4),
                "change": round(fx_bar.get("change", 0), 4),
                "pct": round(fx_bar.get("pct", 0), 4),
                "open": round(fx_bar.get("open", fx_bar["close"]), 4),
                "high": round(fx_bar.get("high", fx_bar["close"]), 4),
                "low": round(fx_bar.get("low", fx_bar["close"]), 4),
                "unit": "CNY/USD",
                "updated_at": datetime.fromtimestamp(fx_bar.get("time", now_ts), BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
            }

        return result
