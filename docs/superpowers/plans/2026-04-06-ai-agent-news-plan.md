# AI 多 Agent 并发新闻搜索实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 MiniMax MCP web_search 并发 3 路 AI agent 搜索金价新闻，完成后汇总分析替换现有爬虫方案。

**Architecture:** Python asyncio 并发调用 `claude -p --mcp-config ... --dangerously-skip-permissions` 启动 3 个搜索子 agent，结果合并去重后送入主分析 agent，输出新闻列表 + 金价分析。

**Tech Stack:** Python asyncio + subprocess，Claude Code CLI + MiniMax MCP，无新增依赖。

---

## 文件变更总览

| 文件 | 操作 |
|------|------|
| `~/.claude/mcp_minimax.json` | 新增 — MCP server 配置 |
| `backend/data/sources/minimax_news.py` | 新增 — MiniMax agent 封装 + 结果解析 |
| `backend/services/briefing_service.py` | 重构 — 替换 `_fetch_news`，TTL 更新为 10min/30min |
| `frontend/js/app.js` | 调整 — `days=3` 参数确认 |
| `frontend/index.html` | 调整 — 版本号更新 |

---

## Task 1: 创建 MCP 配置文件

**文件：** `~/.claude/mcp_minimax.json`

- [ ] **Step 1: 写入配置文件**

```json
{
  "mcpServers": {
    "MiniMax": {
      "type": "stdio",
      "command": "/Users/chenyanyu/.local/bin/uvx",
      "args": ["minimax-coding-plan-mcp", "-y"],
      "env": {
        "MINIMAX_API_KEY": "sk-cp-KlpVl6IfxHEuVcDNinRnv8ajicGtO9iRdv-fo3TPuov8B00EyZOxOEC5evQG41Hq642rnE8Daylg-7yh0VVjXZN57YhWozCbiC7sazdx49kk43mkwhtwWyo",
        "MINIMAX_API_HOST": "https://api.minimaxi.com"
      }
    }
  }
}
```

Run:
```bash
cat > ~/.claude/mcp_minimax.json << 'EOF'
{
  "mcpServers": {
    "MiniMax": {
      "type": "stdio",
      "command": "/Users/chenyanyu/.local/bin/uvx",
      "args": ["minimax-coding-plan-mcp", "-y"],
      "env": {
        "MINIMAX_API_KEY": "sk-cp-KlpVl6IfxHEuVcDNinRnv8ajicGtO9iRdv-fo3TPuov8B00EyZOxOEC5evQG41Hq642rnE8Daylg-7yh0VVjXZN57YhWozCbiC7sazdx49kk43mkwhtwWyo",
        "MINIMAX_API_HOST": "https://api.minimaxi.com"
      }
    }
  }
}
EOF
```

- [ ] **Step 2: 验证 MCP 可用**

```bash
claude -p "用web_search搜索黄金新闻，返回1条" --mcp-config ~/.claude/mcp_minimax.json --dangerously-skip-permissions --output-format text 2>&1 | head -5
```
Expected: 返回包含黄金新闻标题的文字

- [ ] **Step 3: Commit**

```bash
echo "MCP config created at ~/.claude/mcp_minimax.json"
git add backend/ && git commit -m "feat: add MiniMax MCP config for AI news search"
```

---

## Task 2: 创建 minimax_news.py（搜索 agent 封装）

**文件：** Create: `backend/data/sources/minimax_news.py`

- [ ] **Step 1: 写搜索 agent 函数（subprocess 调用 claude -p + MCP）**

```python
"""MiniMax MCP web_search agent — 并发多路 AI 搜索金价新闻。"""
import asyncio
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
MCP_CONFIG = os.path.expanduser("~/.claude/mcp_minimax.json")
SEARCH_TIMEOUT = 60  # seconds
ANALYZE_TIMEOUT = 120  # seconds


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    published_ts: int  # Unix UTC
    published: str     # "YYYY-MM-DD"

    @classmethod
    def from_text(cls, title: str, summary: str = "", url: str = "",
                  source: str = "MiniMax") -> "NewsItem":
        now = datetime.now(BEIJING_TZ)
        return cls(
            title=title.strip(),
            summary=summary.strip(),
            url=url.strip(),
            source=source,
            published_ts=int(now.timestamp()),
            published=now.strftime("%Y-%m-%d"),
        )


SEARCH_QUERIES = {
    "geopolitics": "黄金 地缘政治 战争 制裁 最新新闻",
    "macro": "美联储 利率 央行 黄金 宏观 最新",
    "market": "黄金价格 黄金ETF 黄金期货 行情 最新",
}

SEARCH_PROMPT_TEMPLATE = """你是一位黄金市场资讯搜索助手。请使用 web_search 工具搜索以下内容：

【搜索任务】
{query}

请返回 3-5 条最新相关新闻，每条包含：
- 标题
- 发布时间（如已知）
- 内容摘要（50字以内）
- 原始链接（可选）

搜索要求：
1. 优先返回中文新闻，其次英文
2. 发布时间在近 7 天内
3. 内容必须与黄金价格直接相关

直接输出搜索结果，无需解释。"""


ANALYZE_PROMPT_TEMPLATE = """你是一位专业黄金市场分析师。基于以下从多个权威来源搜索到的最新新闻，请评估当前金价走势。

【搜索来源汇总】
{news_list}

评估原则：
1. 时效性：越近期的新闻权重越高
2. 重要性分级：地缘政治/突发风险 ★★★ > 央行政策/宏观经济 ★★ > 市场情绪/技术面 ★
3. 综合判断，给出金价走势预期

请严格按以下4行格式输出，无任何解释、前言或分节符号：
【金价走势】震荡偏强/震荡偏弱/上涨/下跌/区间震荡——20字以内一句话概括核心逻辑
【重点关注】近期最值得关注的2-3条新闻（标注来源，30字以内）
★★★ 因素一（地缘政治/突发风险）：一句话影响分析
★★ 因素二（央行政策/宏观经济）：一句话影响分析"""


def _call_claude(prompt: str, timeout: int, extra_env: dict | None = None) -> str:
    """调用 claude -p，带 MCP config，返回 stdout。"""
    env = {**os.environ}
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--mcp-config", MCP_CONFIG,
            "--dangerously-skip-permissions",
            "--output-format", "text",
        ],
        capture_output=True, text=True, timeout=timeout, env=env,
    )
    if result.returncode != 0:
        logger.warning(f"claude -p error: {result.stderr[:200]}")
        raise RuntimeError(f"claude exit {result.returncode}: {result.stderr[:100]}")
    return result.stdout.strip()


def _parse_news_from_text(text: str) -> list[NewsItem]:
    """从 agent 输出文本解析 NewsItem 列表。

    Agent 输出格式不定，尝试从常见 Markdown 列表格式解析。
    """
    items: list[NewsItem] = []
    lines = text.strip().splitlines()
    for line in lines:
        line = line.strip()
        # 跳过空行和元信息行
        if not line or line.startswith("【") or line.startswith("搜索") or line.startswith("##"):
            continue
        # 解析 Markdown 列表项: "- **标题** 摘要"
        # 或: "1. 标题 - 摘要"
        # 或: "标题（摘要）"
        title = ""
        summary = ""

        # 去掉列表标记
        for prefix in ("- ", "* ", "• "):
            if line.startswith(prefix):
                line = line[len(prefix):]
                break

        # 提取加粗标题: **标题**
        import re as _re
        m = _re.search(r'\*\*([^*]+)\*\*', line)
        if m:
            title = m.group(1)
            rest = line[m.end():].strip()
            if rest.startswith("-") or rest.startswith("—"):
                summary = rest.lstrip("-—").strip()
        else:
            # 尝试冒号分割
            parts = line.split("：", 1)
            if len(parts) == 2:
                title = parts[0].strip()
                summary = parts[1].strip()
            else:
                title = line[:80]

        if title and len(title) > 3:
            items.append(NewsItem.from_text(title, summary))

    return items


async def search_agent(query: str, dimension: str) -> list[NewsItem]:
    """运行单个搜索 agent，返回 NewsItem 列表。"""
    prompt = SEARCH_PROMPT_TEMPLATE.format(query=query)
    try:
        loop = asyncio.get_event_loop()
        text = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _call_claude(prompt, SEARCH_TIMEOUT)),
            timeout=SEARCH_TIMEOUT + 5,
        )
        items = _parse_news_from_text(text)
        logger.info(f"Agent [{dimension}] returned {len(items)} items")
        return items
    except asyncio.TimeoutError:
        logger.warning(f"Agent [{dimension}] timed out")
        return []
    except Exception as e:
        logger.error(f"Agent [{dimension}] failed: {e}")
        return []


async def search_all() -> list[NewsItem]:
    """并发执行 3 路搜索 agent，去重合并返回。"""
    tasks = [
        search_agent(q, dim)
        for dim, q in SEARCH_QUERIES.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[NewsItem] = []
    for i, r in enumerate(results):
        dim = list(SEARCH_QUERIES.keys())[i]
        if isinstance(r, Exception):
            logger.error(f"Agent [{dim}] exception: {r}")
            continue
        all_items.extend(r)

    # 去重：按 title 前50字符去重
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in all_items:
        key = item.title[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # 按时间倒序
    unique.sort(key=lambda x: x.published_ts, reverse=True)
    logger.info(f"search_all: {len(all_items)} total, {len(unique)} unique")
    return unique


def news_items_to_dict(items: list[NewsItem]) -> list[dict]:
    return [
        {
            "title": it.title,
            "summary": it.summary,
            "url": it.url,
            "source": it.source,
            "published_ts": it.published_ts,
            "published": it.published,
        }
        for it in items
    ]


async def analyze_news(items: list[NewsItem]) -> str:
    """主分析 agent：基于新闻列表生成金价分析。"""
    if not items:
        return "暂无足够新闻数据生成分析。"
    news_lines = []
    for i, it in enumerate(items[:15], 1):
        line = f"{i}. [{it.source}] {it.title}"
        if it.summary:
            line += f" — {it.summary}"
        news_lines.append(line)
    news_list = "\n".join(news_lines)
    prompt = ANALYZE_PROMPT_TEMPLATE.format(news_list=news_list)
    try:
        loop = asyncio.get_event_loop()
        content = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _call_claude(prompt, ANALYZE_TIMEOUT)),
            timeout=ANALYZE_TIMEOUT + 5,
        )
        logger.info(f"Analysis generated: {len(content)} chars")
        return content.strip()
    except asyncio.TimeoutError:
        logger.error("Analysis timed out")
        return "分析生成超时，请重试。"
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return f"分析生成失败：{e}"
```

- [ ] **Step 2: 验证文件语法**

Run: `python3 -c "import backend.data.sources.minimax_news; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/data/sources/minimax_news.py
git commit -m "feat: add MiniMax MCP search agent"
```

---

## Task 3: 重构 briefing_service.py

**文件：** Modify: `backend/services/briefing_service.py`

TTL 更新：新闻 10 分钟，分析 30 分钟。

- [ ] **Step 1: 写新版本 briefing_service.py**

```python
"""Briefing service — AI agent 搜索 + 分析，in-memory 缓存。

News TTL: 10 min | Analysis TTL: 30 min
"""
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
_NEWS_TTL = 600    # 10 minutes
_ANALYSIS_TTL = 1800  # 30 minutes

_news_cache: dict = {"ts": 0, "data": None}
_analysis_cache: dict = {"ts": 0, "data": ""}


def get_briefing(days: int = 3) -> dict:
    """返回缓存的 briefing + news，各自从 TTL 独立刷新。"""
    news = _get_news(days)
    analysis = _get_analysis(news, days)
    return {
        "weekly": {
            "content": analysis,
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def _get_news(days: int) -> list:
    if _news_cache["data"] is not None and (time.time() - _news_cache["ts"]) < _NEWS_TTL:
        return _news_cache["data"]
    # 强制刷新
    return refresh_news(days)["news"]


def _get_analysis(news: list, days: int) -> str:
    if _analysis_cache["data"] is not None and (time.time() - _analysis_cache["ts"]) < _ANALYSIS_TTL:
        return _analysis_cache["data"]
    return _generate_analysis(news, days)


def refresh_news(days: int = 3) -> dict:
    """强制刷新新闻（并发 AI 搜索），不清除现有 AI 分析缓存。"""
    from backend.data.sources.minimax_news import search_all, news_items_to_dict

    try:
        items = asyncio.run(search_all())
        news = news_items_to_dict(items)
        _news_cache["data"] = news
        _news_cache["ts"] = time.time()
        logger.info(f"refresh_news: {len(news)} items fetched")

        # 同时更新 AI 分析（用新新闻）
        analysis = _generate_analysis(news, days)
        return {
            "weekly": {
                "content": analysis,
                "time_range": _time_range(days),
                "news_count": len(news),
            },
            "news": news,
            "news_count": len(news),
        }
    except Exception as e:
        logger.error(f"refresh_news failed: {e}")
        # 回退到缓存
        fallback = _news_cache["data"] or []
        return {
            "weekly": {
                "content": _analysis_cache["data"] or "搜索失败，请重试。",
                "time_range": _time_range(days),
                "news_count": len(fallback),
            },
            "news": fallback,
            "news_count": len(fallback),
        }


def refresh_briefing_only(days: int = 3) -> dict:
    """强制重新分析，不刷新新闻。"""
    news = _news_cache["data"] or []
    analysis = _generate_analysis(news, days)
    return {
        "weekly": {
            "content": analysis,
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }


def _generate_analysis(news: list, days: int) -> str:
    """调用 AI 主分析 agent。"""
    if not news:
        return "暂无足够新闻数据生成分析。"
    from backend.data.sources.minimax_news import analyze_news

    try:
        content = asyncio.run(analyze_news(news))
        _analysis_cache["data"] = content
        _analysis_cache["ts"] = time.time()
        return content
    except Exception as e:
        logger.error(f"_generate_analysis failed: {e}")
        return f"分析生成失败：{e}"


def _time_range(days: int) -> str:
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"
```

- [ ] **Step 2: 验证语法**

Run: `python3 -c "from backend.services.briefing_service import get_briefing, refresh_news; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/briefing_service.py
git commit -m "refactor: replace news scrapers with MiniMax AI agent search"
```

---

## Task 4: 前端适配

**文件：** Modify: `frontend/index.html`（版本号）

- [ ] **Step 1: 更新 JS 版本号**

```bash
# 在 frontend/index.html 中将 app.js?v=32 改为 v=33
sed -i '' 's/app.js?v=[0-9]*/app.js?v=33/' frontend/index.html
```

- [ ] **Step 2: Commit**

```bash
git add frontend/index.html
git commit -m "chore: bump app.js to v33"
```

---

## Task 5: 端到端测试

- [ ] **Step 1: 重启后端**

```bash
cd /Users/chenyanyu/DoSomeThing/gold-dashboard && ./start.sh restart
```

- [ ] **Step 2: 测试搜索 API**

```bash
curl -s -X POST "http://127.0.0.1:18000/api/briefings/news/refresh?days=3" | python3 -c "
import sys, json
d = json.load(sys.stdin)
news = d.get('news', [])
print(f'News: {len(news)} items')
for n in news[:3]:
    print(f'  - [{n[\"source\"]}] {n[\"title\"]}')
print(f'Analysis: {d[\"weekly\"][\"content\"][:100]}...')
"
```
Expected: 返回多条新闻 + AI 分析文本（耗时约 30-60s）

- [ ] **Step 3: 测试刷新按钮**

在浏览器打开 http://127.0.0.1:18000，点「🔄 刷新资讯」，观察：
- 新闻列表秒出？
- AI 分析骨架等待？
- Toast 显示条数？

---

## Task 6: 清理旧文件（可选）

确认新方案稳定后，删除旧爬虫文件：
- `backend/data/sources/bernama.py`
- `backend/data/sources/futu.py`
- `backend/data/sources/aastocks.py`
- `backend/data/sources/news_evaluation.py`
- `backend/data/sources/briefing.py`

如保留作为兜底，改为从新服务导入即可。
