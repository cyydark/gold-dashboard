"""国际金价 via Eastmoney SSE API (GC00Y / COMEX黄金期货).

API: https://8.futsseapi.eastmoney.com/sse/101_GC00Y_qt
Token获取参考 eastmoney_au.py（从 globalfuture.js 提取）。
"""
import logging
import re
import time
import requests
import json
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 60  # 1 minute

_cache: dict | None = None
_cache_ts: float = 0.0
_FALLBACK_TOKEN = "1101ffec61617c99be287c1bec3085ff"


def _fetch_token() -> str:
    """从 globalfuture.js 提取 Eastmoney SSE API token。"""
    try:
        resp = requests.get(
            "https://quote.eastmoney.com/newstatic/build/globalfuture.js",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/javascript"},
            timeout=10, verify=False,
        )
        resp.raise_for_status()
        match = re.search(r'token["\']?\s*:\s*["\']?([0-9a-f]{32})', resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"Token fetch error: {e}")
    return _FALLBACK_TOKEN


def _fetch_raw() -> dict | None:
    """Fetch raw GC00Y data from Eastmoney SSE API."""
    token = _fetch_token()
    url = f"https://8.futsseapi.eastmoney.com/sse/101_GC00Y_qt"
    params = {"token": token}
    try:
        resp = requests.get(
            url,
            params=params,
            headers={
                "Referer": "https://quote.eastmoney.com/",
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/event-stream",
            },
            timeout=10, stream=True, verify=False,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8", errors="replace")
            if decoded.startswith("data:") or decoded.startswith("{"):
                raw = decoded[5:].strip() if decoded.startswith("data:") else decoded
                obj = json.loads(raw)
                qt = obj.get("qt", {})
                if qt:
                    return qt
        logger.warning("Eastmoney GC00Y: no data events received")
        return None
    except Exception as e:
        logger.warning(f"Eastmoney GC00Y request error: {e}")
        return None


def fetch_xauusd() -> dict | None:
    """Get 国际金价 (GC00Y) from Eastmoney, cached 60 seconds."""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _TTL:
        return _cache

    qt = _fetch_raw()
    if qt is None:
        return _cache

    try:
        # 字段: p=价格, zdf=涨跌幅%, zde=涨跌额, o=开盘, h=最高, l=最低
        # zsjd=小数位数(1=1位小数)，价格已直接是USD，无需除以任何数
        zsjd = int(qt.get("zsjd", 2))
        price = round(float(qt.get("p", 0)), zsjd)
        pct = round(float(qt.get("zdf", 0)), 2)
        change = round(float(qt.get("zde", 0)), zsjd)
        open_px = round(float(qt.get("o", price)), zsjd)
        high = round(float(qt.get("h", price)), zsjd)
        low = round(float(qt.get("l", price)), zsjd)
        name = qt.get("name", "COMEX黄金")
        ut_str = str(qt.get("utime", ""))

        updated_at = datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间")
        if ut_str.isdigit():
            try:
                ut = datetime.fromtimestamp(int(ut_str), BEIJING_TZ)
                updated_at = ut.strftime("%m月%d日 %H:%M:%S 北京时间")
            except Exception:
                pass

        result = {
            "symbol": "XAUUSD",
            "name": name,
            "price": round(price, 2),
            "change": round(change, 2),
            "pct": round(pct, 2),
            "open": round(open_px, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "unit": "USD/oz",
            "updated_at": updated_at,
            "_ts": now,
        }
        _cache = result
        _cache_ts = now
        return result
    except Exception as e:
        logger.warning(f"Eastmoney GC00Y transform error: {e}, qt={qt}")
        return _cache


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_xauusd()
    print("XAUUSD result:", result)
