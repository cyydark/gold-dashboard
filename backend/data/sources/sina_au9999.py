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

    Fields: [0]最新价 [1]涨跌额 [2]开盘价 [3]时间... [7]昨收 [8]今结算 [9]成交量
    注意: [10][11]不是涨跌额/涨跌幅(是成交额字段)，改用 price - [7]昨收 计算。
    """
    try:
        resp = requests.get(
            _REALTIME_URL,
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.text.strip()

        m = re.search(r'hq_str_gds_AU9999="([^"]+)"', text)
        if not m:
            logger.warning(f"Sina AU9999 realtime: pattern mismatch, text={text[:100]}")
            return None

        fields = m.group(1).split(",")
        if len(fields) < 12:
            logger.warning(f"Sina AU9999 realtime: unexpected field count {len(fields)}")
            return None

        price = float(fields[0])
        prev = float(fields[7])  # 昨收
        change = round(price - prev, 2) if prev > 0 else 0.0
        pct = round((price - prev) / prev * 100, 4) if prev > 0 else 0.0

        return {
            "price":  price,
            "open":   float(fields[2]),
            "high":   float(fields[4]),
            "low":    float(fields[5]),
            "change": change,
            "pct":    pct,
        }
    except Exception as e:
        logger.warning(f"Sina AU9999 realtime error: {e}")
        return None
