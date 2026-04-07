"""国内金价 AU9999 via Eastmoney Kline API.

数据源: push2his.eastmoney.com (分钟K线)
品种: AU9999 (SGE 黄金9999, secid=118.AU9999)
Kline 原生字段: time, open, close, high, low, volume
涨跌额/涨跌幅 = (f43 - f44) / 100 (数据源原生字段，昨收→现价)
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
_SECID = "118.AU9999"


def fetch_au9999_realtime() -> list[dict] | None:
    """Fetch AU9999 Kline bars from Eastmoney.

    Returns up to 1000 bars (1-minute frequency, ~2 trading days).
    change/pct computed from Eastmoney realtime API (昨收→现价).
    """
    today_str = date.today().strftime("%Y%m%d")

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
            prev_close = int(rt_data.get("f44", 0)) / 100.0
    except Exception as e:
        logger.warning(f"Eastmoney realtime error: {e}")

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
                "lmt": 1000,
            },
            headers=_HEADERS,
            timeout=10,
            proxies={"http": None, "https": None},
        )
        kline_resp.raise_for_status()
        klines = kline_resp.json().get("data", {}).get("klines", [])
    except Exception as e:
        logger.warning(f"Eastmoney Kline error: {e}")
        return None

    if not klines:
        logger.warning("Eastmoney Kline: no bars returned")
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
            "pct":    round((close_px - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
        })

    return records if records else None
