"""News AI evaluation: gold price impact assessment.

DB layer removed; _sync_save_processed_news and _update_direction_in_db are no-ops.
"""
import logging
import os
import re
import subprocess

from backend.data import constants as c

logger = logging.getLogger(__name__)

# Compiled once
DIRECTION_RE = re.compile(r"^[\u300c\u201c]?(上升|下降|中性)[\u300d\u201d].*[\u300c\u201c]?(重点关注|普通)[\u300d\u201d]")


EVALUATE_PROMPT_TEMPLATE = """以下是黄金市场相关新闻标题，请逐一评估每条新闻对金价的影响。

输出格式（每条一行，无需编号）：
「{direction}」「{watch}」「{title}」

其中：
- direction: 上升 | 下降 | 中性
- watch: 重点关注 | 普通
- title: 原文标题（保留不变）

标题列表：
{text}

直接输出结果，每条一行，无需解释："""


def _parse_evaluation(line: str) -> tuple[str, str]:
    """Parse a single evaluation line. Returns (direction, watch_tag)."""
    m = DIRECTION_RE.match(line.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "中性", "普通"


def _evaluate_titles(titles: list[str]) -> dict[str, tuple[str, str]]:
    """Batch-evaluate gold price impact via Claude CLI. Returns {title: (direction, watch_tag)}."""
    if not titles:
        return {}
    text = "\n".join(f"- {t}" for t in titles)
    prompt = EVALUATE_PROMPT_TEMPLATE.format(
        direction="{direction}", watch="{watch}", title="{title}", text=text
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=c.CLI_TIMEOUT, env={**os.environ},
        )
        if result.returncode != 0:
            logger.warning(f"Evaluate CLI error: {result.stderr}")
            return {}
        lines = result.stdout.strip().splitlines()
        results = {}
        for i, title in enumerate(titles):
            if i < len(lines):
                direction, watch_tag = _parse_evaluation(lines[i])
                results[title] = (direction, watch_tag)
            else:
                results[title] = ("中性", "普通")
        return results
    except Exception as e:
        logger.warning(f"Evaluate failed: {e}")
        return {}


def _update_direction_in_db(items: list[dict], evaluations: dict[str, tuple[str, str]]):
    """No-op: DB removed, direction cache updated in-memory only."""
    pass


def _sync_save_processed_news(items: list[dict], hour_range: str = ""):
    """No-op: DB removed, news saved to in-memory cache only."""
    pass
