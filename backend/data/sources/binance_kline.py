"""国际金价 XAUUSD — Kline 存储.

数据源: /api/v3/klines (5分钟K线, 最多1000根)
Binance symbol: XAUTUSDT
Kline 原生字段: time, open, high, low, close, volume
(无涨跌额/涨跌幅字段，存 0)
"""
import logging
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def fetch_xauusd_kline() -> list[dict] | None:
    """Fetch XAUUSD 5m Kline bars from Binance (for DB storage).

    Returns:
        List of bars [{time, open, high, low, close, volume, change, pct}, ...]
        Kline has no change/pct fields, stored as 0.
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
        logger.warning(f"Binance Kline error: {e}")
        return None

    records = []
    for k in klines:
        records.append({
            "time":   int(k[0]) // 1000,
            "open":   round(float(k[1]), 2),
            "high":   round(float(k[2]), 2),
            "low":    round(float(k[3]), 2),
            "close":  round(float(k[4]), 2),
            "volume": 0,
            "change": 0,
            "pct":    0,
        })
    return records if records else None


# -------------------------------------------------------------------
# 实时价格 — SSE 展示用
# -------------------------------------------------------------------
def fetch_xauusd_realtime() -> dict | None:
    """Fetch XAUUSD current price from Binance 24hr ticker (for SSE display).

    Returns:
        {price, change, pct, open, high, low} or None on error.
    """
    try:
        resp = requests.get(
            "https://www.binance.com/api/v3/ticker/24hr",
            params={"symbol": "XAUTUSDT"},
            headers=_HEADERS,
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        d = resp.json()
        return {
            "price":  round(float(d.get("lastPrice", 0)), 2),
            "change": round(float(d.get("priceChange", 0)), 2),
            "pct":    round(float(d.get("priceChangePercent", 0)), 2),
            "open":   round(float(d.get("openPrice", 0)), 2),
            "high":   round(float(d.get("highPrice", 0)), 2),
            "low":    round(float(d.get("lowPrice", 0)), 2),
        }
    except Exception as e:
        logger.warning(f"Binance ticker error: {e}")
        return None
