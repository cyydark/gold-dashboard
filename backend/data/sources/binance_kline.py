"""国际金价 XAUUSD — Kline 存储.

数据源: /api/v3/klines (5分钟K线, 最多1000根)
Binance symbol: XAUTUSDT
Kline 原生字段: time, open, high, low, close, volume

change/pct 通过 24hr ticker 补全最新 bar 的涨跌。
"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

_TICKER_URL = "https://www.binance.com/api/v3/ticker/24hr"

# Set BINANCE_SSL_VERIFY=0 to skip SSL verification (e.g. corporate proxy)
_SSL_VERIFY = os.environ.get("BINANCE_SSL_VERIFY", "1") != "0"


def _fetch_ticker() -> dict | None:
    """Fetch 24hr ticker for XAUTUSDT: returns {price, change, pct, open, high, low}."""
    try:
        resp = requests.get(
            _TICKER_URL,
            params={"symbol": "XAUTUSDT"},
            headers=_HEADERS,
            timeout=10,
            verify=_SSL_VERIFY,
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


def fetch_xauusd_kline() -> list[dict] | None:
    """Fetch XAUUSD 5m Kline bars from Binance (for DB storage).

    Returns:
        List of bars [{time, open, high, low, close, volume, change, pct}, ...]
        Latest bar's change/pct from 24hr ticker; historical bars use 0.
    """
    try:
        resp = requests.get(
            "https://www.binance.com/api/v3/klines",
            params={"symbol": "XAUTUSDT", "interval": "5m", "limit": 1000},
            headers=_HEADERS,
            timeout=10,
            verify=_SSL_VERIFY,
        )
        resp.raise_for_status()
        klines = resp.json()
    except Exception as e:
        logger.warning(f"Binance Kline error: {e}")
        return None

    if not klines:
        return None

    # Ticker for latest bar change/pct
    ticker = _fetch_ticker()
    ticker_price = ticker["price"] if ticker else None

    records = []
    for i, k in enumerate(klines):
        close_px = round(float(k[4]), 2)
        # Latest bar: use ticker change/pct; historical: compute from prev close
        if i == 0 and ticker:
            change = ticker["change"]
            pct = ticker["pct"]
        else:
            prev_close = round(float(klines[i - 1][4]), 2) if i > 0 else close_px
            change = round(close_px - prev_close, 2)
            pct = round(change / prev_close * 100, 4) if prev_close else 0.0
        records.append({
            "time":   int(k[0]) // 1000,
            "open":   round(float(k[1]), 2),
            "high":   round(float(k[2]), 2),
            "low":    round(float(k[3]), 2),
            "close":  close_px,
            "volume": 0,
            "change": change,
            "pct":    pct,
        })
    return records


# -------------------------------------------------------------------
# 实时价格 — SSE 展示用
# -------------------------------------------------------------------
def fetch_xauusd_realtime() -> dict | None:
    """Fetch XAUUSD current price from Binance 24hr ticker (for SSE display)."""
    return _fetch_ticker()
