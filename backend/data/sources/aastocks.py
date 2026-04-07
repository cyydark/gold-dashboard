"""AAStocks AAFN gold news via search page + getmorenews.ashx pagination API."""
import html
import logging
import re
import time
from datetime import datetime, timezone, timedelta

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_TTL = 300  # 5 minutes
_MAX_PAGES = 200  # pagination cap
_cache: list[dict] = []
_cache_ts: float = 0.0

# Broad gold market filter: any title mentioning gold/silver, or gold market actors
BROAD_GOLD_KEYWORDS = [
    "gold", "xau", "xauusd", "silver", "bullion", "precious metal",
    "goldman sachs", "goldman", "gold futures", "gold etf",
    "gold rally", "gold surge", "gold falls", "gold drop", "gold retreat",
    "commodity markets", "commodity price",
]
EXCLUDE_KEYWORDS = [
    "bitcoin", "cryptocurrency", "tesla deliveries", "apple iphone",
    "chinese restaurant", "kimchi",
]


def _is_gold_article(title: str) -> bool:
    t = title.lower()
    if any(kw in t for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw in t for kw in BROAD_GOLD_KEYWORDS)


def _parse_dt(dt_str: str) -> datetime:
    try:
        return datetime.strptime(dt_str.strip(), "%Y/%m/%d %H:%M").replace(tzinfo=BEIJING_TZ)
    except ValueError:
        return datetime.now(BEIJING_TZ)


def _fetch_initial_page() -> tuple[list[dict], str, str]:
    """Fetch SSR search page to extract pagination cursor only.

    SSR items have no reliable publish date without heavy HTML parsing.
    We skip SSR items and rely on the getmorenews.ashx API for dated items.

    Returns ([], last_news_id, last_newstime).
    """
    try:
        resp = httpx.get(
            "http://www.aastocks.com/en/usq/news/search.aspx",
            params={"catg": "1", "key": "gold"},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "en",
            },
            timeout=15,
            verify=False,
            follow_redirects=True,
        )
        html_text = resp.text
    except Exception as e:
        logger.warning(f"AAStocks SSR fetch error: {e}")
        return [], "", ""

    # Extract pagination cursor from JS vars in raw HTML
    m_id = re.search(r"sLastNewsID\s*=\s*'([^']+)'", html_text)
    m_time = re.search(r"sLastNewsTime\s*=\s*'([^']+)'", html_text)
    last_id = m_id.group(1) if m_id else ""
    last_time = m_time.group(1) if m_time else ""
    return [], last_id, last_time


def _fetch_more_news(news_id: str, newstime: str) -> tuple[list[dict], str, str]:
    """Call getmorenews.ashx API, returns (items, next_newsid, next_newstime).

    Returns ([], "", "") when no more data.
    """
    try:
        resp = httpx.get(
            "http://www.aastocks.com/en/resources/datafeed/getmorenews.ashx",
            params={
                "cat": "us-latest",
                "newstime": newstime,
                "newsid": news_id,
                "period": "",
                "key": "gold",
                "cur": "",
                "newsrev": "1",
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Referer": "http://www.aastocks.com/en/usq/news/search.aspx?catg=1&key=gold",
            },
            timeout=15,
            verify=False,
        )
        text = resp.text.strip()
        # "1" or "2" → no more items
        if text in ("1", "2"):
            return [], "", ""
        data = resp.json()
    except Exception as e:
        logger.warning(f"AAStocks getmorenews API error: {e}")
        return [], "", ""

    items = []
    next_id = ""
    next_time = ""
    for n in data:
        title_raw = html.unescape((n.get("h") or "").strip())
        if not _is_gold_article(title_raw):
            continue
        dt_str = n.get("dt", "")
        pub_dt = _parse_dt(dt_str) if dt_str else datetime.now(BEIJING_TZ)
        source = n.get("s", "AAFN")
        nid = n.get("id", "")
        dtd = n.get("dtd", "")
        items.append({
            "title": title_raw,
            "title_en": title_raw,
            "source": f"AASTOCKS-{source}" if source != "AAFN" else "AASTOCKS",
            "url": f"https://www.aastocks.com/en/usq/news/comment.aspx?source={source}&id={nid}&catg=1",
            "published": pub_dt.strftime("%Y-%m-%d %H:%M"),
            "published_ts": int(pub_dt.timestamp()),
        })
        # Advance cursor to the oldest (last) item
        next_id = nid
        next_time = dtd

    return items, next_id, next_time


def fetch_aastocks_news() -> list[dict]:
    """Fetch gold news from AAStocks: SSR first page + paginated API.

    SSR returns ~10 items without dates; API pagination returns dated items.
    """
    global _cache, _cache_ts
    now_ts = time.time()
    if _cache and (now_ts - _cache_ts) < _TTL:
        return _cache

    all_items: list[dict] = []
    seen_urls: set[str] = set()

    # Step 1: SSR first page
    ssr_items, last_id, last_time = _fetch_initial_page()
    for item in ssr_items:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            all_items.append(item)

    # Step 2: Cursor-based pagination via getmorenews.ashx
    for _ in range(_MAX_PAGES):
        if not last_id:
            break
        more_items, last_id, last_time = _fetch_more_news(last_id, last_time)
        if not more_items:
            break
        for item in more_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                all_items.append(item)

    # Sort newest first
    all_items.sort(key=lambda x: x.get("published", ""), reverse=True)

    _cache = all_items
    _cache_ts = now_ts
    logger.info(f"AAStocks: {len(all_items)} gold items fetched")
    return all_items


# Alias for pluggable interface
fetch_news = fetch_aastocks_news
