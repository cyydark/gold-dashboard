"""News service — fetches from multiple sources, gold-only filtering, no DB."""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

# 集中式黄金关键词过滤 — 所有源统一过此关卡
GOLD_KEYWORDS_EN = [
    "gold", "xau", "xauusd", "silver", "bullion", "precious metal",
    "goldman sachs", "goldman", "gold futures", "gold etf",
    "gold rally", "gold surge", "gold falls", "gold drop",
]
GOLD_KEYWORDS_ZH = [
    "黄金", "金价", "金条", "金币", "金矿", "金饰", "金店",
    "国际金", "现货金", "期货金", "COMEX", "伦敦金",
    "XAU", "au9999", "au(t+d)", "央行购金", "购金潮", "白银",
]
EXCLUDE_KEYWORDS = [
    "bitcoin", "cryptocurrency", "tesla deliveries", "iphone", "apple",
    "women's sports", "wnba", "kimchi", "chinese restaurant",
]


def _is_gold_news(title: str) -> bool:
    """Return True if title is primarily about gold/silver."""
    t = title.lower()
    if any(kw.lower() in t for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw.lower() in t for kw in GOLD_KEYWORDS_EN) or \
           any(kw in title for kw in GOLD_KEYWORDS_ZH)


def get_news(days: int = 1) -> list:
    """Fetch news from all sources, filter by days and gold-only, sorted newest first."""
    items = _fetch_news_from_sources()
    items = _filter_by_days(items, days)
    items = _filter_gold_only(items)
    return items


def _filter_by_days(items: list, days: int) -> list:
    """Filter news items to those published within the last `days` days, sorted newest first."""
    if days <= 0:
        return _sort_news(items)
    cutoff = datetime.now(BEIJING_TZ) - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()
    filtered = [it for it in items if it.get("published_ts", 0) >= cutoff_ts]
    return _sort_news(filtered)


def _sort_news(items: list) -> list:
    """Sort news by published_ts descending (newest first)."""
    return sorted(items, key=lambda x: x.get("published_ts", 0), reverse=True)


def _filter_gold_only(items: list[dict]) -> list[dict]:
    """Centralized gold news filter — deduplicate by URL after filtering."""
    filtered = [it for it in items if _is_gold_news(it.get("title", ""))]
    seen: set = set()
    unique = []
    for it in filtered:
        url = it.get("url", "")
        if url and url in seen:
            continue
        seen.add(url)
        unique.append(it)
    logger.info(f"Gold filter: {len(items)} -> {len(unique)} (dropped {len(items)-len(unique)})")
    return unique


def _fetch_news_from_sources() -> list:
    """Fetch news from available news sources."""
    all_news: list = []
    fetchers = [
        _fetch_bernama,
        _fetch_futu,
        _fetch_aastocks,
        _fetch_cnbc,
        _fetch_local_news,
    ]
    for fn in fetchers:
        try:
            items = fn()
            if isinstance(items, list):
                all_news.extend(items)
        except Exception:
            pass
    return all_news


def _fetch_bernama() -> list:
    try:
        from backend.data.sources.bernama import fetch_bernama_gold_news
        return fetch_bernama_gold_news()
    except Exception:
        return []


def _fetch_futu() -> list:
    try:
        from backend.data.sources.futu import fetch_futu_news
        return fetch_futu_news()
    except Exception:
        return []


def _fetch_aastocks() -> list:
    try:
        from backend.data.sources.aastocks import fetch_aastocks_news
        return fetch_aastocks_news()
    except Exception:
        return []


def _fetch_cnbc() -> list:
    try:
        from backend.data.sources.cnbc import fetch_cnbc_news
        return fetch_cnbc_news()
    except Exception:
        return []


def _fetch_local_news() -> list:
    try:
        from backend.data.sources.local_news import fetch_local_news as _fetch
        return _fetch()
    except Exception:
        return []
