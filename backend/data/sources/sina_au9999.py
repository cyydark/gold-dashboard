"""国内金价 AU9999 via Sina Finance realtime snapshot.

数据源: hq.sinajs.cn (symbol=gds_AU9999)
品种: 沪金99 (gds_AU9999)
单位: CNY/g

注意: 新浪K线接口已停用，图表K线数据改用 eastmoney_xauusd。
"""
import logging
import re
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

_REALTIME_URL = "https://hq.sinajs.cn/list=gds_AU9999"


def fetch_au9999_realtime() -> dict | None:
    """Fetch AU9999 realtime snapshot from Sina (gds_AU9999).

    Returns fields: [0]最新价 [2]开盘价 [4]最高价 [5]最低价 [10]涨跌额 [11]涨跌幅(%)
    """
    try:
        resp = requests.get(
            _REALTIME_URL,
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.text.strip()

        # Parse: var hq_str_gds_AU9999="1034.00,0,1034.00,1034.50,1042.00,1020.00,15:29:49,1027.50,1022.00,425104,43.00,1.00,2026-04-03,沪金99";
        m = re.search(r'hq_str_gds_AU9999="([^"]+)"', text)
        if not m:
            logger.warning(f"Sina AU9999 realtime: pattern mismatch, text={text[:100]}")
            return None

        fields = m.group(1).split(",")
        if len(fields) < 12:
            logger.warning(f"Sina AU9999 realtime: unexpected field count {len(fields)}")
            return None

        return {
            "price":  float(fields[0]),
            "open":   float(fields[2]),
            "high":   float(fields[4]),
            "low":    float(fields[5]),
            "change": float(fields[10]),
            "pct":    float(fields[11]),
        }
    except Exception as e:
        logger.warning(f"Sina AU9999 realtime error: {e}")
        return None
