"""国际金价 XAU via Sina Finance Kline & Realtime API.

数据源: 新浪财经 finance.sina.com.cn
品种: hf_XAU (伦敦金现货, 美元/盎司)
单位: USD/oz

K线接口: CN_MarketDataService.getKLineData (5分钟K线, 1023根)
实时接口: hq.sinajs.cn (伦敦金快照)

涨跌额/涨跌幅 = (close - 今结算) / 今结算，今结算来自实时接口 f8
"""

import logging
import re
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

_REALTIME_URL = "https://hq.sinajs.cn/list=hf_XAU"


def fetch_xauusd_realtime() -> dict | None:
    """Fetch XAU realtime snapshot from Sina Finance.

    Returns current price, change, pct, open, high, low.
    change/pct = (price - prev_close) / prev_close, using field[7] (昨收).
    """
    try:
        resp = requests.get(_REALTIME_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()
        # var hq_str_hf_XAU="4651.71,4675.990,4651.71,4652.06,4671.60,4600.79,
        #                    10:42:00,4675.99,4652.28,0,0,0,2026-04-06,伦敦金收盘价仅供参考";
        m = re.search(r'hq_str_hf_XAU="([^"]+)"', text)
        if not m:
            logger.warning("Sina XAU realtime: pattern not matched")
            return None

        fields = m.group(1).split(",")
        if len(fields) < 9:
            logger.warning(f"Sina XAU realtime: expected >=9 fields, got {len(fields)}")
            return None

        price = float(fields[0])      # f0: 当前价
        # f1: 昨收, f2: 开盘, f3: 买价, f4: 最高, f5: 最低
        # f6: 时间, f7: 昨收, f8: 今结算
        open_px = float(fields[2])
        high_px = float(fields[4])
        low_px = float(fields[5])
        prev_close = float(fields[7])  # f7: 昨收

        change = round(price - prev_close, 2)
        pct = round((price - prev_close) / prev_close * 100, 4) if prev_close else 0.0

        return {
            "price": price,
            "change": change,
            "pct": pct,
            "open": open_px,
            "high": high_px,
            "low": low_px,
        }
    except Exception as e:
        logger.warning(f"Sina XAU realtime error: {e}")
        return None
