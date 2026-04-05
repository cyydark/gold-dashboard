"""XAUUSD 5分钟K线 via Binance API.

数据源: Binance XAUT/USDT 5分钟K线
Binance API: https://www.binance.com/api/v3/klines?symbol=XAUTUSDT&interval=5m&limit=1000
"""
import logging
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def fetch_xauusd_history() -> list[dict] | None:
    """Fetch XAUUSD OHLCV via Binance 5m klines.

    Returns:
        List of bars [{time, open, high, low, close, volume}, ...] or None on error.
    Binance returns max 1000 bars per request. 5m × 1000 ≈ 3.5 days.
    """
    try:
        resp = requests.get(
            "https://www.binance.com/api/v3/klines",
            params={"symbol": "XAUTUSDT", "interval": "5m", "limit": 1000},
            headers=_HEADERS,
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
            "time":  ts_s,
            "open":  round(float(k[1]), 2),
            "high":  round(float(k[2]), 2),
            "low":   round(float(k[3]), 2),
            "close": round(float(k[4]), 2),
            "volume": 0,
        })
    return records if records else None
