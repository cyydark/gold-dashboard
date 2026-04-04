# AI 简报功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 AI 简报功能，每小时由 Claude CLI 生成金价分析简报，永久存库，前端左右分栏展示。

**Architecture:**
- 后端：FastAPI 调度任务 + 数据库 + API 接口
- AI 调用：subprocess 调用 `claude -p` 命令
- 前端：Phase 1 临时区域测试，Phase 2 左右分栏替换新闻列表

**Tech Stack:** FastAPI / SQLite / Claude CLI / Vanilla JS

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/data/db.py` | 修改 | 新增 `ai_briefings` 表、新增 `save_briefing`/`get_recent_briefings` 函数 |
| `backend/alerts/checker.py` | 修改 | 新增每小时调度任务 `_generate_briefing` |
| `backend/routers/price.py` | 修改 | 新增 `GET /api/briefings` 接口 |
| `frontend/index.html` | 修改 | Phase 1 临时简报区域 |
| `frontend/js/app.js` | 修改 | 获取并渲染简报数据 |
| `frontend/css/style.css` | 修改 | Phase 1 临时样式 |

---

## Phase 1 实现

### Task 1: 数据库表和函数

**Files:**
- Modify: `backend/data/db.py`

- [ ] **Step 1: 在 init_db 中新增 ai_briefings 表**

在 `backend/data/db.py` 的 `init_db` 函数中，`news_items` 表创建语句之后添加：

```python
await db.executescript("""
    CREATE TABLE IF NOT EXISTS ai_briefings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        news_count INTEGER DEFAULT 0,
        news_titles TEXT,
        time_range TEXT,
        generated_at TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
""")
```

- [ ] **Step 2: 新增 save_briefing 函数**

在 `backend/data/db.py` 末尾添加：

```python
async def save_briefing(content: str, news_count: int, news_titles: list[str], time_range: str) -> int:
    """保存一条 AI 简报到数据库，返回新记录 ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO ai_briefings (content, news_count, news_titles, time_range, generated_at) VALUES (?, ?, ?, ?, ?)",
            (content, news_count, json.dumps(news_titles, ensure_ascii=False), time_range, datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_recent_briefings(limit: int = 24) -> list[dict]:
    """获取最近 limit 条简报，按时间倒序（最新在前）."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT id, content, news_count, news_titles, time_range, generated_at, created_at "
            "FROM ai_briefings ORDER BY generated_at DESC LIMIT ?",
            (limit,),
        )
        results = []
        for r in await rows.fetchall():
            d = dict(r)
            if d.get("news_titles"):
                try:
                    d["news_titles"] = json.loads(d["news_titles"])
                except Exception:
                    d["news_titles"] = []
            results.append(d)
        return results
```

- [ ] **Step 3: 添加 import**

在 `backend/data/db.py` 顶部添加：

```python
import json
```

- [ ] **Step 4: 测试**

Run: `cd /Users/chenyanyu/DoSomeThing/gold-dashboard && python -c "import asyncio; from backend.data.db import init_db; asyncio.run(init_db()); print('done')"`

Expected: 无报错，数据库初始化成功

---

### Task 2: Claude CLI 调用模块

**Files:**
- Create: `backend/data/sources/briefing.py`

- [ ] **Step 1: 创建 briefing.py**

```python
"""Claude CLI 调用生成金价简报。"""
import subprocess
import logging
from datetime import datetime, timezone, timedelta

from backend.data.db import save_briefing

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))


PROMPT_TEMPLATE = """你是一位专业的黄金市场分析师。请根据以下最近1小时的相关新闻，生成一份简洁有力的金价分析简报。

【相关新闻】（共 {news_count} 条）
{news_list}

【要求】
1. 总结新闻反映的主要驱动因素（地缘政治、美元、利率等）
2. 指出最值得关注的1-2个事件
3. 给出你对短期金价走势的判断（偏多/偏空/中性）
4. 提示纸黄金投资者应注意什么

用中文回答，简洁有力，不超过200字。禁止使用<think>或</think>等推理标记。"""


def call_claude_cli(prompt: str) -> str:
    """调用 claude -p 命令，返回简报文本。"""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=120, env={**__import__("os").environ},
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
```

- [ ] **Step 2: 测试（可选，手动验证）**

Run: `cd /Users/chenyanyu/DoSomeThing/gold-dashboard && python -c "from backend.data.sources.briefing import call_claude_cli; print(call_claude_cli('用一句话分析黄金后市，走势偏多还是偏空？'))"`

Expected: Claude CLI 输出（需登录认证）

---

### Task 3: 调度任务接入

**Files:**
- Modify: `backend/alerts/checker.py`

- [ ] **Step 1: 新增 _generate_briefing 任务**

在 `backend/alerts/checker.py` 顶部添加 import：

```python
from backend.data.sources.briefing import generate_briefing_from_news
from datetime import datetime, timezone, timedelta
```

在 `start_scheduler` 函数中添加每小时调度：

```python
scheduler.add_job(
    _generate_briefing_scheduled,
    'interval', hours=1,
    id="briefing_hourly",
    next_run_time=datetime.now(timezone(timedelta(hours=8))),  # 启动时立即运行一次
)
```

在 `get_cached_news()` 函数后添加：

```python
async def _generate_briefing_scheduled():
    """每小时从最近1小时新闻生成简报。"""
    from backend.data.sources.international import BEIJING_TZ
    try:
        news = get_cached_news()
        if not news:
            logger.info("No cached news for briefing")
            return

        now = datetime.now(BEIJING_TZ)
        prev_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        hour_label = f"{prev_hour.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%H:%M')}"

        await generate_briefing_from_news(news, hour_label)
        logger.info(f"Briefing task completed for {hour_label}")
    except Exception as e:
        logger.warning(f"Briefing task error: {e}")
```

- [ ] **Step 2: 测试调度任务启动无报错**

Run: `cd /Users/chenyanyu/DoSomeThing/gold-dashboard && python -c "from backend.alerts.checker import start_scheduler; start_scheduler(99999); import time; time.sleep(3); print('OK')"`

Expected: 输出 "OK"，无 traceback

---

### Task 4: API 接口

**Files:**
- Modify: `backend/routers/price.py`

- [ ] **Step 1: 新增 /api/briefings 接口**

在 `backend/routers/price.py` 末尾添加：

```python
@router.get("/briefings")
async def get_briefings(limit: int = 24):
    """返回最近 limit 条 AI 简报，按时间倒序。"""
    from backend.data.db import get_recent_briefings
    briefings = await get_recent_briefings(limit)
    return {"briefings": briefings}
```

- [ ] **Step 2: 启动服务并测试**

Run: `cd /Users/chenyanyu/DoSomeThing/gold-dashboard && uvicorn backend.main:app --port 18000 &`（后台已运行，跳过）

Run: `curl -s http://localhost:18000/api/briefings | python -m json.tool | head -20`

Expected: `{"briefings": []}` 或有数据的 JSON 列表

---

### Task 5: 前端 Phase 1 临时区域

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/css/style.css`
- Modify: `frontend/js/app.js`

- [ ] **Step 1: 在 index.html 中 chart-section 之前添加简报区域**

在 `<section class="chart-section">` 之前添加：

```html
<!-- AI 简报区域 (Phase 1) -->
<section class="briefing-section" id="briefing-section">
  <div class="briefing-header">
    <span class="briefing-title">🤖 AI 简报</span>
    <button id="refresh-briefing-btn" class="briefing-refresh-btn">🔄 刷新</button>
  </div>
  <div id="briefing-list" class="briefing-list">
    <div class="briefing-loading">加载中...</div>
  </div>
</section>
```

- [ ] **Step 2: 在 style.css 中添加简报样式**

在 CSS 文件末尾添加：

```css
/* AI 简报样式 (Phase 1) */
.briefing-section {
  background: #1a1d27;
  border: 1px solid #2a2d37;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.briefing-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.briefing-title {
  font-size: 1em;
  font-weight: 600;
  color: #f0c040;
}

.briefing-refresh-btn {
  background: #2a2d37;
  border: 1px solid #3a3d47;
  border-radius: 6px;
  color: #e0e0e0;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 0.85em;
}

.briefing-refresh-btn:hover {
  background: #3a3d47;
}

.briefing-list {
  max-height: 300px;
  overflow-y: auto;
}

.briefing-item {
  border-bottom: 1px solid #2a2d37;
  padding: 10px 0;
}

.briefing-item:last-child {
  border-bottom: none;
}

.briefing-time {
  font-size: 0.75em;
  color: #888;
  margin-bottom: 4px;
}

.briefing-content {
  font-size: 0.9em;
  color: #d0d0d0;
  line-height: 1.6;
  white-space: pre-wrap;
}

.briefing-loading {
  color: #666;
  text-align: center;
  padding: 20px;
}

.briefing-empty {
  color: #666;
  text-align: center;
  padding: 20px;
}
```

- [ ] **Step 3: 在 app.js 中添加简报加载逻辑**

在 `window.addEventListener("DOMContentLoaded")` 之前添加：

```javascript
let briefings = [];

async function loadBriefings() {
  const list = document.getElementById("briefing-list");
  if (!list) return;
  try {
    const res = await fetch("/api/briefings");
    const data = await res.json();
    briefings = data.briefings || [];
    if (briefings.length === 0) {
      list.innerHTML = '<div class="briefing-empty">暂无简报，将于下一小时生成</div>';
      return;
    }
    list.innerHTML = briefings.map(b => `
      <div class="briefing-item">
        <div class="briefing-time">${b.time_range || b.generated_at}</div>
        <div class="briefing-content">${escapeHtml(b.content)}</div>
      </div>
    `).join("");
  } catch (e) {
    list.innerHTML = '<div class="briefing-empty">加载失败</div>';
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
```

- [ ] **Step 4: 在 DOMContentLoaded 中初始化简报加载**

在 `window.addEventListener("DOMContentLoaded", async () => {` 内添加为第一个语句：

```javascript
loadBriefings();
```

- [ ] **Step 5: 绑定刷新按钮**

在 `initControls()` 函数之后添加：

```javascript
document.getElementById("refresh-briefing-btn")?.addEventListener("click", loadBriefings);
```

- [ ] **Step 6: 验证**

访问 http://localhost:18000/，确认简报区域显示正常

---

## Phase 2 实现

### Task 6: 左右分栏布局替换

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/css/style.css`
- Modify: `frontend/js/app.js`

- [ ] **Step 1: 修改 index.html 布局**

删除 Phase 1 添加的 `<section class="briefing-section">`。
在 `news-section` 外层包裹分栏容器：

```html
<!-- 新闻 + 简报 左右分栏 -->
<section class="content-grid">
  <div class="briefing-column">
    <div class="briefing-column-header">🤖 AI 简报</div>
    <div id="briefing-list-col" class="briefing-list-col"></div>
  </div>
  <div class="news-column" id="news-section">
    <div class="news-header">
      <span class="news-title">📰 相关资讯</span>
      <span class="news-refresh" id="news-refresh-time"></span>
    </div>
    <div id="news-list" class="news-list">
      <div class="news-loading">加载中...</div>
    </div>
  </div>
</section>
```

- [ ] **Step 2: 更新 CSS**

删除 Phase 1 的 `.briefing-section` 样式，替换为：

```css
/* 左右分栏布局 */
.content-grid {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.briefing-column {
  background: #1a1d27;
  border: 1px solid #2a2d37;
  border-radius: 12px;
  padding: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.briefing-column-header {
  font-size: 1em;
  font-weight: 600;
  color: #f0c040;
  margin-bottom: 12px;
}

.briefing-list-col {
  overflow-y: auto;
  max-height: calc(100vh - 380px);
  flex: 1;
}

.briefing-item {
  border-bottom: 1px solid #2a2d37;
  padding: 10px 0;
}

.briefing-item:last-child {
  border-bottom: none;
}

.briefing-time {
  font-size: 0.75em;
  color: #888;
  margin-bottom: 4px;
}

.briefing-content {
  font-size: 0.88em;
  color: #d0d0d0;
  line-height: 1.6;
  white-space: pre-wrap;
}

.briefing-empty {
  color: #666;
  font-size: 0.9em;
  padding: 10px 0;
}

/* 响应式：移动端上下排列 */
@media (max-width: 768px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  .briefing-list-col {
    max-height: 300px;
  }
}
```

- [ ] **Step 3: 更新 app.js 渲染目标**

将 `loadBriefings` 中的 DOM ID 从 `briefing-list` 改为 `briefing-list-col`。

- [ ] **Step 4: 验证**

访问 http://localhost:18000/，确认左右分栏布局正常。

---

## 自查清单

完成 Phase 1 后，对照设计 spec 检查：

- [ ] `ai_briefings` 表已创建且永久存储
- [ ] 每小时调度任务已注册
- [ ] `/api/briefings` 返回正确 JSON
- [ ] 前端简报区域显示正常
- [ ] 不影响现有新闻列表功能
