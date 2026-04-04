"""USD/CNY 汇率 via Eastmoney SSE API (USDCNH).

API: https://80.push2.eastmoney.com/api/qt/stock/sse?secid=133.USDCNH
HTTP/1.1 返回空响应，必须使用 HTTP/2（curl --http2）。
Cookie 不是必需的（浏览器访问时带 cookie 是为了 Session 跟踪，与 API 可用性无关）。
"""
import json
import logging
import subprocess
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 60

_cache: dict | None = None
_cache_ts: float = 0.0


def _fetch_raw() -> dict | None:
    """Fetch USDCNH data via Eastmoney SSE API（HTTP/2）。"""
    url = (
        "https://80.push2.eastmoney.com/api/qt/stock/sse"
        "?secid=133.USDCNH"
        "&fields=f43,f44,f45,f46,f58,f60,f86"
        "&invt=2&fltt=1"
    )
    cmd = [
        "curl", "-sL", "--max-time", "10", "--http2",
        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Referer: https://quote.eastmoney.com/",
        "-H", "Accept: text/event-stream, */*",
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        # SSE stream may contain multiple "data:" lines; take first with actual data
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "null":
                continue
            obj = json.loads(line)
            data = obj.get("data", {})
            if data:
                return data
        logger.warning("Eastmoney FX SSE: no data in stream")
        return None
    except Exception as e:
        logger.warning(f"Eastmoney FX curl error: {e}")
        return None


def fetch_usdcny() -> dict | None:
    """Get USD/CNY (USDCNH) from Eastmoney, cached 60 seconds."""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _TTL:
        return _cache

    qt = _fetch_raw()
    if qt is None:
        return _cache

    try:
        # 字段（与浏览器对照）：
        #   f43=当前价  f46=今开  f44=今高  f45=今低  f60=昨收
        #   f58=名称  f86=Unix时间戳
        # 价格字段均需除以 10000
        price = float(qt.get("f43", 0)) / 10000
        open_px = float(qt.get("f46", 0)) / 10000
        high = float(qt.get("f44", 0)) / 10000
        low = float(qt.get("f45", 0)) / 10000
        prev_close = float(qt.get("f60", 0)) / 10000
        name = qt.get("f58", "美元兑离岸人民币")
        ut_ts = int(qt.get("f86", 0))

        change = round(price - prev_close, 4)
        pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0

        # f86 = Unix 时间戳（秒）
        updated_at = datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间")
        if ut_ts > 0:
            try:
                updated_at = datetime.fromtimestamp(ut_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间")
            except Exception:
                pass

        result = {
            "symbol": "USDCNY",
            "name": name,
            "price": round(price, 4),
            "change": round(change, 4),
            "pct": round(pct, 2),
            "open": round(open_px, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "unit": "CNY/USD",
            "updated_at": updated_at,
            "_ts": now,
        }
        _cache = result
        _cache_ts = now
        return result
    except Exception as e:
        logger.warning(f"Eastmoney USDCNH transform error: {e}, qt={qt}")
        return _cache


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_usdcny()
    print("USDCNY result:", result)
