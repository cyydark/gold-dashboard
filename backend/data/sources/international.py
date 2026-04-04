"""国际金价 + USD/CNY 汇率 via Binance + er-api.

XAU/USD: Binance XAUT/USDT (24/7)
USD/CNY: er-api

Historical K线: Binance klines
News: 富途牛牛直接API (backend/data/sources/futu.py)
"""
import os
import re
import logging
import time
import json
import requests
import feedparser
import httpx
import yaml
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

import yfinance as yf

logger = logging.getLogger(__name__)

RSSHUB_BASE = os.environ.get("RSSHUB_BASE_URL", "http://localhost:11200")
SOURCES_FILE = Path(__file__).parent.parent.parent.parent / "sources.yaml"
BEIJING_TZ = timezone(timedelta(hours=8))

_xau_cache = {"data": None, "timestamp": 0.0}
_usdcny_cache = {"data": None, "timestamp": 0.0}
_gf_history_cache: dict[int, dict] = {}  # {window: {"data": records, "timestamp": float}}
_TTL = 60  # 1 minute
_GF_HISTORY_TTL = 300  # 5 minutes

def _fetch_json(url: str) -> dict | None:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Fetch error {url}: {e}")
        return None

def fetch_xauusd() -> dict | None:
    """Get XAU/USD price from Binance XAUT/USDT, with 60s cache."""
    now = time.time()
    if _xau_cache["data"] is not None and (now - _xau_cache["timestamp"]) < _TTL:
        return _xau_cache["data"]

    data = _fetch_json("https://www.binance.com/api/v3/ticker/24hr?symbol=XAUTUSDT")
    if not data or not data.get("lastPrice"):
        if _xau_cache["data"] is not None:
            return _xau_cache["data"]
        return None

    last = float(data["lastPrice"])
    open_px = float(data.get("openPrice", last))
    xau = {
        "symbol": "XAUUSD",
        "name": "国际黄金 XAU/USD",
        "price": round(last, 2),
        "change": round(last - open_px, 2),
        "pct": round(float(data.get("priceChangePercent", 0)), 2),
        "open": round(open_px, 2),
        "high": round(float(data["highPrice"]), 2),
        "low": round(float(data["lowPrice"]), 2),
        "unit": "USD/oz",
        "updated_at": datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }
    _xau_cache["data"] = xau
    _xau_cache["timestamp"] = now
    return xau

def fetch_usdcny() -> dict | None:
    """Get USD/CNY rate from er-api, with 60s cache."""
    now = time.time()
    if _usdcny_cache["data"] is not None and (now - _usdcny_cache["timestamp"]) < _TTL:
        return _usdcny_cache["data"]

    data = _fetch_json("https://open.er-api.com/v6/latest/USD")
    if not data:
        if _usdcny_cache["data"] is not None:
            return _usdcny_cache["data"]
        return None

    rate = float(data["rates"]["CNY"])
    cny = {
        "symbol": "USDCNY",
        "name": "美元兑人民币 USD/CNY",
        "price": round(rate, 4),
        "change": 0,
        "pct": 0,
        "unit": "CNY/USD",
        "updated_at": datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }
    _usdcny_cache["data"] = cny
    _usdcny_cache["timestamp"] = now
    return cny

# ---------------------------------------------------------------------------
def fetch_xauusd_history(days: int = 5) -> list[dict] | None:
    """Fetch XAUUSD OHLCV via Binance 5m klines.

    Binance returns max 1000 bars per request. 5m × 1000 ≈ 3.5 days.
    """
    try:
        resp = requests.get(
            "https://www.binance.com/api/v3/klines?symbol=XAUTUSDT&interval=5m&limit=1000",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        klines = resp.json()
    except Exception as e:
        logger.warning(f"Binance klines error: {e}")
        return None

    records = []
    for k in klines:
        ts_s = int(k[0]) // 1000
        records.append({
            "time": ts_s,
            "open":  round(float(k[1]), 2),
            "high":  round(float(k[2]), 2),
            "low":   round(float(k[3]), 2),
            "close": round(float(k[4]), 2),
            "volume": 0,
        })
    return records if records else None

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

def _sync_save_news(items: list[dict], hour_range: str = ""):
    """Save news items to DB synchronously using sqlite3 (no asyncio needed)."""
    import sqlite3
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timedelta
    from backend.data.db import DB_PATH

    now_bj = datetime.now(BEIJING_TZ)
    fetched_at = now_bj.isoformat()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            for item in items:
                published_raw = item.get("published", "")
                pub_ts = None
                try:
                    pub_dt = datetime.strptime(published_raw[:16], "%Y-%m-%d %H:%M")
                    pub_ts = pub_dt.replace(tzinfo=BEIJING_TZ)
                except Exception:
                    try:
                        pub_ts = parsedate_to_datetime(published_raw).astimezone(BEIJING_TZ)
                    except Exception:
                        pass
                if pub_ts is None:
                    pub_ts = now_bj - timedelta(minutes=_time_ago_minutes(item.get("time_ago", "")))

                conn.execute("""
                    INSERT INTO news_items (title, title_en, source, url, direction, time_ago, published_at, fetched_at, hour_range)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title=excluded.title, title_en=excluded.title_en,
                        direction=excluded.direction, time_ago=excluded.time_ago,
                        published_at=excluded.published_at, fetched_at=excluded.fetched_at,
                        hour_range=excluded.hour_range
                """, (
                    item.get("title", ""), item.get("title_en", ""),
                    item.get("source", ""), item.get("url", ""),
                    item.get("direction", "neutral"), item.get("time_ago", ""),
                    pub_ts.isoformat(), fetched_at, hour_range,
                ))
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to save news to DB: {e}")

# News cache
_news_cache: list[dict] = []
_news_timestamp: float = 0.0
_NEWS_TTL = 300  # 5 minutes

def fetch_news() -> list[dict]:
    """Fetch gold-related news from RSS feeds defined in sources.yaml."""
    global _news_cache, _news_timestamp
    now = time.time()
    if _news_cache and (now - _news_timestamp) < _NEWS_TTL:
        return _news_cache

    if not SOURCES_FILE.exists():
        logger.warning(f"sources.yaml not found at {SOURCES_FILE}, returning empty news list")
        _news_cache = []
        _news_timestamp = now
        return []

    try:
        with open(SOURCES_FILE) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to read sources.yaml: {e}")
        _news_cache = []
        _news_timestamp = now
        return []

    all_news: list[dict] = []

    for src in config.get("sources", []):
        if not src.get("enabled", True):
            continue
        url = src["url"].replace("http://192.168.2.200:11200", RSSHUB_BASE)
        keywords = src.get("keywords", [])
        src_name = src.get("name", "未知来源")
        try:
            resp = httpx.get(url, timeout=15, verify=False)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:100]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                link = entry.get("link", "")
                published = ""
                # Parse RSS date: feedparser returns GMT struct_time, convert to Beijing
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_dt = parsedate_to_datetime(entry.published).astimezone(BEIJING_TZ)
                        published = pub_dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        published = entry.get("published", "")
                else:
                    raw = entry.get("published", "") or entry.get("updated", "")
                    # Try parsing directly as Beijing time
                    try:
                        pub_dt = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
                        published = pub_dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        published = raw

                # time_ago for sorting
                mins = _time_ago_minutes(published)
                time_ago = published  # store as-is for display

                all_news.append({
                    "source": src_name,
                    "title_en": title,
                    "title": title,
                    "url": link,
                    "published": published,
                    "time_ago": time_ago,
                    "direction": _gold_direction(title),
                })
        except Exception as e:
            logger.warning(f"RSS fetch error for {src_name}: {e}")

    # Futu direct API
    try:
        from backend.data.sources.futu import fetch_futu_news
        futu_news = fetch_futu_news()
        all_news.extend(futu_news)
    except Exception as e:
        logger.warning(f"Futu news fetch error: {e}")

                # Sort newest first — entries already reverse-chronological from RSS; skip sort
    _news_cache = all_news
    _news_timestamp = now

    if _news_cache:
        import threading
        threading.Thread(target=_sync_save_news, args=(_news_cache,), daemon=True).start()

    return _news_cache

# ---- Sentiment: gold price direction ----
# Word-boundary patterns for precise matching
_CLEAR_UP_RE = re.compile(
    r'\b(surge[sd]?|rises?|rising|rally(?:ing|ed|s)?|gain(?:ed|ing)?|'
    r'gains(?= (?:on|in|of|to|as|despite|amid|after|because|while|when|if|with|amid))|'
    r'jump(?:ed|s)?|spike[sd]?|climb(?:ing|s|ed)?|soar(?:ing|s|ed)?)\b',
    re.IGNORECASE,
)
_CLEAR_DN_RE = re.compile(
    r'\b(sank|sink(?:s|ing)?|plunge[sd]?|plummet(?:ed|s|ing)?|'
    r'drop(?:ped|s)?|fell|fall(?:s|ing|ed)?|'
    r'tumble[sd]?|slip(?:ped|s|ping)?|'
    r'retreat(?:s|ing)?|retrace[sd]?|pull(?:s|ing)? ?back|'
    r'recede[sd]?|\berase\b|erases|erasing|erased|'
    r'capitulat(?:es|ing|ed)?)\b',
    re.IGNORECASE,
)
_GIVING_UP_RE = re.compile(
    r'\b(giving up|gives up|give up)(?:[\s]+(?:gains?|intraday|all|its|hopes?|reserves?)|$)',
    re.IGNORECASE,
)

def _gold_direction(title_en: str) -> str:
    """Return 'up' | 'down' | 'neutral' based on English headline keywords."""
    lower = title_en.lower()

    # "giving up" is always down; if "gains" also fires, down wins
    giving_up = bool(_GIVING_UP_RE.search(lower))

    clear_up = bool(_CLEAR_UP_RE.search(lower))
    clear_dn = bool(_CLEAR_DN_RE.search(lower)) or giving_up
    if clear_up and not clear_dn:
        return "up"
    if clear_dn and not clear_up:
        return "down"

    up_found = any(kw in lower for kw in [
        "bullish", "safe haven", "war", "conflict", "record high",
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
