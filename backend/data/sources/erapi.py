"""USD/CNY 汇率 via er-api."""
import logging
import time
import requests
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 60  # 1 minute

_cache: dict | None = None
_cache_ts: float = 0.0


def fetch_usdcny() -> dict | None:
    """Get USD/CNY rate from er-api, with 60s cache."""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _TTL:
        return _cache

    try:
        resp = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"er-api fetch error: {e}")
        if _cache is not None:
            return _cache
        return None

    rate = float(data["rates"]["CNY"])
    cny = {
        "symbol": "USDCNY",
        "name": "美元兑人民币 USD/CNY",
        "price": round(rate, 4),
        "change": 0,
        "pct": 0,
        "unit": "CNY/USD",
        "updated_at": datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }
    _cache = cny
    _cache_ts = now
    return cny
