"""富途牛牛 7×24 实时资讯 via Futu News API."""
import logging
import sqlite3
import threading
import time
import httpx
from datetime import datetime, timezone, timedelta
from backend.data.db import DB_PATH

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 300  # 5 minutes
_cache: list[dict] = []
_cache_ts: float = 0.0


def _sync_save_news(items: list[dict], hour_range: str = ""):
    """Save news items to DB synchronously."""
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
        logger.warning(f"Failed to save news to DB: {e}")


def fetch_futu_news(page_size: int = 50) -> list[dict]:
    """Fetch news from Futu API, returns normalized news items."""
    global _cache, _cache_ts
    now = time.time()
    if _cache and (now - _cache_ts) < _TTL:
        return _cache

    try:
        resp = httpx.get(
            "https://news.futunn.com/news-site-api/main/get-flash-list",
            params={"pageSize": page_size},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": "https://news.futunn.com/hk/main/live",
            },
            timeout=15,
            verify=False,
        )
        json_data = resp.json()
        news_list = (
            json_data
            .get("data", {})
            .get("data", {})
            .get("news", [])
        )
    except Exception as e:
        logger.warning(f"Futu API fetch error: {e}")
        _cache = []
        _cache_ts = now
        return []

    items = []
    for n in news_list:
        ts = n.get("time", "")
        pub_ts = int(ts) if ts.isdigit() else None
        pub_date = (
            datetime.fromtimestamp(pub_ts, BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
            if pub_ts else ""
        )
        content = n.get("content", "").strip()
        title = content[:80] if content else ""
        detail_url = n.get("detailUrl", "")
        full_text = content
        items.append({
            "source": "富途牛牛",
            "title_en": title,
            "title": title,
            "url": detail_url,
            "published": pub_date,
            "time_ago": pub_date,
            "direction": "neutral",
        })

    _cache = items
    _cache_ts = now
    return items
