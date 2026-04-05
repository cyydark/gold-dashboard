"""BernamaBiz gold futures news via search page scraping."""
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta

import httpx

from backend.data.db import DB_PATH

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 300  # 5 minutes
_cache: list[dict] = []
_cache_ts: float = 0.0


def _parse_relative_time(time_str: str) -> datetime:
    """Parse '1d ago' / '2h ago' → datetime (Beijing time, approximate)."""
    now = datetime.now(BEIJING_TZ)
    m = re.match(r"(\d+)\s*(hour|day|minute|d|h|m)a?\s*ago", time_str.strip())
    if not m:
        return now
    val: int = int(m.group(1))
    unit: str = m.group(2)[0].lower()
    if unit == "d":
        return now - timedelta(days=val)
    if unit == "h":
        return now - timedelta(hours=val)
    return now - timedelta(minutes=val)


def _parse_absolute_date(text: str, default: datetime) -> datetime:
    """Extract 'April 4' / 'March 31' from article text → datetime (current year)."""
    m = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\b", text)
    if not m:
        return default
    try:
        month_name, day = m.group(1), int(m.group(2))
        year = default.year
        dt = datetime(year, datetime.strptime(month_name, "%B").month, day)
        return dt.replace(tzinfo=BEIJING_TZ)
    except ValueError:
        return default


def _sync_save_news(items: list[dict], hour_range: str = ""):
    """Save news items to DB synchronously."""
    if not items:
        return
    now_bj = datetime.now(BEIJING_TZ)
    fetched_at = now_bj.isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            for item in items:
                pub = item.get("published", "")
                pub_ts = None
                if pub:
                    try:
                        pub_dt = datetime.strptime(pub[:16], "%Y-%m-%d %H:%M")
                        pub_ts = pub_dt.replace(tzinfo=BEIJING_TZ).isoformat()
                    except Exception:
                        pass
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
                    pub_ts or pub or fetched_at, fetched_at, hour_range,
                ))
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to save Bernama news to DB: {e}")


def fetch_bernama_gold_news() -> list[dict]:
    """Scrape gold news from bernamabiz.com search page, returns normalized items."""
    global _cache, _cache_ts
    now = time.time()
    if _cache and (now - _cache_ts) < _TTL:
        return _cache

    try:
        resp = httpx.get(
            "https://www.bernamabiz.com/search.php",
            params={"terms": "gold"},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "en",
            },
            timeout=15,
            verify=False,
        )
        html = resp.text
    except Exception as e:
        logger.warning(f"BernamaBiz fetch error: {e}")
        _cache = []
        _cache_ts = now
        return []

    items = []
    blocks = re.split(r'<div class="d-md-flex post-entry-2 small-img">', html)

    for block in blocks[1:]:  # skip header
        id_m = re.search(r'news\.php\?id=(\d+)', block)
        time_m = re.search(r'<div class="post-meta"><span>([^<]+)</span></div>', block)
        title_m = re.search(r'<h3><a href="news\.php\?id=\d+">([^<]+)</a></h3>', block)

        if not (id_m and title_m):
            continue

        news_id = id_m.group(1)
        title = title_m.group(1).strip()
        time_str = time_m.group(1).strip() if time_m else ""

        # Parse relative time → base datetime
        pub_dt = _parse_relative_time(time_str)
        # Refine with absolute date from article text (e.g. "April 4")
        pub_dt = _parse_absolute_date(block, pub_dt)

        items.append({
            "source": "BERNAMA",
            "title_en": title,
            "title": title,
            "url": f"https://www.bernamabiz.com/news.php?id={news_id}",
            "published": pub_dt.strftime("%Y-%m-%d %H:%M"),
            "time_ago": time_str,
            "direction": "neutral",
        })

    _cache = items
    _cache_ts = now
    logger.info(f"BernamaBiz fetched {len(items)} gold news items")
    return items
