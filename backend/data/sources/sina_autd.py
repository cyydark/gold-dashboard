"""国内黄金T+D (AUTD) via Sina Finance API.

数据源: quotes.sina.cn (分钟K线) + hq.sinajs.cn (实时快照)
品种: AUTD (SGE 黄金T+D, gds_AUTD 延期 / hf_AUTD 期货)
单位: CNY/g
K线接口 symbol 使用 hf_AUTD (期货); 实时接口 symbol 使用 gds_AUTD (延期).
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

_KLINE_URL = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
_REALTIME_URL = "https://hq.sinajs.cn/list=gds_AUTD"


def fetch_autd_history(scale: int = 5, datalen: int = 1023) -> list[dict] | None:
    """Fetch AUTD 5-minute Kline bars from Sina Finance.

    Args:
        scale: K线周期（分钟数），支持 1/5/15/30/60，默认 5 分钟。
        datalen: 本次请求返回的最多 bar 数量，默认 1023。

    Returns:
        每项包含 time(int timestamp), open, high, low, close, volume, change, pct。
        change/pct 以当日开盘价为基准计算（K线接口不直接提供昨收）。
        出错或无数据时返回 None。
    """
    try:
        resp = requests.get(
            _KLINE_URL,
            params={"symbol": "hf_AUTD", "scale": scale, "datalen": datalen},
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        bars: list[dict] = resp.json()
    except Exception as e:
        logger.warning(f"Sina AUTD Kline error: {e}")
        return None

    if not bars:
        logger.warning("Sina AUTD Kline: no bars returned")
        return None

    records = []
    for bar in bars:
        day_str = bar.get("day", "")
        open_px = float(bar.get("open", 0))
        close_px = float(bar.get("close", 0))

        try:
            dt = datetime.strptime(day_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.warning(f"Sina AUTD Kline: unrecognised day format '{day_str}', skipping")
            continue

        change = round(close_px - open_px, 2)
        pct = round(change / open_px * 100, 2) if open_px else 0.0

        records.append({
            "time":   int(dt.timestamp()),
            "open":   open_px,
            "high":   float(bar.get("high", 0)),
            "low":    float(bar.get("low", 0)),
            "close":  close_px,
            "volume": float(bar.get("vol", 0)),
            "change": change,
            "pct":    pct,
        })

    return records if records else None


def fetch_autd_realtime() -> dict | None:
    """Fetch AUTD realtime snapshot from Sina Finance.

    字段映射（gds_AUTD）:
        [0] 当前价  [1] ?  [2] 开盘  [3] 买价  [4] 最高  [5] 最低
        [6] 时间    [7] 昨收  [8] 结算价  [9] 成交量
        [12] 日期   [13] 品种名

    Returns:
        dict 包含 price, change, pct, open, high, low。
        change/pct 以昨收为基准计算。出错时返回 None。
    """
    try:
        resp = requests.get(_REALTIME_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        raw = resp.text.strip()
    except Exception as e:
        logger.warning(f"Sina AUTD realtime error: {e}")
        return None

    # 格式: var hq_str_gds_AUTD="field0,field1,...field13";
    m = re.search(r'="([^"]+)"', raw)
    if not m:
        logger.warning(f"Sina AUTD realtime: unexpected response format: {raw[:80]}")
        return None

    fields = m.group(1).split(",")
    if len(fields) < 14:
        logger.warning(f"Sina AUTD realtime: insufficient fields ({len(fields)}): {fields}")
        return None

    try:
        price = float(fields[0])
        open_px = float(fields[2])
        prev_close = float(fields[7])
    except ValueError as e:
        logger.warning(f"Sina AUTD realtime: field parse error: {e}")
        return None

    change = round(price - prev_close, 2)
    pct = round(change / prev_close * 100, 2) if prev_close else 0.0

    return {
        "price":  price,
        "change": change,
        "pct":    pct,
        "open":   open_px,
        "high":   float(fields[4]),
        "low":    float(fields[5]),
    }
