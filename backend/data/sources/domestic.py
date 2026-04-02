"""Domestic gold (AU9999) data via akshare SDK, with 5-min cache."""
import logging
import time
import asyncio
from datetime import datetime, timezone, timedelta
import akshare as ak

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

_cache = {"data": None, "timestamp": 0.0}
_CACHE_TTL = 300  # 5 minutes


def _fetch_once_sync() -> dict | None:
    """Fetch AU9999 from Shanghai Gold Exchange via akshare (sync, no cache)."""
    for attempt in range(3):
        try:
            # 实时分时行情（最新价）
            df_spot = ak.spot_quotations_sge(symbol="Au99.99")
            latest_row = df_spot.iloc[-1]
            latest_price = float(latest_row["现价"])

            # 日K线数据（昨收/今日开盘/最高/最低）
            df_hist = ak.spot_hist_sge(symbol="Au99.99")
            latest_day = df_hist.iloc[-1]
            prev_close = float(latest_day["close"])
            today_open = float(latest_day["open"])
            day_high = float(latest_day["high"])
            day_low = float(latest_day["low"])

            change = round(latest_price - prev_close, 2)
            pct = round((change / prev_close) * 100, 2) if prev_close else 0

            now_bj = datetime.now(BEIJING_TZ)
            ts_str = now_bj.strftime("%m月%d日 %H:%M:%S 北京时间")

            return {
                "symbol": "AU9999",
                "name": "国内黄金 AU9999",
                "price": round(latest_price, 2),
                "change": change,
                "pct": pct,
                "open": round(today_open or latest_price, 2),
                "high": round(day_high or latest_price, 2),
                "low": round(day_low or latest_price, 2),
                "unit": "CNY/g",
                "updated_at": ts_str,
            }
        except Exception as e:
            logger.warning(f"akshare AU9999 attempt {attempt+1} error: {e}")
            if attempt < 2:
                time.sleep(3)
    return None


async def fetch_au9999() -> dict | None:
    """Get AU9999 data with 5-minute cache (async, uses thread pool)."""
    now = time.time()
    if _cache["data"] is not None and (now - _cache["timestamp"]) < _CACHE_TTL:
        return _cache["data"]

    # Run akshare in thread pool to avoid blocking event loop
    data = await asyncio.to_thread(_fetch_once_sync)

    if data:
        _cache["data"] = data
        _cache["timestamp"] = now
    elif _cache["data"] is not None:
        # Return stale data if fetch fails
        return _cache["data"]
    return data
