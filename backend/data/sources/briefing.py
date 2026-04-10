"""AI 金市简报生成 via claude -p 命令。"""
import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone, timedelta

from backend.data import constants as c

logger = logging.getLogger(__name__)


class BriefingGenerationError(Exception):
    """Raised when Claude CLI fails to generate a briefing."""
    pass


DAILY_PROMPT_TEMPLATE = """用大白话分析黄金走势，结合新闻和实际行情数据。不要任何markdown格式。

【新闻来源】（共{news_count}条，当前金价 ${current_price} USD/oz）
{news_list}

【实际行情数据】
{kline_summary}

按顺序输出两个板块，不要任何markdown格式：

【分析结论】
（金价当前方向、核心驱动、新闻与走势是否吻合，用大白话）

【金价预期】

接下来涨还是跌：
说清楚。

能涨/跌到多少：
给个大概的数字区间。

什么时候见效：
大概要等多久？

什么情况下会变卦：
说出最可能打破预期的一件事。"""


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


async def call_claude_cli_async(prompt: str) -> str:
    """Async version of call_claude_cli."""
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--output-format", "text",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ},
    )
    try:
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(f"Claude CLI async error: {stderr.decode()}")
            return ""
        return stdout.decode().strip()
    finally:
        await proc.wait()


async def call_claude_cli_streaming(prompt: str):
    """流式生成，yield text chunks via claude CLI subprocess.

    --output-format stream-json 输出到 stdout。
    """
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ},
    )
    try:
        async for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            # stream-json 格式：{"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
            msg = data.get("message", {})
            if isinstance(msg, dict):
                for item in msg.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "text":
                        t = item.get("text", "")
                        if t:
                            yield t
            # 最终结果：{"type":"result","result":"..."}
            result = data.get("result")
            if isinstance(result, str) and result:
                yield result
    finally:
        # 消费 stderr 防止 pipe buffer 填满（不做 drain，只读空）
        try:
            await proc.stderr.read()
        except Exception as e:
            logger.debug("stderr drain error (non-fatal): %s", e)
        await proc.wait()


def _build_news_list(news: list[dict], limit: int = 30) -> str:
    """从新闻列表构建 prompt 文本，默认最多取前 limit 条。"""
    lines = []
    for n in news[:limit]:
        title = n.get("title", "").strip()
        if not title:
            continue
        lines.append(title)
    if len(news) > limit:
        lines.append(f"（另有 {len(news) - limit} 条新闻省略）")
    return "\n".join(lines)
