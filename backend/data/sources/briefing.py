"""AI 金市简报生成 via claude -p 命令。"""
import json
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone

from backend.data.db import save_briefing

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

PROMPT_TEMPLATE = """你是一位专业、客观的黄金市场分析师。请根据以下 {news_count} 条新闻，撰写一份简洁、有深度的金市每日简报。

要求：
- 结构清晰，分为"市场概况"、"影响因素"、"短期展望"三个部分
- 篇幅控制在 300-500 字左右
- 语言简洁专业，适合投资者快速阅读
- 若有重大利多/利空因素，需明确指出
- 无需客套话，直接开始分析

以下是新闻列表：
{news_list}
"""


def call_claude_cli(prompt: str) -> str:
    """调用 claude -p 命令，返回简报文本。"""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=120, env={**os.environ},
        )
        if result.returncode != 0:
            logger.warning(f"Claude CLI error: {result.stderr}")
            return ""
        return result.stdout.strip()
    except FileNotFoundError:
        logger.warning("claude CLI not found")
        return ""
    except Exception as e:
        logger.warning(f"Claude CLI call failed: {e}")
        return ""


def _build_news_list(news: list[dict]) -> tuple[str, list[str]]:
    """从新闻列表构建 prompt 中的新闻文本和标题列表。"""
    titles = []
    lines = []
    for i, n in enumerate(news[:20], 1):
        title = n.get("title", "").strip()
        source = n.get("source", "未知来源")
        if title:
            titles.append(title)
            lines.append(f"{i}. [{source}] {title}")
    return "\n".join(lines), titles


async def generate_briefing_from_news(news: list[dict], hour_label: str):
    """用 news 生成简报并写入数据库。"""
    if not news:
        logger.info("No news to generate briefing")
        return

    news_list_text, news_titles = _build_news_list(news)
    prompt = PROMPT_TEMPLATE.format(news_count=len(news), news_list=news_list_text)

    content = call_claude_cli(prompt)
    if not content:
        logger.warning("Briefing generation failed, skipping save")
        return

    await save_briefing(
        content=content,
        news_count=len(news),
        news_titles=news_titles,
        time_range=hour_label,
    )
    logger.info(f"Briefing saved: {content[:60]}...")
