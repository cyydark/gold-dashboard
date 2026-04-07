"""国内金价 AU9999 K线 via Sina SHFE Gold Futures (AU0) 1分钟K线.

数据源: stock2.finance.sina.com.cn (Sina SHFE Futures)
品种: AU0 (SHFE 黄金主力连续期货)
单位: CNY/g

说明:
  - AU0 与 AU9999 现货价格高度相关，期货与现货升贴水通常在 ±5 CNY/g 以内
  - 频率: 1分钟，约 5 个交易日，~1023 条（上接口限制）

K线接口: InnerFuturesNewService.getFewMinLine (symbol=AU0, type=1)
字段: d=时间, o=开盘, h=最高, l=最低, c=收盘, v=成交量, p=持仓量
"""
import json
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

_URL = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php"
    "/=/InnerFuturesNewService.getFewMinLine"
)
_SYMBOL = "AU0"
_TYPE = "1"  # 1分钟


def fetch_au9999_realtime() -> list[dict] | None:
    """Fetch AU9999-style Kline bars via Sina AU0 SHFE Futures (1min).

    Returns up to 1023 bars (1-minute frequency, ~5 trading days).
    Uses close price as proxy for AU9999 spot level.
    """
    try:
        resp = requests.get(
            _URL,
            params={"symbol": _SYMBOL, "type": _TYPE},
            headers=_HEADERS,
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        text = resp.text
        lparen = text.index("=(")
        rparen = text.rindex(")")
        bars = json.loads(text[lparen + 2 : rparen])
    except Exception as e:
        logger.warning(f"Sina AU0 1min Kline error: {e}")
        return None

    if not bars:
        logger.warning("Sina AU0 1min Kline: no bars returned")
        return None

    records = []
    for bar in bars:
        try:
            dt = datetime.strptime(bar["d"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        records.append({
            "time":   int(dt.timestamp()),
            "open":   float(bar["o"]),
            "high":   float(bar["h"]),
            "low":    float(bar["l"]),
            "close":  float(bar["c"]),
            "volume": float(bar["v"]) if bar.get("v") else 0.0,
        })

    return records if records else None
