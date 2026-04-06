"""在岸人民币/美元 (USDCNY) via Sina Finance realtime snapshot.

数据源: hq.sinajs.cn (symbol=fx_susdcny)
品种: 在岸人民币 USDCNY
单位: CNY/USD
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

_REALTIME_URL = "https://hq.sinajs.cn/list=fx_susdcny"


def fetch_usdcny() -> list[dict] | None:
    """Fetch USDCNY realtime snapshot from Sina (fx_susdcny).

    Returns a list with one bar: [{time, open, high, low, close, volume}]
    Compatible with yfinance_fx.fetch_usdcny return format.
    """
    try:
        resp = requests.get(_REALTIME_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()

        # Parse: var hq_str_fx_susdcny="19:30:56,6.8816,6.8821,6.8859,...,在岸人民币,-0.0595,-0.0041,...";
        m = re.search(r'hq_str_fx_susdcny="([^"]+)"', text)
        if not m:
            logger.warning(f"Sina USDCNY realtime: pattern mismatch, text={text[:100]}")
            return None

        fields = m.group(1).split(",")
        if len(fields) < 12:
            logger.warning(f"Sina USDCNY realtime: unexpected field count {len(fields)}")
            return None

        # [1]open, [2]prev_close, [3]high, [7]low, [8]current_price, [10]change, [11]pct
        price = float(fields[8])
        prev = float(fields[2])
        open_ = float(fields[1])
        high = float(fields[3])
        low = float(fields[7])
        change = float(fields[10])
        pct = float(fields[11])

        import time as _time
        return [{
            "time": int(_time.time()),
            "open": open_,
            "high": high,
            "low": low,
            "close": price,
            "volume": 0,
            # extra fields for API response
            "price": price,
            "change": change,
            "pct": pct,
        }]
    except Exception as e:
        logger.warning(f"Sina USDCNY realtime error: {e}")
        return None
