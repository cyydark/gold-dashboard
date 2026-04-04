"""
AI Briefing: MiniMax-powered news sentiment analysis and hourly gold briefing.
"""
import os
import re
import logging
import feedparser
import httpx
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

# MiniMax config
_MINIMAX_KEY = os.getenv("MINIMAX_API_KEY", "")
_MINIMAX_BASE = "https://api.minimax.chat/v1"
_MODEL = "MiniMax-M2.7"

# Sources config
_SOURCES_FILE = Path(os.getenv("SOURCES_FILE", "/Users/chenyanyu/DoSomeThing/gold-dashboard/sources.yaml"))
_RSSHUB_BASE = os.getenv("RSSHUB_BASE_URL", "http://192.168.2.200:11200")

MINIMAX_SYSTEM_PROMPT = (
    "你是一位专业的贵金属分析师，专注于黄金市场。"
    "你的分析简洁、有深度，用中文回答。"
    "输出内容必须纯净，只输出最终分析结果，不要包含任何思考过程或推理标签。"
)

# Shared AI state (read by /api/briefing endpoint)
_ai_state = {
    "briefing": None,
    "briefing_ts": 0,
    "alerts": [],
    "news": [],
}


def get_ai_state() -> dict:
    return _ai_state


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> thinking tags from model output."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def _call_minimax(prompt: str, max_tokens: int = 600, temperature: float = 0.3) -> str:
    """Call MiniMax API, return stripped text."""
    if not _MINIMAX_KEY:
        return ""

    try:
        client = OpenAI(api_key=_MINIMAX_KEY, base_url=_MINIMAX_BASE)
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": MINIMAX_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        return _strip_think_tags(content)
    except Exception as e:
        logger.warning(f"MiniMax API error: {e}")
        return ""


def _get_sources() -> list[dict]:
    """Load sources from YAML config."""
    if not _SOURCES_FILE.exists():
        return []
    try:
        with open(_SOURCES_FILE) as f:
            data = yaml.safe_load(f)
        return data.get("sources", [])
    except Exception as e:
        logger.warning(f"Failed to load sources.yaml: {e}")
        return []


def _get_news() -> list[dict]:
    """Fetch news from RSS sources in sources.yaml."""
    sources = _get_sources()
    if not sources:
        return []

    all_news = []
    keywords = set()
    for src in sources:
        if not src.get("enabled"):
            continue
        for kw in src.get("keywords", []):
            keywords.add(kw.strip())

        url = src["url"].replace("http://192.168.2.200:11200", _RSSHUB_BASE)
        try:
            resp = httpx.get(url, timeout=15, verify=False)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                all_news.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": src["name"],
                    "sentiment": None,
                    "level": None,
                    "reason": None,
                })
        except Exception as e:
            logger.warning(f"Failed to fetch {src['name']}: {e}")

    # Deduplicate by title
    seen = set()
    deduped = []
    for n in all_news:
        if n["title"] not in seen:
            seen.add(n["title"])
            deduped.append(n)

    # Keyword filter: keep only gold-relevant news
    if keywords:
        filtered = []
        for n in deduped:
            title_lower = n["title"].lower()
            if any(kw.lower() in title_lower for kw in keywords):
                filtered.append(n)
        return filtered[:20]

    return deduped[:20]


def _analyze_news(news: list[dict]) -> list[dict]:
    """Run MiniMax sentiment analysis on each news item."""
    sentiment_prompt = """判断以下新闻对黄金价格的影响，用JSON格式回答：

新闻标题：{title}
新闻来源：{source}

要求：
1. sentiment：利多（利多金价）、利空（利空金价）、中性
2. level：轻微（对金价影响小）、中等（有一定影响）、重大（重大影响）
3. reason：1-2句话解释原因

只输出JSON，不要其他内容：
{{"sentiment":"利多|利空|中性","level":"轻微|中等|重大","reason":"原因"}}
"""

    results = []
    for n in news:
        prompt = sentiment_prompt.format(title=n["title"], source=n["source"])
        raw = _call_minimax(prompt, max_tokens=150)

        # Parse JSON from response
        sentiment = "中性"
        level = "轻微"
        reason = ""

        try:
            # Try to extract JSON object
            m = re.search(r'\{[^{}]*\}', raw)
            if m:
                import json
                parsed = json.loads(m.group())
                sentiment = parsed.get("sentiment", "中性")
                level = parsed.get("level", "轻微")
                reason = parsed.get("reason", "")
        except Exception:
            pass

        n["sentiment"] = sentiment
        n["level"] = level
        n["reason"] = reason
        results.append(n)

    return results


def _generate_briefing(news: list[dict]):
    """Generate hourly briefing from analyzed news (no current gold price)."""
    if not news:
        return

    # Sort newest first
    news_sorted = sorted(news, key=lambda x: x.get("published", ""), reverse=True)

    news_text = "\n".join(
        f"- [{n['source']}] {n['title']} (情绪:{n.get('sentiment','中性')})"
        for n in news_sorted[:15]
    )

    prompt = f"""你是一位专业的黄金市场分析师，根据今日相关新闻生成一份金价简报。

今日相关新闻：
{news_text}

要求：
1. 不提及当前具体金价数字
2. 总结今日主要驱动因素（地缘政治、美元、利率等）
3. 指出最值得关注的1-3个事件
4. 给出后市判断（偏多/偏空/中性）
5. 提示纸黄金投资者应注意什么

用中文，简洁有力，不超过300字。禁止使用<think>或</think>等推理标记。"""

    briefing = _call_minimax(prompt, max_tokens=500, temperature=0.5)
    if not briefing:
        return

    global _ai_state
    _ai_state["briefing"] = briefing
    _ai_state["briefing_ts"] = int(datetime.now(BEIJING_TZ).timestamp())
    logger.info(f"Briefing generated: {briefing[:60]}...")


def run_ai_check(force_briefing: bool = False):
    """Main entry: fetch news → analyze sentiment → generate briefing hourly."""
    global _ai_state

    news = _get_news()
    if not news:
        logger.warning("No news fetched for AI analysis")
        return

    # Analyze sentiment for each news item
    analyzed = _analyze_news(news)

    # Build alerts (medium/significant, non-neutral)
    alerts = [
        {
            "title": n["title"][:100],
            "source": n["source"],
            "sentiment": n["sentiment"],
            "level": n["level"],
            "summary": n.get("reason", ""),
            "link": n["link"],
            "ts": int(datetime.now(BEIJING_TZ).timestamp()),
        }
        for n in analyzed
        if n["level"] in ("中等", "重大") and n["sentiment"] != "中性"
    ][:10]

    _ai_state["news"] = analyzed
    _ai_state["alerts"] = alerts

    # Generate briefing every hour (or on demand)
    now_ts = int(datetime.now(BEIJING_TZ).timestamp())
    last_ts = _ai_state.get("briefing_ts", 0)
    if force_briefing or (now_ts - last_ts) >= 3600:
        _generate_briefing(analyzed)

    logger.info(f"AI check done: {len(analyzed)} news, {len(alerts)} alerts, briefing={bool(_ai_state['briefing'])}")
