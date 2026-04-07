"""国内金价 AU9999 (黄金9999) via Eastmoney push2 realtime API.

数据源: push2.eastmoney.com/api/qt/stock/get (secid=118.AU9999)
品种: 沪金 AU9999 (SGE)
单位: CNY/g

注意: eastmoney_au9999.py 提供K线数据，本文件仅提供实时快照。
涨跌额/涨跌幅 基于 Eastmoney Kline 的昨收计算（不混用其他数据源）。
"""
import logging

import httpx

logger = logging.getLogger(__name__)

_EM_URL = (
    "https://push2.eastmoney.com/api/qt/stock/get"
    "?secid=118.AU9999"
    "&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58"
    "&ut=fa5fd1943c7b386f172d6893dbfba10b"
)
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

_prev_close: float | None = None


def _fetch_prev_close_em() -> float:
    """Fetch AU9999 prev_close from Eastmoney Kline (last bar's close)."""
    global _prev_close
    if _prev_close is not None:
        return _prev_close
    try:
        from datetime import date
        today = date.today().strftime("%Y%m%d")
        kline_url = (
            "https://push2his.eastmoney.com/api/qt/stock/kline/get"
            "?secid=118.AU9999"
            "&fields1=f1,f2,f3,f4"
            "&fields2=f51,f52,f53,f54,f55,f56,f57"
            "&klt=1&fqt=1&end=" + today + "&lmt=2"
        )
        r = httpx.get(kline_url, headers=_EM_HEADERS, timeout=10, verify=False)
        r.raise_for_status()
        klines = r.json().get("data", {}).get("klines", [])
        # Kline returned: date,open,close,high,low,volume,amount (ascending time)
        # First bar = oldest, last bar = latest
        if klines:
            # Use first bar close as prev_close (it's from previous session)
            parts = klines[0].split(",")
            if len(parts) >= 3:
                _prev_close = float(parts[2])
    except Exception as e:
        logger.warning(f"Eastmoney Kline for prev_close error: {e}")
    return _prev_close or 0.0


def fetch_au9999_realtime() -> dict | None:
    """Fetch AU9999 realtime snapshot from Eastmoney.

    Returns:
        {"price": float, "change": float, "pct": float, "open": float,
         "high": float, "low": float, "unit": "CNY/g", "ts": int}
    """
    try:
        resp = httpx.get(_EM_URL, headers=_EM_HEADERS, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        if not data:
            return None

        price = float(data.get("f43", 0)) / 100
        high = float(data.get("f44", 0)) / 100
        low = float(data.get("f45", 0)) / 100
        open_ = float(data.get("f46", 0)) / 100

        prev = _fetch_prev_close_em()
        change = round(price - prev, 2) if prev > 0 else 0.0
        pct = round((price - prev) / prev * 100, 4) if prev > 0 else 0.0

        return {
            "price": round(price, 2),
            "change": change,
            "pct": pct,
            "open": round(open_, 2),
            "high": round(high, 2),
            "low": round(low, 2),
        }
    except Exception as e:
        logger.warning(f"Eastmoney AU9999 realtime error: {e}")
        return None
