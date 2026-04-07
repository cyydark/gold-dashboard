"""国内金价 AU9999 (黄金9999) via Eastmoney push2 realtime API.

数据源: push2.eastmoney.com/api/qt/stock/get (secid=118.AU9999)
品种: 沪金 AU9999 (SGE)
单位: CNY/g

注意: eastmoney_au9999.py 提供K线数据，本文件仅提供实时快照。
字段映射:
  f43=最新价(×100) f44=最高(×100) f45=最低(×100)
  f46=今开(×100)   f47=成交量    f48=成交额
  f50=时间(分)     f57=代码      f58=名称
涨跌额/涨跌幅 基于本地缓存计算。
"""
import logging

import httpx

logger = logging.getLogger(__name__)

_URL = (
    "https://push2.eastmoney.com/api/qt/stock/get"
    "?secid=118.AU9999"
    "&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58"
    "&ut=fa5fd1943c7b386f172d6893dbfba10b"
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

# 本地缓存上一笔价格（用于计算涨跌）
_last_price: float | None = None


def fetch_au9999_realtime() -> dict | None:
    """Fetch AU9999 realtime snapshot from Eastmoney.

    Returns:
        {"price": float, "change": float, "pct": float, "open": float,
         "high": float, "low": float, "unit": "CNY/g", "ts": int}
    """
    global _last_price
    try:
        resp = httpx.get(_URL, headers=_HEADERS, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        if not data:
            return None

        # f43/f44/f45/f46 原始值为 ×100 的整数
        price = float(data.get("f43", 0)) / 100
        high = float(data.get("f44", 0)) / 100
        low = float(data.get("f45", 0)) / 100
        open_ = float(data.get("f46", 0)) / 100
        ts = int(data.get("f50", 0))  # 分钟时间戳（近似）

        if _last_price is not None and _last_price > 0:
            change = round(price - _last_price, 2)
            pct = round((change / _last_price) * 100, 4)
        else:
            change = 0.0
            pct = 0.0

        _last_price = price

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
