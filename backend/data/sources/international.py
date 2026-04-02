"""GCW00:COMEX (COMEX gold futures) and USD/CNY via yfinance SDK.

International gold: yfinance Ticker("GC=F") — COMEX 黄金期货主力合约
USD/CNY:           yfinance Ticker("CNY=X") — 离岸人民币汇率

All functions are synchronous with their own cache.
"""
import re
import logging
import time
import asyncio
import json
import requests
import urllib.parse
from datetime import datetime, timezone, timedelta

import yfinance as yf
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BEIJING_TZ = timezone(timedelta(hours=8))

_xau_cache = {"data": None, "timestamp": 0.0}
_usdcny_cache = {"data": None, "timestamp": 0.0}
_TTL = 60  # 1 minute


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
        pct = round((change / float(prev["Close"])) * 100, 4) if prev["Close"] else 0

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


def fetch_xauusd_history(days: int = 90):
    """Fetch GC=F OHLCV history via yfinance using start/end to get exact range."""
    try:
        ticker = yf.Ticker("GC=F")
        now = datetime.utcnow()

        if days <= 1:
            # Exact 24h × 5-min bars
            start = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            end = (now + timedelta(hours=1)).strftime("%Y-%m-%d")
            data = ticker.history(start=start, end=end, interval="5m", auto_adjust=True)
        elif days <= 5:
            # Exact days × 15-min bars
            start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
            end = (now + timedelta(hours=1)).strftime("%Y-%m-%d")
            data = ticker.history(start=start, end=end, interval="15m", auto_adjust=True)
        else:
            # Daily bars for longer range
            start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
            end = (now + timedelta(hours=1)).strftime("%Y-%m-%d")
            data = ticker.history(start=start, end=end, interval="1d", auto_adjust=True)

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
                "volume": int(row["Volume"]),
            })
        return records
    except Exception as e:
        logger.warning(f"yfinance history error: {e}")
        return None


def _time_ago_minutes(ago: str) -> int:
    """Parse '5小时前' / '3 hours ago' → minutes for sorting (smaller = newer)."""
    m = re.match(r"^(\d+)\s*(分钟|min)", ago, re.I)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)\s*(小时|hour)", ago, re.I)
    if m:
        return int(m.group(1)) * 60
    m = re.match(r"^(\d+)\s*(日|天|day)", ago, re.I)
    if m:
        return int(m.group(1)) * 1440
    return 999999


def _sync_save_news(items: list[dict]):
    """Save news items to DB synchronously using sqlite3 (no asyncio needed)."""
    import sqlite3
    from datetime import datetime, timedelta
    # Import DB_PATH from db.py (no circular: db.py does not import international.py)
    from backend.data.db import DB_PATH

    now_utc = datetime.utcnow()
    fetched_at = now_utc.isoformat()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            for item in items:
                mins = _time_ago_minutes(item.get("time_ago", ""))
                pub_ts = now_utc - timedelta(minutes=mins)
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
        """Scrape news synchronously using sync Playwright API."""
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
                title_text = re.sub(r"^\d+\s*(分钟|小时|日|minutes?|hours?|days?)\s*(前|ago)\s+", "", title_text, flags=re.I).strip()
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

        # Persist to DB (run sync function in thread pool, no asyncio needed)
        if _news_cache:
            import threading
            threading.Thread(target=_sync_save_news, args=(_news_cache,), daemon=True).start()

        return _news_cache
    except Exception as e:
        logger.warning(f"News scrape error: {e}")
        return _news_cache if _news_cache else []


# ---- Translation ----
def _translate(text: str) -> str:
    """Translate English text to Chinese via MyMemory (free, no key)."""
    if not text:
        return ""
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text[:500])}&langpair=en|zh-CN"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated and translated != text:
            return translated
    except Exception:
        pass
    return text  # fallback: return original


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

    # Clear directional verbs — highest priority, always win
    clear_up = any(kw in lower for kw in [
        "surge", "rises", "rising", "rally", "rallying", "gain", "gains",
        "gain", "climb", "climbs", "climbing", "soar", "soars", "soaring",
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

    # Secondary signals — both directions present = neutral
    up_found = any(kw in lower for kw in [
        "bullish", "safe haven", "war", "conflict", "record high", "peak",
        "strong demand", "us-China", "trade war",
    ])
    dn_found = any(kw in lower for kw in [
        "bearish", "victory", "tariff", "sell-off", "correction",
        "profit taking", "dollar strength",
    ])
    if up_found and not dn_found:
        return "up"
    if dn_found and not up_found:
        return "down"

    # Remove vague/misleading keywords: inflation, high, low, demand alone are too ambiguous
    return "neutral"
