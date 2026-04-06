"""国内金价 AU9999 via Sina Finance Kline API.

数据源: quotes.sina.cn (分钟K线 / 实时快照)
品种: AU9999 (SGE 黄金9999, symbol=njs_gold)
单位: CNY/g
Kline 原生字段: day, open, close, high, low, vol
涨跌额/涨跌幅 = (close - prev_close) / prev_close * 100
"""
import logging
import re
import requests
from datetime import date, datetime

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

_KLINE_URL = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
_REALTIME_URL = "https://hq.sinajs.cn/list=njs_gold"
_SYMBOL = "njs_gold"


def fetch_au9999_realtime() -> dict | None:
    """Fetch AU9999 realtime snapshot from Sina.

    Returns fields: [1]最新价 [2]开盘价 [3]最高价 [4]最低价 [7]涨跌额 [8]涨跌幅(%)
    """
    try:
        resp = requests.get(
            _REALTIME_URL,
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.text.strip()

        # Parse: var hq_str_njs_gold="名称,最新价,开盘价,...,涨跌额,涨跌幅,..."
        m = re.search(r'"([^"]+)"', text)
        if not m:
            logger.warning(f"Sina realtime: pattern mismatch, text={text[:100]}")
            return None

        fields = m.group(1).split(",")
        if len(fields) < 9:
            logger.warning(f"Sina realtime: unexpected field count {len(fields)}")
            return None

        return {
            "price":  float(fields[1]),
            "open":   float(fields[2]),
            "high":   float(fields[3]),
            "low":    float(fields[4]),
            "change": float(fields[7]),
            "pct":    float(fields[8]),
        }
    except Exception as e:
        logger.warning(f"Sina realtime error: {e}")
        return None


def fetch_au9999_history(scale: int = 5, datalen: int = 1023) -> list[dict] | None:
    """Fetch AU9999 Kline bars from Sina.

    Args:
        scale:   K线周期（分钟数），默认 5 分钟
        datalen: 返回条数上限，默认 1023

    Returns list of bars ordered oldest -> newest.
    change/pct 使用前一日收盘价（首条数据的昨收字段）计算。
    """
    try:
        resp = requests.get(
            _KLINE_URL,
            params={"symbol": _SYMBOL, "scale": scale, "datalen": datalen},
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        bars: list[dict] = resp.json()
    except Exception as e:
        logger.warning(f"Sina Kline error: {e}")
        return None

    if not bars:
        logger.warning("Sina Kline: no bars returned")
        return None

    # prev_close = close price of the bar before the first returned bar (昨收)
    prev_close = float(bars[0].get("close", 0)) if bars else 0.0
    records = []
    for bar in bars:
        close_px = float(bar["close"])
        records.append({
            "time":   int(datetime.strptime(bar["day"], "%Y-%m-%d %H:%M").timestamp()),
            "open":   float(bar["open"]),
            "high":   float(bar["high"]),
            "low":    float(bar["low"]),
            "close":  close_px,
            "volume": float(bar["vol"]),
            "change": round(close_px - prev_close, 2),
            "pct":    round((close_px - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
        })

    return records if records else None
