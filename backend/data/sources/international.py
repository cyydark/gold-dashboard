"""GCW00:COMEX (COMEX gold futures) via Google Finance batchexecute API.

International gold: Google Finance /finance/_/GoogleFinanceUi/data/batchexecute?rpcids=AiCwsd
  — captures the same OHLCV data displayed on https://www.google.com/finance/quote/GCW00:COMEX
  — requires x-goog-ext-* auth header captured from Playwright, replayed immediately
USD/CNY: yfinance Ticker("CNY=X") — 离岸人民币汇率

All functions are synchronous with their own cache.
"""
import os
import re
import logging
import time
import json
import requests
import urllib.parse
from datetime import datetime, timezone, timedelta

_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "translategemma:4b")
_OLLAMA_URL = "http://localhost:11434/api/generate"

import yfinance as yf
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

CHROME_PATH = os.environ.get("CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
BEIJING_TZ = timezone(timedelta(hours=8))

_xau_cache = {"data": None, "timestamp": 0.0}
_usdcny_cache = {"data": None, "timestamp": 0.0}
_gf_history_cache: dict[int, dict] = {}  # {window: {"data": records, "timestamp": float}}
_TTL = 60  # 1 minute
_GF_HISTORY_TTL = 300  # 5 minutes


def _fetch_xauusd_once() -> dict | None:
    """Fetch GC=F (COMEX gold futures) via yfinance — sync, no cache."""
    try:
        ticker = yf.Ticker("GC=F")
        info = ticker.info

        price = info.get("regularMarketPrice")
        prev_close = info.get("regularMarketPreviousClose")
        day_open = info.get("regularMarketOpen")
        day_high = info.get("regularMarketDayHigh")
        day_low = info.get("regularMarketDayLow")
        change_abs = (price - prev_close) if (price and prev_close) else None
        change_pct = (change_abs / prev_close * 100) if prev_close else None

        # Derive open if not provided
        open_price = day_open or (price - change_abs if (price and change_abs is not None) else price)

        now_bj = datetime.now(BEIJING_TZ)
        ts_str = now_bj.strftime("%m月%d日 %H:%M:%S 北京时间")

        return {
            "symbol": "XAUUSD",
            "name": "国际黄金 XAU/USD",
            "price": round(price, 2) if price else None,
            "change": round(change_abs, 2) if change_abs is not None else 0,
            "pct": round(change_pct, 2) if change_pct is not None else 0,
            "open": round(open_price, 2) if open_price else None,
            "high": round(day_high, 2) if day_high else None,
            "low": round(day_low, 2) if day_low else None,
            "unit": "USD/oz",
            "updated_at": ts_str,
        }
    except Exception as e:
        logger.warning(f"yfinance GC=F error: {e}")
        return None


def _fetch_usdcny_once() -> dict | None:
    """Fetch CNY=X (USD/CNY) via yfinance — sync, no cache."""
    try:
        ticker = yf.Ticker("CNY=X")
        data = ticker.history(period="2d", auto_adjust=True)
        if data.empty or len(data) < 1:
            return None

        latest = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else latest

        price = float(latest["Close"])
        change = round(price - float(prev["Close"]), 4)
        pct = round((change / float(prev["Close"]) * 100), 4) if prev["Close"] else 0

        now_bj = datetime.now(BEIJING_TZ)
        ts_str = now_bj.strftime("%m月%d日 %H:%M:%S 北京时间")

        return {
            "symbol": "USDCNY",
            "name": "美元兑人民币 USD/CNY",
            "price": round(price, 4),
            "change": change,
            "pct": pct,
            "open": round(float(latest["Open"]), 4),
            "high": round(float(latest["High"]), 4),
            "low": round(float(latest["Low"]), 4),
            "unit": "CNY/USD",
            "updated_at": ts_str,
        }
    except Exception as e:
        logger.warning(f"yfinance CNY=X error: {e}")
        return None


def fetch_xauusd() -> dict | None:
    """Get GC=F (COMEX) price with 60s cache."""
    now = time.time()
    if _xau_cache["data"] is not None and (now - _xau_cache["timestamp"]) < _TTL:
        return _xau_cache["data"]

    xau = _fetch_xauusd_once()
    if xau:
        _xau_cache["data"] = xau
        _xau_cache["timestamp"] = now
    elif _xau_cache["data"] is not None:
        return _xau_cache["data"]
    return xau


def fetch_usdcny() -> dict | None:
    """Get USD/CNY rate with 60s cache."""
    now = time.time()
    if _usdcny_cache["data"] is not None and (now - _usdcny_cache["timestamp"]) < _TTL:
        return _usdcny_cache["data"]

    usdcny = _fetch_usdcny_once()
    if usdcny:
        _usdcny_cache["data"] = usdcny
        _usdcny_cache["timestamp"] = now
    elif _usdcny_cache["data"] is not None:
        return _usdcny_cache["data"]
    return usdcny


# ---------------------------------------------------------------------------
# Google Finance OHLCV fetch
# ---------------------------------------------------------------------------

_WINDOW_MAP = {
    1: 1,   # 1D window  → body NUM=1
    5: 2,   # 5D window  → body NUM=2
    30: 3,  # 1M window  → body NUM=3
}

# Which window param to use based on requested days
_WINDOW_DEFAULT = {
    1: 1,
    5: 2,
    30: 3,
}


def _parse_gf_timestamp(ts_arr: list) -> int | None:
    """Convert GF ts_arr [year,month,day,hour,minute,null,null,[tz_offset]] to UTC unix ms.

    GF returns ET (UTC-4) timestamps.  E.g.
    [2026,3,27,17,0,null,null,[-14400]] → 2026-03-27 17:00 ET.
    """
    try:
        if not ts_arr or len(ts_arr) < 5:
            return None
        year, month, day = ts_arr[0], ts_arr[1], ts_arr[2]
        hour = ts_arr[3] if ts_arr[3] is not None else 0
        minute = ts_arr[4] if ts_arr[4] is not None else 0
        tz_arr = ts_arr[-1] if isinstance(ts_arr[-1], list) else []
        tz_seconds = tz_arr[0] if tz_arr else -14400  # default ET = UTC-4
        et_tz = timezone(timedelta(seconds=tz_seconds))
        et_dt = datetime(year, month, day, hour, minute, tzinfo=et_tz)
        return int(et_dt.timestamp() * 1000)
    except Exception:
        return None


def _parse_gf_raw(raw: str) -> list[dict]:
    """Parse Google Finance batchexecute raw response into flat bar list.

    Response format:
      )}'  <length>  [[wrb.fr,AiCwsd,escaped_inner_json]]

    Inner JSON: [[[GCW00, COMEX], /g/..., USD, [session_group]]]
    Bars: session_group[3][0][1] = list of [ts_arr, ohlcv]
      ohlcv = [close, spread, pct, vol_type, vol_type2, vol_type3]

    Returns list of {time, open, high, low, close, volume} sorted ascending.
    """
    # Strip length-prefixed chunks to get the outer JSON array
    try:
        header_end = raw.index("[[")
    except ValueError:
        raise ValueError("No JSON array found in GF response")

    json_str = raw[header_end:]

    # Find matching close-bracket for the outermost [[ ... ]]
    depth = 0
    arr_start = -1
    arr_end = -1
    for i, c in enumerate(json_str):
        if c == "[":
            if depth == 0:
                arr_start = i
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                arr_end = i + 1
                break

    if arr_start < 0 or arr_end < 0:
        raise ValueError(f"Could not find matching outer brackets (start={arr_start}, end={arr_end})")

    outer = json.loads(json_str[arr_start:arr_end])
    # outer = [[wrb.fr, AiCwsd, escaped_inner]]
    inner_str = outer[0][2]

    # inner_str is a JSON string with \" escaped quotes — unescape for json.loads
    inner_fixed = inner_str.replace('\\"', '"')
    parsed = json.loads(inner_fixed)
    # parsed = [[[GCW00, COMEX], /g/..., USD, [session_group]]]
    # session_group = [[[1, [start_ts], [end_ts]], bars]]
    session_groups = parsed[0]

    records = []
    for seg in session_groups:
        if not isinstance(seg, list) or len(seg) < 4:
            continue
        bar_container = seg[3]
        if not isinstance(bar_container, list) or len(bar_container) < 1:
            continue
        bars_info = bar_container[0]
        if not isinstance(bars_info, list) or len(bars_info) < 2:
            continue
        session_meta = bars_info[0]  # [1, [start_ts], [end_ts]]
        bars = bars_info[1]

        if not isinstance(bars, list):
            continue

        for bar_item in bars:
            if not isinstance(bar_item, list) or len(bar_item) < 2:
                continue
            ts_arr = bar_item[0]
            ohlcv = bar_item[1]
            if not isinstance(ts_arr, list) or not isinstance(ohlcv, list):
                continue
            if len(ohlcv) < 4:
                continue

            ts_ms = _parse_gf_timestamp(ts_arr)
            if ts_ms is None:
                continue

            # ohlcv[0]=close, ohlcv[1]=high-low spread, ohlcv[4]=volume-category?
            close_px = float(ohlcv[0])
            # Derive high/low from close ± spread/2 (spread = high - low)
            spread = float(ohlcv[1]) if ohlcv[1] else 0.0
            high_px = close_px + spread / 2.0
            low_px = close_px - spread / 2.0

            records.append({
                "time": ts_ms // 1000,   # GF ts_arr already in ET; ts_ms is ms → seconds
                "open": round(low_px, 2),
                "high": round(high_px, 2),
                "low": round(low_px, 2),
                "close": round(close_px, 2),
                "volume": 0,
            })

    records.sort(key=lambda x: x["time"])
    return records


def _fetch_gf_once(window: int) -> list[dict] | None:
    """Capture x-goog-ext header via Playwright, replay with requests.

    Args:
        window: 1=1D, 2=5D, 3=1M (maps to POST body NUM parameter)

    Returns list of {time, open, high, low, close, volume} or None on failure.
    """
    if not os.path.exists(CHROME_PATH):
        logger.warning(f"Chrome not found at {CHROME_PATH}")
        return None

    captured: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Wait for batchexecute request using expect_request context manager.
        # The chart fires this ~11s after DOM loaded; context manager blocks until received.
        try:
            with page.expect_request(lambda r: "AiCwsd" in r.url, timeout=25000) as req_info:
                page.goto(
                    "https://www.google.com/finance/quote/GCW00:COMEX",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
            matched = req_info.value
            captured["url"] = matched.url
            captured["body"] = matched.post_data
            for name, val in matched.headers.items():
                if name.startswith("x-goog-ext"):
                    captured["auth_header"] = (name, val)
                    break
        except Exception:
            pass  # TimeoutError — proceed with whatever was captured (may be empty)

        browser.close()

    url = captured.get("url")
    body = captured.get("body")
    auth_header = captured.get("auth_header")

    if not url or not body:
        logger.warning("GF batchexecute request not captured")
        return None

    # Body is URL-encoded: f.req=<encoded_json>
    # Decode, modify/replace NUM, re-encode.
    # NUM param is at the end of the inner JSON: ...]],1,null... (1=1D, 2=5D, 3=1M)
    try:
        import urllib.parse
        raw_body = body if isinstance(body, str) else body.decode("latin-1")
        params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
        inner_body = params.get("f.req", [""])[0]
        inner_decoded = urllib.parse.unquote(inner_body)
        # For window=1, body already has 1 — no change needed
        # For window=2/3, replace ]],1, with ]],{window},
        if window == 1:
            new_inner = inner_decoded
        else:
            new_inner = re.sub(r'\],\d+,', '],' + str(window) + ',', inner_decoded, count=1)
        new_body = urllib.parse.urlencode({"f.req": new_inner}).encode("latin-1")
    except Exception as e:
        logger.warning(f"Failed to modify GF body: {e}")
        return None

    # Replay with captured auth header
    headers = {}
    if auth_header:
        headers[auth_header[0]] = auth_header[1]
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    try:
        resp = requests.post(url, data=new_body, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"GF API returned {resp.status_code}")
            return None
        raw = resp.text
    except Exception as e:
        logger.warning(f"GF API request failed: {e}")
        return None

    if not raw or len(raw) < 50:
        logger.warning("GF API returned empty response")
        return None

    try:
        records = _parse_gf_raw(raw)
    except Exception as e:
        logger.warning(f"GF parse error: {e}")
        return None

    return records


def fetch_gf_xauusd_history(days: int = 5) -> list[dict] | None:
    """Fetch GCW00:COMEX OHLCV via Google Finance (5-min cache per window).

    Returns {time, open, high, low, close, volume} sorted ascending, or None on failure.
    """
    window = _WINDOW_MAP.get(days, 2)  # default to 5D window
    now = time.time()

    # Return cached data if still fresh
    if window in _gf_history_cache:
        entry = _gf_history_cache[window]
        if now - entry["timestamp"] < _GF_HISTORY_TTL:
            logger.info(f"GF cache hit window={window}, {len(entry['data'])} bars")
            return entry["data"]

    records = _fetch_gf_once(window)
    if not records:
        return None
    logger.info(f"GF fetched {len(records)} bars, range={records[0]['time']}..{records[-1]['time']}")
    _gf_history_cache[window] = {"data": records, "timestamp": now}
    return records


def _fetch_xauusd_history_fallback(days: int = 90):
    """Fallback to yfinance when GF fails."""
    try:
        ticker = yf.Ticker("GC=F")
        now_bj = datetime.now(BEIJING_TZ)
        if days <= 1:
            start_bj = now_bj - timedelta(days=1)
            data = ticker.history(start=start_bj, end=now_bj, interval="5m", auto_adjust=True)
        elif days <= 5:
            start_bj = now_bj - timedelta(days=days)
            data = ticker.history(start=start_bj, end=now_bj, interval="15m", auto_adjust=True)
        else:
            start_bj = now_bj - timedelta(days=days)
            data = ticker.history(start=start_bj, end=now_bj, interval="1d", auto_adjust=True)

        if data.empty:
            return None

        records = []
        for ts, row in data.iterrows():
            utc_ts = ts.tz_convert("UTC") if ts.tz else ts
            records.append({
                "time": int(utc_ts.timestamp()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if "Volume" in row else 0,
            })
        return records
    except Exception as e:
        logger.warning(f"yfinance history fallback error: {e}")
        return None


def fetch_xauusd_history(days: int = 5) -> list[dict] | None:
    """Fetch GCW00:COMEX OHLCV via Google Finance. Returns None on failure."""
    return fetch_gf_xauusd_history(days)


# ---------------------------------------------------------------------------
# News scraping
# ---------------------------------------------------------------------------

def _time_ago_minutes(ago: str) -> int:
    """Parse '5小时前' / '3 hours ago' → minutes for sorting (smaller = newer)."""
    if not ago:
        return 999999
    s = ago.strip()
    m = re.match(r"^(\d+)\s*(分钟|min)", s, re.I)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)\s*(小时|hour)", s, re.I)
    if m:
        return int(m.group(1)) * 60
    m = re.match(r"^(\d+)\s*(日|天|day)", s, re.I)
    if m:
        return int(m.group(1)) * 1440
    return 999999


def _sync_save_news(items: list[dict]):
    """Save news items to DB synchronously using sqlite3 (no asyncio needed)."""
    import sqlite3
    from datetime import datetime, timedelta
    from backend.data.db import DB_PATH

    now_bj = datetime.now(BEIJING_TZ)
    fetched_at = now_bj.isoformat()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            for item in items:
                mins = _time_ago_minutes(item.get("time_ago", ""))
                pub_ts = now_bj - timedelta(minutes=mins)
                conn.execute("""
                    INSERT INTO news_items (title, title_en, source, url, direction, time_ago, published_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title=excluded.title, title_en=excluded.title_en,
                        direction=excluded.direction, time_ago=excluded.time_ago,
                        fetched_at=excluded.fetched_at
                """, (
                    item.get("title", ""), item.get("title_en", ""),
                    item.get("source", ""), item.get("url", ""),
                    item.get("direction", "neutral"), item.get("time_ago", ""),
                    pub_ts.isoformat(), fetched_at,
                ))
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to save news to DB: {e}")


# News cache
_news_cache: list[dict] = []
_news_timestamp: float = 0.0
_NEWS_TTL = 300  # 5 minutes


def fetch_news() -> list[dict]:
    """Scrape related news from Google Finance GCW00:COMEX page."""
    global _news_cache, _news_timestamp
    now = time.time()
    if _news_cache and (now - _news_timestamp) < _NEWS_TTL:
        return sorted(_news_cache, key=lambda x: _time_ago_minutes(x["time_ago"]))

    def _scrape_sync():
        import os as _os
        if not _os.path.exists(CHROME_PATH):
            logger.warning(f"Chrome not found at {CHROME_PATH}, skipping news scrape")
            return []
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page()
            page.goto(
                "https://www.google.com/finance/quote/GCW00:COMEX?comparison=USD-CNY",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            page.wait_for_timeout(10000)
            links = page.query_selector_all("a[href]")

            news = []
            seen_titles = set()
            for el in links:
                href = el.get_attribute("href")
                text = el.inner_text()
                if not text or len(text) < 20:
                    continue
                if not href or href.startswith("/") or href.startswith("?"):
                    continue

                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if not lines:
                    continue

                source = lines[0]
                time_ago = ""
                for line in lines[1:]:
                    if re.match(r"^\d+\s*(分钟|小时|日|minutes?|hours?|days?)\s*(前|ago)$", line, re.I):
                        time_ago = line
                        break

                if not time_ago:
                    continue

                skip = len(lines) > 2
                title_parts = re.split(r"\n+", text)
                title_text = " ".join(title_parts[1:]) if skip else text
                title_text = re.sub(r"\s+", " ", title_text).strip()
                title_text = re.sub(
                    r"^\d+\s*(分钟|小时|日|minutes?|hours?|days?)\s*(前|ago)\s+",
                    "", title_text, flags=re.I,
                ).strip()
                if title_text in seen_titles:
                    continue
                seen_titles.add(title_text)

                title_cn = _translate(title_text)
                direction = _gold_direction(title_text)

                news.append({
                    "source": source,
                    "title_en": title_text,
                    "title": title_cn,
                    "url": href,
                    "time_ago": time_ago,
                    "direction": direction,
                })
                if len(news) >= 10:
                    break

            browser.close()
            return news

    try:
        parsed = _scrape_sync()
        if parsed:
            parsed.sort(key=lambda x: _time_ago_minutes(x["time_ago"]))
        _news_cache = parsed if parsed else []
        _news_timestamp = now

        if _news_cache:
            import threading
            threading.Thread(target=_sync_save_news, args=(_news_cache,), daemon=True).start()

        return _news_cache
    except Exception as e:
        logger.warning(f"News scrape error: {e}")
        return _news_cache if _news_cache else []


# ---- Translation via Ollama + MyMemory fallback ----
def _translate(text: str) -> str:
    """Translate English to Chinese via local Ollama translategemma model, fallback to MyMemory."""
    if not text:
        return ""
    try:
        prompt = (
            "Translate the following English text to Chinese (Simplified). "
            "Output only the Chinese translation:\n\n" + text[:500]
        )
        resp = requests.post(
            _OLLAMA_URL,
            json={"model": _OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        result = resp.json()
        translated = result.get("response", "").strip()
        if "\n" in translated:
            translated = translated.split("\n")[0].strip()
        if not any("\u4e00" <= c <= "\u9fff" for c in translated):
            return _translate_mymemory(text)
        return translated
    except Exception as e:
        logger.warning(f"Ollama translation error: {e}")
    return _translate_mymemory(text)


def _translate_mymemory(text: str) -> str:
    """Fallback MyMemory translation."""
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text[:500])}&langpair=en|zh-CN"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated and translated != text:
            return translated
    except Exception:
        pass
    return text


# ---- Sentiment: gold price direction ----
_GOLD_UP_KW = [
    "surge", "rises", "rising", "rally", "rallying", "gain", "gains",
    "climb", "climbs", "climbing", "soar", "soars", "soaring",
    "bullish", "safe haven", "inflation", "war", "conflict",
    "demand", "high", "record high", "peak", "strong demand",
]
_GOLD_DN_KW = [
    "plunge", "plunges", "plunging", "drop", "drops", "dropped",
    "fall", "falls", "falling", "fell",
    "decline", "declines", "declining",
    "tumble", "tumbling", "bearish", "victory", "tariff",
    "sell-off", "correction", "profit taking",
]


def _gold_direction(title_en: str) -> str:
    """Return 'up' | 'down' | 'neutral' based on English headline keywords."""
    lower = title_en.lower()

    clear_up = any(kw in lower for kw in [
        "surge", "rises", "rising", "rally", "rallying", "gain", "gains",
        "jump", "jumps", "jumped", "spike", "spikes", "spiked",
    ])
    clear_dn = any(kw in lower for kw in [
        "sink", "sinks", "sank",
        "plunge", "plunges", "plunging", "plummet", "plummets",
        "drop", "drops", "dropped",
        "fall", "falls", "fell", "falling",
        "tumble", "tumbling", "tumbled",
        "slip", "slips", "slipped",
    ])
    if clear_up and not clear_dn:
        return "up"
    if clear_dn and not clear_up:
        return "down"

    up_found = any(kw in lower for kw in [
        "bullish", "safe haven", "war", "conflict", "record high", "peak",
        "strong demand", "us-china", "trade war", "tariff",
    ])
    dn_found = any(kw in lower for kw in [
        "bearish", "victory", "sell-off", "correction",
        "profit taking", "dollar strength",
    ])
    if up_found and not dn_found:
        return "up"
    if dn_found and not up_found:
        return "down"

    return "neutral"
