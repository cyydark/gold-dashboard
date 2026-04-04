"""富途牛牛 7×24 实时资讯 via Futu News API."""
import logging
import time
import httpx
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 300  # 5 minutes
_cache: list[dict] = []
_cache_ts: float = 0.0


def _gold_direction(text: str) -> str:
    """Return 'up' | 'down' | 'neutral' based on Chinese/English keywords."""
    up_kw = [
        "上涨", "攀升", "飙升", "大涨", "创新高", "避险", "冲突", "战争",
        "美以", "空袭", "导弹", "制裁", "降息", "黄金需求",
        "surge", "rises", "rally", "spike", "soar",
    ]
    dn_kw = [
        "下跌", "回落", "大跌", "暴跌", "回调", "获利了结", "美元走强",
        "升值", "抛售",
        "drop", "fell", "plunge", "tumble",
    ]
    t = text.lower()
    up = any(k in t for k in up_kw)
    dn = any(k in t for k in dn_kw)
    if up and not dn:
        return "up"
    if dn and not up:
        return "down"
    return "neutral"


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
            "direction": _gold_direction(full_text),
        })

    _cache = items
    _cache_ts = now
    return items
