"""BitcoinWorld gold news via HTML search page: https://bitcoinworld.co.in/?s=gold"""
import logging
import re
import time
from datetime import datetime, timezone, timedelta

import httpx

from backend.data.sources.news_evaluation import _sync_save_processed_news

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 300  # 5 minutes
_cache: list[dict] = []
_cache_ts: float = 0.0

# Gold keywords — article title must contain at least one of these (word-boundary matched)
GOLD_KEYWORDS = [
    "gold price", "gold prices", "gold etf", "gold etfs",
    "gold forecast", "gold trading", "gold market", "gold futures",
    "gold outlook", "gold analysis", "gold demand", "gold supply",
    "gold rally", "gold sector", "gold stocks", "gold bullion",
    "gold investor", "gold investment", "gold steadies",
    "gold retreats", "gold demand", "xau", "bullion",
    "precious metal", "gold surge", "gold falls", "gold plummets",
    "gold stead",  # matches "gold steadies", "gold stability", etc.
    "silver",  # gold + silver often together
]

# Exclude articles that are purely Bitcoin/crypto with gold as peripheral mention
_EXCLUDE = [
    "bitcoin triumph", "bitcoin wins", "bitcoin investment",
    "bitcoin reclaim", "bitcoin investors",
    "solana price", "cryptocurrency trends",
    "anthropic", "tokenized asset", "michael saylor",
]


def _html_unescape(text: str) -> str:
    """Decode common HTML entities."""
    replacements = {
        "&amp;": "&",
        "&#8217;": "'",
        "&#8216;": "'",
        "&#8220;": '"',
        "&#8221;": '"',
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#039;": "'",
        "&hellip;": "...",
    }
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    return text


def _is_gold_article(title: str) -> bool:
    """Filter: include articles where gold is a primary topic."""
    t = title.lower()
    if not any(re.search(r'\b' + re.escape(kw.lower()) + r'\b', t) for kw in GOLD_KEYWORDS):
        return False
    if any(kw in t for kw in _EXCLUDE):
        return False
    return True


def _parse_og_time(html: str) -> datetime | None:
    """Extract og:published_time from article HTML."""
    m = re.search(r'"article:published_time"\s+content="([^"]+)"', html)
    if not m:
        return None
    try:
        # Parse ISO 8601: "2026-04-03T16:30:11+05:30"
        s = m.group(1).replace("+05:30", "+0530")
        # Convert IST (+05:30) to Beijing time (+08:00), i.e. +3 hours
        naive = datetime.fromisoformat(s)
        # IST offset is +05:30, Beijing is +08:00, diff = +02:30
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        aware = naive.replace(tzinfo=ist_tz)
        return aware.astimezone(BEIJING_TZ)
    except Exception:
        return None


def _fetch_article_time(url: str) -> datetime | None:
    """Fetch a single article page and extract publish time."""
    try:
        resp = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            },
            timeout=10,
            verify=False,
        )
        return _parse_og_time(resp.text)
    except Exception:
        return None


def _sync_save_news(items: list[dict], hour_range: str = ""):
    """Save news items to DB synchronously with AI evaluation."""
    _sync_save_processed_news(items, hour_range)


def fetch_bitcoinworld_gold_news() -> list[dict]:
    """Fetch gold news from BitcoinWorld HTML search page, returns normalized items.

    This uses HTML scraping instead of RSS to get more comprehensive results
    (RSS only covers a subset of gold articles on the site).
    """
    global _cache, _cache_ts
    import time
    now_ts = time.time()
    if _cache and (now_ts - _cache_ts) < _TTL:
        return _cache

    try:
        resp = httpx.get(
            "https://bitcoinworld.co.in/",
            params={"s": "gold"},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            },
            timeout=15,
            verify=False,
        )
        html = resp.text
    except Exception as e:
        logger.warning(f"BitcoinWorld HTML fetch error: {e}")
        _cache = []
        _cache_ts = now_ts
        return []

    # Extract all article title+URL from search page
    raw_articles = re.findall(
        r'<h2 class="entry-title[^"]*"[^>]*><a href="([^"]+)"[^>]*>(.*?)</a></h2>',
        html,
    )

    gold_articles = []
    for url, raw_title in raw_articles:
        title = _html_unescape(re.sub(r'<[^>]+>', '', raw_title).strip())
        if _is_gold_article(title):
            gold_articles.append({"title": title, "url": url})

    if not gold_articles:
        _cache = []
        _cache_ts = now_ts
        return []

    # Fetch publish time for each article (parallel, via sync httpx in thread pool)
    def fetch_times():
        results = {}
        for article in gold_articles:
            dt = _fetch_article_time(article["url"])
            results[article["url"]] = dt or datetime.now(BEIJING_TZ)
        return results

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        future = ex.submit(fetch_times)
        times = future.result()

    items = []
    now_bj = datetime.now(BEIJING_TZ)
    for article in gold_articles:
        pub_dt = times[article["url"]]
        items.append({
            "source": "BitcoinWorld",
            "title_en": article["title"],
            "title": article["title"],
            "url": article["url"],
            "published": pub_dt.strftime("%Y-%m-%d %H:%M"),
            "time_ago": pub_dt.strftime("%Y-%m-%d"),
        })

    # Sort newest first
    items.sort(key=lambda x: x["published"], reverse=True)

    _cache = items
    _cache_ts = now_ts
    logger.info(f"BitcoinWorld fetched {len(items)} gold news items from HTML search")
    return items


# Alias for pluggable interface
fetch_news = fetch_bitcoinworld_gold_news
