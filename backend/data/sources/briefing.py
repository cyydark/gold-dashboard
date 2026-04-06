"""AI 金市简报生成 via claude -p 命令。"""
import logging
import os
import subprocess

from backend.data import constants as c

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

DAILY_PROMPT_TEMPLATE = """你是一位专业黄金市场分析师。基于最新资讯提供的{news_count}条相关新闻，请评估当前金价走势。

评估原则：
1. 时效性：越近期的新闻权重越高
2. 重要性分级：地缘政治/突发风险 ★★★ > 央行政策/宏观经济 ★★ > 市场情绪/技术面 ★
3. 综合判断，给出金价走势预期

{news_list}

请严格按以下4行格式输出，无任何解释、前言或分节符号：
【金价走势】震荡偏强/震荡偏弱/上涨/下跌/区间震荡——20字以内一句话概括核心逻辑
【重点关注】近期最值得关注的2-3条新闻（30字以内）
★★★ 因素一（地缘政治/突发风险）：一句话影响分析
★★ 因素二（央行政策/宏观经济）：一句话影响分析"""


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


def _build_news_list(news: list[dict]) -> str:
    """从新闻列表构建 prompt 文本。"""
    lines = []
    for n in news:
        title = n.get("title", "").strip()
        if not title:
            continue
        lines.append(title)
    return "\n".join(lines)


async def generate_briefing_from_news(news: list[dict], hour_range: str) -> str:
    """Generate hourly briefing text from news using Claude CLI."""
    if not news:
        return "暂无足够新闻数据生成简报。"
    news_list = _build_news_list(news)
    prompt = PROMPT_TEMPLATE.format(news_list=news_list)
    return call_claude_cli(prompt)


async def generate_daily_briefing_from_news(news: list[dict], date_str: str) -> str:
    """Generate daily briefing text from news using Claude CLI."""
    if not news:
        return "暂无足够新闻数据生成日报。"
    news_list = _build_news_list(news)
    prompt = DAILY_PROMPT_TEMPLATE.format(news_count=len(news), news_list=news_list)
    return call_claude_cli(prompt)
