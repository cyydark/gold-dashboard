"""国内金价 AU9999 via fx678 API.

数据源: https://api-q.fx678img.com/histories.php
品种: 上海黄金交易所 AU9999
粒度: 5分钟 (5m)
历史深度: ~5天 (1600 bars 上限)
"""
import logging
import requests

logger = logging.getLogger(__name__)

_API = "https://api-q.fx678img.com/histories.php"
_PARAMS = {
    "symbol": "AU9999",
    "codeType": "5900",
    "resolution": "5",   # 5分钟
    "limit": 1600,       # 最大返回条数
}


def fetch_au9999_history() -> list[dict] | None:
    """Fetch AU9999 OHLCV via fx678 (5m, ~5 days).

    Returns:
        List of bars [{time, open, high, low, close, volume}, ...] or None on error.
    """
    try:
        resp = requests.get(
            _API,
            params=_PARAMS,
            headers={
                "Referer": "https://quote.fx678.com/symbol/AU9999",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            },
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("s") != "ok" or not data.get("t"):
            logger.warning(f"fx678 AU9999: no data, status={data.get('s')}")
            return None

        ts_list = data["t"]
        records = []
        for i, ts_s in enumerate(ts_list):
            records.append({
                "time":  ts_s,
                "open":  round(float(data["o"][i]), 2),
                "high":  round(float(data["h"][i]), 2),
                "low":   round(float(data["l"][i]), 2),
                "close": round(float(data["c"][i]), 2),
                "volume": int(data["v"][i]) if data["v"][i] else 0,
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"fx678 AU9999 error: {e}")
        return None
