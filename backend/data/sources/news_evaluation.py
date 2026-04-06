"""News AI evaluation: translation + gold price impact assessment.

Centralized module for processing raw news — called by data source _sync_save_news
before writing to DB.

Evaluation runs asynchronously in a background thread to avoid blocking news saves.
"""
import asyncio
import logging
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone, timedelta

from backend.data import constants as c
from backend.repositories.news_repository import _direction_cache

logger = logging.getLogger(__name__)
BEIJING_TZ = timezone(timedelta(hours=8))
_evaluation_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="news_eval")

# Compiled once
DIRECTION_RE = re.compile(r"^[\u300c\u201c]?(上升|下降|中性)[\u300d\u201d].*[\u300c\u201c]?(重点关注|普通)[\u300d\u201d]")


def _is_english(text: str) -> bool:
    """Return True if text contains no CJK characters."""
    return not any('\u4e00' <= ch <= '\u9fff' for ch in text)


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
    """Update direction field for already-saved news items (called in background thread)."""
    if not evaluations:
        return
    try:
        updates = []
        for item in items:
            title_en = item.get("title_en", "")
            title = item.get("title", "")
            url = item.get("url", "")
            direction, watch_tag = evaluations.get(title_en) or evaluations.get(title) or ("中性", "普通")
            direction_field = direction if watch_tag == "普通" else f"{direction}|{watch_tag}"
            if url:
                _direction_cache[url] = direction_field
            if url:
                updates.append((direction_field, url))
        if updates:
            async def _do_update():
                from backend.repositories.news_repository import NewsRepository
                repo = NewsRepository()
                await repo.update_directions(updates)
                logger.info(f"Direction updated for {len(updates)} items")
            asyncio.run(_do_update())
    except Exception as e:
        logger.warning(f"Failed to update direction in DB: {e}")


def _sync_save_processed_news(items: list[dict], hour_range: str = ""):
    """Save news items to DB immediately; evaluate gold impact asynchronously.

    All data sources call this function instead of raw SQL writes.
    Evaluation runs in background to avoid blocking the news refresh flow.
    """
    if not items:
        return

    # Step 1: Save to DB immediately (no AI call — fast) via NewsRepository
    titles_to_eval = []
    eval_keys = []  # (title_en or title, lookup_key)

    try:
        async def _do_save():
            from backend.repositories.news_repository import NewsRepository
            repo = NewsRepository()
            await repo.save_many(items, hour_range)

        asyncio.run(_do_save())
    except Exception as e:
        logger.warning(f"Failed to save processed news to DB: {e}")
        return

    # Collect titles for async evaluation (skip if cached)
    for item in items:
        url = item.get("url", "")
        if url not in _direction_cache:
            title_en = item.get("title_en", "")
            title = item.get("title", "")
            if _is_english(title_en) and len(title_en) > 5:
                titles_to_eval.append(title_en)
                eval_keys.append((title_en, title_en))
            elif _is_english(title) and len(title) > 5:
                titles_to_eval.append(title)
                eval_keys.append((title, title))

    # Step 2: Kick off async evaluation (non-blocking)
    if titles_to_eval:
        def _background_evaluate():
            evals = _evaluate_titles(titles_to_eval)
            # Map back to items by title_en/title
            eval_map = {}
            for orig_title, lookup_key in eval_keys:
                if lookup_key in evals:
                    eval_map[lookup_key] = evals[lookup_key]
            _update_direction_in_db(items, eval_map)

        _evaluation_executor.submit(_background_evaluate)
