"""国内金价 AU9999 (黄金9999) via Eastmoney push2 realtime API.

数据源: push2.eastmoney.com/api/qt/ulist.np/get (secid=118.AU9999)
品种: 沪金 AU9999 (SGE)
单位: CNY/g

字段映射 (ulist.np):
  f2=最新价 f3=涨跌幅(%) f4=涨跌额 f5=成交量
  f17=今开 f18=昨结 f44=最高 f45=最低
涨跌额/涨跌幅直接取 f3/f4（数据源原生字段）。
"""
import logging

import httpx

logger = logging.getLogger(__name__)

_LIST_URL = (
    "https://push2.eastmoney.com/api/qt/ulist.np/get"
    "?fltt=2&invt=2"
    "&fields=f2,f3,f4,f17,f18&secids=118.AU9999"
)
# Eastmoney public API token (公开标识，非个人密钥)
_EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
_STOCK_URL = (
    "https://push2.eastmoney.com/api/qt/stock/get"
    f"?secid=118.AU9999&fields=f43,f44,f45,f46&ut={_EASTMONEY_UT}"
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}


def fetch_au9999_realtime() -> dict | None:
    """Fetch AU9999 realtime snapshot from Eastmoney.

    Returns:
        {"price": float, "change": float, "pct": float, "open": float,
         "high": float, "low": float, "unit": "CNY/g", "ts": int}
    """
    try:
        # ulist.np: change/pct from f3/f4
        list_resp = httpx.get(_LIST_URL, headers=_HEADERS, timeout=10, verify=False)
        list_resp.raise_for_status()
        diff = list_resp.json().get("data", {}).get("diff", [{}])[0]
        if not diff:
            return None

        price = float(diff.get("f2", 0))
        pct = float(diff.get("f3", 0))
        change = float(diff.get("f4", 0))
        open_ = float(diff.get("f17", 0))

        # push2 stock: high/low from f44/f45 (原始值×100)
        stock_resp = httpx.get(_STOCK_URL, headers=_HEADERS, timeout=10, verify=False)
        stock_resp.raise_for_status()
        stock_data = stock_resp.json().get("data", {})
        high = float(stock_data.get("f44", 0)) / 100
        low = float(stock_data.get("f45", 0)) / 100

        return {
            "price": round(price, 2),
            "change": round(change, 2),
            "pct": round(pct, 2),
            "open": round(open_, 2),
            "high": round(high, 2),
            "low": round(low, 2),
        }
    except Exception as e:
        logger.warning(f"Eastmoney AU9999 realtime error: {e}")
        return None
