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

DAILY_PROMPT_TEMPLATE = """你是一位专业黄金市场分析师。基于近3天内（北京时间）{news_count}条相关新闻，请评估当前金价走势。

评估要求：
1. 参考新闻的时效性（越近期的新闻权重越高）
2. 评估新闻对金价的重要性（地缘政治 > 宏观经济 > 市场情绪）
3. 综合判断，给出金价走势预期

{news_list}

请直接输出，格式如下，先一行判断，再最多3条核心依据，不要标题和分节符号：
【金价预期】震荡偏强/震荡偏弱/上涨/下跌/区间震荡——一句话说明核心逻辑
1. 因素一（重要性）：简要说明
2. 因素二（重要性）：简要说明
3. 因素三（重要性）：简要说明"""


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


def _build_news_list(news: list[dict], limit: int = 20) -> str:
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
    """No-op: DB removed, briefings served from in-memory BriefingService."""
    pass


async def generate_daily_briefing_from_news(news: list[dict], date_str: str):
    """No-op: DB removed, briefings served from in-memory BriefingService."""
    pass
