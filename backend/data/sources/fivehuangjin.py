"""5huangjin.com 三市场实时价格快照.

数据源: https://www.5huangjin.com/data/jin.js (5秒更新)
品种:
  - hf_XAU  伦敦金现货   (London Fix, USD/oz)
  - hf_GC   纽约金期货   (COMEX Gold Futures, USD/oz)
  - gds_AUTD 上海金延期  (SGE Au(T+D), CNY/g)

返回格式: 实时快照字典 (非K线), 用于SSE实时展示.
注意: 该接口不支持CORS, 仅限后端调用; 响应为GBK编码.
"""
import logging
import re
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_URL = "https://www.5huangjin.com/data/jin.js"

# 正则: 匹配 var hq_str_<key>="..." 中每个变量的完整值部分
_RE_VAR = re.compile(r'hq_str_(\w+)=("[^"]*")')


def fetch_fivehuangjin() -> dict | None:
    """Fetch real-time snapshots for London Gold, NY Gold, and Shanghai Gold T+D.

    Returns:
        包含三个市场实时价格的字典, 失败时返回 None.
    """
    try:
        resp = requests.get(_URL, timeout=10)
        resp.raise_for_status()
        # 页面声明GBK编码
        text = resp.content.decode("gbk")
    except Exception as e:
        logger.warning(f"5huangjin request failed: {e}")
        return None

    result: dict[str, dict] = {}

    for key, raw in _RE_VAR.findall(text):
        parts = raw.strip('"').split(",")
        if len(parts) < 13:
            logger.warning(f"5huangjin {key}: unexpected field count {len(parts)}")
            continue

        try:
            current = float(parts[0]) if parts[0] else 0.0
            prev_close = float(parts[1]) if parts[1] else 0.0
            open_px = float(parts[2]) if parts[2] else 0.0
            bid = float(parts[3]) if parts[3] else 0.0
            high = float(parts[4]) if parts[4] else 0.0
            low = float(parts[5]) if parts[5] else 0.0
            time_str = parts[6].strip()
            settle = float(parts[8]) if parts[8] else 0.0
            date_str = parts[12].strip()
        except ValueError as ve:
            logger.warning(f"5huangjin {key}: parse error {ve}")
            continue

        change = round(current - prev_close, 2)
        pct = round(change / prev_close * 100, 4) if prev_close else 0.0

        entry: dict = {
            "price": current,
            "change": change,
            "pct": pct,
            "open": open_px,
            "high": high,
            "low": low,
            "time": time_str,
            "date": date_str,
        }

        if key == "hf_XAU":
            entry["bid"] = bid
            entry["ask"] = current  # 现货无明确ask, 用当前价代替
            entry["unit"] = "USD/oz"
        elif key == "hf_GC":
            entry["unit"] = "USD/oz"
        elif key == "gds_AUTD":
            entry["unit"] = "CNY/g"

        result[key] = entry

    if not result:
        logger.warning("5huangjin: no valid market data extracted")
        return None

    result["updated_at"] = datetime.now(timezone.utc).isoformat()
    return result
