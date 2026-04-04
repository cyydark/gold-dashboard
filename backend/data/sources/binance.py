"""XAU/USD 国际金价 via Binance XAUT/USDT."""
import logging
import time
import requests
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 60  # 1 minute

_cache: dict | None = None
_cache_ts: float = 0.0


def _fetch_json(url: str) -> dict | None:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Fetch error {url}: {e}")
        return None


def fetch_xauusd() -> dict | None:
    """Get XAU/USD price from Binance XAUT/USDT, with 60s cache."""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _TTL:
        return _cache

    data = _fetch_json("https://www.binance.com/api/v3/ticker/24hr?symbol=XAUTUSDT")
    if not data or not data.get("lastPrice"):
        if _cache is not None:
            return _cache
        return None

    last = float(data["lastPrice"])
    open_px = float(data.get("openPrice", last))
    xau = {
        "symbol": "XAUUSD",
        "name": "国际黄金 XAU/USD",
        "price": round(last, 2),
        "change": round(last - open_px, 2),
        "pct": round(float(data.get("priceChangePercent", 0)), 2),
        "open": round(open_px, 2),
        "high": round(float(data["highPrice"]), 2),
        "low": round(float(data["lowPrice"]), 2),
        "unit": "USD/oz",
        "updated_at": datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }
    _cache = xau
    _cache_ts = now
    return xau


def fetch_xauusd_history(days: int = 5) -> list[dict] | None:
    """Fetch XAUUSD OHLCV via Binance 5m klines.

    Binance returns max 1000 bars per request. 5m × 1000 ≈ 3.5 days.
    """
    try:
        resp = requests.get(
            "https://www.binance.com/api/v3/klines?symbol=XAUTUSDT&interval=5m&limit=1000",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        klines = resp.json()
    except Exception as e:
        logger.warning(f"Binance klines error: {e}")
        return None

    records = []
    for k in klines:
        ts_s = int(k[0]) // 1000
        records.append({
            "time": ts_s,
            "open":  round(float(k[1]), 2),
            "high":  round(float(k[2]), 2),
            "low":   round(float(k[3]), 2),
            "close": round(float(k[4]), 2),
            "volume": 0,
        })
    return records if records else None
