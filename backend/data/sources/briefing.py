"""AI 金市简报生成 via claude -p 命令。"""
import logging
import os
import subprocess
import threading

from backend.data import constants as c
from backend.data.db import save_hourly_briefing, save_daily_briefing
from backend.data.sources.futu import _sync_save_news

logger = logging.getLogger(__name__)


class BriefingGenerationError(Exception):
    """Raised when Claude CLI fails to generate a briefing."""

    pass

PROMPT_TEMPLATE = """你是一位专业、客观的黄金市场分析师。以下是近1小时内与金市相关的新闻。

要求：
- 将该小时所有新闻汇总为一条判断，格式：「📈利多/📉利空/➖中性」+ 一句话原因
- 篇幅不超过40字，直接输出，无需标题和分节

新闻列表：
{news_list}
"""

DAILY_PROMPT_TEMPLATE = """你是一位专业黄金市场分析师，基于昨日（北京时间）{news_count}条相关新闻，给出今日金价走势判断。

{news_list}

请直接输出，格式如下，一行判断 + 最多3条依据，不要标题和分节符号：
【金价预期】上涨/下跌/震荡偏强/震荡偏弱/区间震荡——一句话说明
1. 因素一：说明
2. 因素二：说明
3. 因素三：说明
"""


def call_claude_cli(prompt: str) -> str:
    """调用 claude -p 命令，返回简报文本。"""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=c.CLI_TIMEOUT, env={**os.environ},
        )
        if result.returncode != 0:
            logger.warning(f"Claude CLI error: {result.stderr}")
            raise BriefingGenerationError(f"Claude CLI exited with code {result.returncode}: {result.stderr}")
        return result.stdout.strip()
    except FileNotFoundError:
        logger.warning("claude CLI not found")
        raise BriefingGenerationError("claude CLI not found")
    except Exception as e:
        logger.warning(f"Claude CLI call failed: {e}")
        raise BriefingGenerationError(f"Claude CLI call failed: {e}")


def _build_news_list(news: list[dict], limit: int = c.NEWS_LIMIT_BRIEFING) -> str:
    """从新闻列表构建 prompt 文本。"""
    lines = []
    for i, n in enumerate(news[:limit], 1):
        title = n.get("title", "").strip()
        source = n.get("source", "未知来源")
        if not title:
            continue
        lines.append(f"{i}. [{source}] {title}")
    return "\n".join(lines)


async def generate_briefing_from_news(news: list[dict], hour_range: str):
    """用 news 生成简报并写入数据库，同时保存该时段的新闻。"""
    if not news:
        logger.info("No news to generate briefing")
        return

    news_list_text = _build_news_list(news)
    prompt = PROMPT_TEMPLATE.format(news_list=news_list_text)

    try:
        content = call_claude_cli(prompt)
    except BriefingGenerationError:
        logger.warning("Briefing generation failed, skipping save")
        return

    # 保存新闻时标记时段
    threading.Thread(target=_sync_save_news, args=(news, hour_range), daemon=True).start()

    await save_hourly_briefing(
        content=content,
        news_count=len(news),
        time_range=hour_range,
    )
    logger.info(f"Hourly briefing saved: {content[:60]}...")


async def generate_daily_briefing_from_news(news: list[dict], date_str: str):
    """用昨日全天新闻生成每日简报并写入数据库（不重复保存新闻）。"""
    if not news:
        logger.info("No news to generate daily briefing")
        return

    news_list_text = _build_news_list(news, limit=len(news))
    prompt = DAILY_PROMPT_TEMPLATE.format(news_count=len(news), news_list=news_list_text)

    try:
        content = call_claude_cli(prompt)
    except BriefingGenerationError:
        logger.warning("Daily briefing generation failed, skipping save")
        return

    await save_daily_briefing(
        content=content,
        news_count=len(news),
        date_str=date_str,
    )
    logger.info(f"Daily briefing saved for {date_str}: {content[:60]}...")
