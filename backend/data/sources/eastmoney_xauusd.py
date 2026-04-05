"""国际金价 GC00Y via Eastmoney Kline API.

数据源: 东方财富 push2his.eastmoney.com (COMEX 黄金期货主连)
品种: GC00Y (COMEX黄金, secid=101.GC00Y)
单位: USD/oz

涨跌额/涨跌幅 = (close - 昨收) / 昨收，昨收来自 realtime API
"""
import logging
import requests
from datetime import date, datetime

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_REALTIME_URL = "https://push2.eastmoney.com/api/qt/stock/get"
_SECID = "101.GC00Y"


def fetch_xauusd_history() -> list[dict] | None:
    """Fetch GC00Y Kline bars from Eastmoney.

    Returns up to 1500 bars (1-minute frequency, ~2 trading days).
    change/pct computed from yesterday's close (realtime API f44).
    """
    today_str = date.today().strftime("%Y%m%d")

    # Get prev_close for daily change
    prev_close = 0.0
    try:
        rt_resp = requests.get(
            _REALTIME_URL,
            params={"secid": _SECID, "fields": "f44"},
            headers=_HEADERS,
            timeout=10,
        )
        rt_resp.raise_for_status()
        rt_data = rt_resp.json().get("data", {})
        if rt_data:
            prev_close = int(rt_data.get("f44", 0)) / 10000.0
    except Exception as e:
        logger.warning(f"Eastmoney GC00Y realtime error: {e}")

    try:
        kline_resp = requests.get(
            _KLINE_URL,
            params={
                "secid": _SECID,
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": 1,
                "fqt": 1,
                "end": today_str,
                "lmt": 1500,
            },
            headers=_HEADERS,
            timeout=10,
        )
        kline_resp.raise_for_status()
        klines = kline_resp.json().get("data", {}).get("klines", [])
    except Exception as e:
        logger.warning(f"Eastmoney GC00Y Kline error: {e}")
        return None

    if not klines:
        logger.warning("Eastmoney GC00Y Kline: no bars returned")
        return None

    records = []
    for kline in klines:
        parts = kline.split(",")
        dt = datetime.strptime(parts[0], "%Y-%m-%d %H:%M")
        close_px = float(parts[2])
        records.append({
            "time":   int(dt.timestamp()),
            "open":   float(parts[1]),
            "high":   float(parts[3]),
            "low":    float(parts[4]),
            "close":  close_px,
            "volume": float(parts[5]),
            "change": round(close_px - prev_close, 2),
            "pct":    round((close_px - prev_close) / prev_close * 100, 4) if prev_close else 0.0,
        })

    return records if records else None
