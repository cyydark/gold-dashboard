"""富途牛牛要闻 via SSR — https://news.futunn.com/zh/main

要闻（重要新闻）通过服务端渲染嵌入 HTML，不需要额外的 API 请求。
快讯（7×24 实时）通过 get-flash-list API 获取。

两个来源都会经过黄金关键词过滤。
"""
import html
import logging
import re
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Set

import httpx

from backend.data.sources.news_evaluation import _sync_save_processed_news

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

_TTL = 300  # 5 minutes
_cache: list[dict] = []
_cache_ts: float = 0.0
_save_done_event: concurrent.futures.Future | None = None

# 黄金相关关键词：标题必须包含，或正文出现 ≥2 次
# 白名单策略：只保留直接指向黄金的词，不含宏观/地缘词
GOLD_KEYWORDS = [
    # 纯金市词（强相关）
    "黄金", "金价", "金条", "金币", "金矿", "金饰", "金店",
    "国际金", "现货金", "期货金", "黄金期货", "COMEX", "伦敦金",
    "XAU", "au9999", "au(t+d)", "央行购金", "购金潮",
    "Gold", "gold", "XAUUSD", "Goldman Sachs",
    # 贵金属关联词
    "白银", "贵金属",
]


def _sync_save_news(items: list[dict], hour_range: str = ""):
    """Save news items to DB synchronously with AI evaluation."""
    _sync_save_processed_news(items, hour_range)


def fetch_and_save_news(hour_range: str = "") -> concurrent.futures.Future:
    """Fetch gold news and save to DB synchronously.

    Returns a Future whose result is the saved news list.
    Caller can call future.result() to wait for completion.
    """
    global _save_done_event

    def _do():
        items = fetch_futu_news()
        if items:
            _sync_save_news(items, hour_range)
        return items

    _save_done_event = ThreadPoolExecutor(max_workers=1).submit(_do)
    return _save_done_event


def _is_gold_news(title: str, content: str = "") -> bool:
    """Check if a news item is primarily about gold.

    Rules:
    - Title must contain gold keywords, OR
    - Content contains 2+ gold keyword mentions (not just one-off mention)
    This avoids articles about geopolitics/finance that mention gold once in passing.
    """
    gold_count = sum(content.lower().count(kw.lower()) for kw in GOLD_KEYWORDS)
    title_has_gold = any(kw.lower() in title.lower() for kw in GOLD_KEYWORDS)
    return title_has_gold or gold_count >= 2


def _parse_ssr_time(img_src: str, footer_time: str) -> tuple[str, str]:
    """Extract publish datetime from image URL date + footer time text.

    img_src contains date like: /20260405/...
    footer_time contains time like: "09:52" or "Apr 5"
    Returns (published, time_ago) in %Y-%m-%d %H:%M format.
    """
    today = datetime.now(BEIJING_TZ)

    # Extract date from image URL: .../20260405/...
    date_m = re.search(r'/(\d{4})(\d{2})(\d{2})/', img_src)
    if date_m:
        year, month, day = int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3))
    else:
        year, month, day = today.year, today.month, today.day

    # Parse time from footer
    time_text = footer_time.strip()
    hour, minute = 0, 0
    if time_text:
        hm = re.match(r'(\d{1,2}):(\d{2})', time_text)
        if hm:
            hour, minute = int(hm.group(1)), int(hm.group(2))

    pub_dt = datetime(year, month, day, hour, minute, tzinfo=BEIJING_TZ)
    return (
        pub_dt.strftime("%Y-%m-%d %H:%M"),
        pub_dt.strftime("%Y-%m-%d"),
    )


SSR_PAGES = [
    ("https://news.futunn.com/zh/main", "zh-CN"),
    ("https://news.futunn.com/main",    "en"),
]


def _fetch_ssr_articles(url: str, lang: str) -> list[dict]:
    """Fetch 要闻 (important news) from a Futu SSR page.

    The /zh/main and /main pages embed article list via server-side rendering (NUXT).
    Returns list of dicts: {url, title, source, published, time_ago}
    """
    try:
        resp = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": lang,
            },
            timeout=15,
            verify=False,
        )
        html_content = resp.text
    except Exception as e:
        logger.warning(f"Futu SSR fetch error ({url}): {e}")
        return []

    articles = []
    # Each article is in: <a class="market-item list-item" href="URL">...<img alt="TITLE">...</a>
    # Extract URL, title, source, time from each block
    for block_m in re.finditer(
        r'<a\b([^>]+class="[^"]*market-item[^"]*"[^>]*)>(.*?)</a>',
        html_content, re.DOTALL
    ):
        open_attrs = block_m.group(1)
        content = block_m.group(2)

        # URL
        url_m = re.search(r'href="([^"]+)"', open_attrs)
        if not url_m:
            continue
        article_url = url_m.group(1).strip()

        # Title from img alt attribute (most reliable)
        title_m = re.search(r'<img[^>]+alt="([^"]+)"', content)
        if not title_m:
            title_m = re.search(r'<h2[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h2>', content)
        if not title_m:
            continue
        title = html.unescape(title_m.group(1).strip())

        # Source
        source_m = re.search(r'class="footer-source"[^>]*>([^<]+)</span>', content)
        source = source_m.group(1).strip() if source_m else "富途牛牛"

        # Image URL for date extraction
        img_m = re.search(r'<img[^>]+src="([^"]+)"', content)
        img_src = img_m.group(1) if img_m else ""

        # Footer time
        time_m = re.search(r'class="footer-time"[^>]*>(.*?)</span>', content, re.DOTALL)
        footer_time = time_m.group(1).strip() if time_m else ""

        published, time_ago = _parse_ssr_time(img_src, footer_time)
        pub_dt = datetime.strptime(published, "%Y-%m-%d %H:%M").replace(tzinfo=BEIJING_TZ)
        articles.append({
            "url": article_url,
            "title": title,
            "source": source,
            "published": published,
            "published_ts": int(pub_dt.timestamp()),
            "time_ago": time_ago,
        })

    return articles


def fetch_futu_news() -> list[dict]:
    """Fetch 要闻 + 快讯 from Futu, filter gold-related items.

    Combines:
    - SSR articles from /zh/main (要闻)
    - Flash news from get-flash-list API (快讯)
    All items pass through gold keyword filter.
    """
    global _cache, _cache_ts
    now_ts = time.time()
    if _cache and (now_ts - _cache_ts) < _TTL:
        return _cache

    all_items = []
    seen_urls: Set[str] = set()

    # Source 1–2: SSR articles from /zh/main and /main
    for url, lang in SSR_PAGES:
        for article in _fetch_ssr_articles(url, lang):
            title = article["title"]
            if not _is_gold_news(title):
                continue
            url_key = article["url"]
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            all_items.append({
                "source": "富途牛牛",
                "title_en": title,
                "title": title,
                "url": url_key,
                "published": article["published"],
                "time_ago": article["time_ago"],
            })

    # Source 2: Flash news from get-flash-list API (快讯)
    try:
        resp = httpx.get(
            "https://news.futunn.com/news-site-api/main/get-flash-list",
            params={"pageSize": 200},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": "https://news.futunn.com/zh/main",
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
        for n in news_list:
            ts = n.get("time", "")
            pub_ts = int(ts) if ts.isdigit() else None
            pub_date = (
                datetime.fromtimestamp(pub_ts, BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
                if pub_ts else ""
            )
            content = n.get("content", "").strip()
            title = content[:80] if content else ""
            detail_url = n.get("detailUrl", "") or ""
            if not _is_gold_news(title, content):
                continue
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)
            pub_dt = datetime.fromtimestamp(pub_ts, BEIJING_TZ)
            all_items.append({
                "source": "富途牛牛",
                "title_en": title,
                "title": title,
                "url": detail_url,
                "published": pub_dt.strftime("%Y-%m-%d %H:%M"),
                "published_ts": pub_ts,
            })
    except Exception as e:
        logger.warning("Futu flash API error: %s", e)

    _cache = all_items
    _cache_ts = now_ts
    logger.info(f"Futu: {len(all_items)} gold items (要闻+快讯)")
    return all_items


# Alias for pluggable interface
fetch_news = fetch_futu_news
