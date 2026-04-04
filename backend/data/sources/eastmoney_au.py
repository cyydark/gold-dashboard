"""AU9999 real-time data via Eastmoney futures SSE API.

Token is extracted from the quote page JS at startup and refreshed hourly.
API endpoint: https://66.futsseapi.eastmoney.com/sse/118_AU9999_qt  (SSE streaming)
Token source: https://quote.eastmoney.com/newstatic/build/globalfuture.js
"""
import logging
import re
import time
import requests

logger = logging.getLogger(__name__)

_CACHE: dict | None = None
_CACHE_TTL = 30
_TOKEN_TTL = 3600

_token: str | None = None
_token_ts: float = 0.0
_FALLBACK_TOKEN = "1101ffec61617c99be287c1bec3085ff"


def _fetch_token() -> str | None:
    """Extract the API token from the Eastmoney quote page JS."""
    global _token, _token_ts
    now = time.time()
    if _token is not None and (now - _token_ts) < _TOKEN_TTL:
        return _token

    try:
        resp = requests.get(
            "https://quote.eastmoney.com/newstatic/build/globalfuture.js",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/javascript,*/*",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        text = resp.text
        match = re.search(r'token["\']?\s*:\s*["\']?([0-9a-f]{32})', text)
        if match:
            _token = match.group(1)
            _token_ts = now
            logger.info(f"Eastmoney token acquired: {_token}")
            return _token
        logger.warning("Eastmoney token not found in JS, using fallback")
        return _FALLBACK_TOKEN
    except Exception as e:
        logger.warning(f"Failed to fetch Eastmoney token: {e}")
        return _FALLBACK_TOKEN


def fetch_au9999() -> dict | None:
    """Fetch AU9999 real-time data from Eastmoney SSE API, cached for 30 seconds."""
    global _CACHE, _CACHE_TTL
    now = time.time()

    if _CACHE is not None and (now - _CACHE.get("_ts", 0)) < _CACHE_TTL:
        return _CACHE

    qt = _fetch_raw()
    if qt is None:
        return _CACHE

    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))

    try:
        price = float(qt["p"])
        open_px = float(qt["o"])
        high = float(qt["h"])
        low = float(qt["l"])
        change = float(qt["zde"])
        pct = float(qt["zdf"])
        utime = int(qt["utime"])

        result = {
            "symbol": "AU9999",
            "name": "国内黄金 AU9999",
            "price": round(price, 2),
            "change": round(change, 2),
            "pct": round(pct, 2),
            "open": round(open_px, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "unit": "CNY/g",
            "updated_at": datetime.fromtimestamp(utime, BEIJING_TZ).strftime(
                "%m月%d日 %H:%M:%S 北京时间"
            ),
            "_ts": now,
        }
        _CACHE = result
        return result
    except Exception as e:
        logger.warning(f"Eastmoney AU9999 transform error: {e}, qt={qt}")
        return _CACHE


def _fetch_raw() -> dict | None:
    """Fetch raw AU9999 data from Eastmoney SSE API."""
    token = _fetch_token()
    try:
        resp = requests.get(
            "https://66.futsseapi.eastmoney.com/sse/118_AU9999_qt",
            params={
                "token": token,
                "field": (
                    "name,sc,dm,p,zsjd,zdf,zde,utime,o,"
                    "zjsj,qrspj,h,l,mrj,mcj,vol,cclbh,zt,dt,"
                    "np,wp,ccl,rz,cje,mcl,mrl,jjsj,j,lb,zf"
                ),
            },
            headers={
                "Referer": "https://quote.eastmoney.com/globalfuture/AU9999.html",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/event-stream",
            },
            stream=True,
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8", errors="replace")
            raw = ""
            if decoded.startswith("data:"):
                raw = decoded[5:].strip()
            elif decoded.startswith("{"):
                raw = decoded
            if not raw:
                continue
            import json
            obj = json.loads(raw)
            qt = obj.get("qt", {})
            if qt:
                return qt

        logger.warning("Eastmoney SSE: no data events received")
        return None
    except Exception as e:
        logger.warning(f"Eastmoney AU9999 request error: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_au9999()
    print("AU9999 result:", result)
