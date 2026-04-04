# 黄金简报 AI 功能设计方案

**日期**：2026-04-04
**状态**：Phase 1 独立测试

---

## 背景

现有项目（FastAPI + 前端图表）已有新闻列表。用户希望新增 AI 简报功能，由 Claude CLI 定时生成专业金价分析，永久存库，前端左右分栏展示。

---

## 阶段划分

### Phase 1：独立测试
- 新增数据库表、新增调度任务、新增 API 接口
- 前端用临时区域展示（不改动现有布局）
- 测试通过后进入 Phase 2

### Phase 2：替换布局
- 简报移到新闻列表上方，左右分栏
- 左侧 AI 简报，右侧新闻列表

---

## 数据库设计

### 表：ai_briefings

```sql
CREATE TABLE IF NOT EXISTS ai_briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,           -- AI 生成的简报内容
    news_count INTEGER DEFAULT 0,    -- 本次分析的新闻条数
    news_titles TEXT,                -- 本次分析的新闻标题（JSON 数组）
    time_range TEXT,                 -- 本次分析的时间范围，如 "2026-04-04 09:00 ~ 10:00"
    generated_at TEXT NOT NULL,      -- 简报生成时间
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 后端设计

### 新增文件

- `backend/data/sources/briefing.py` — 调用 Claude CLI 生成简报

### 修改文件

- `backend/data/db.py` — 新增 `init_db` 建表语句、新增 `save_briefing` / `get_recent_briefings` 函数
- `backend/alerts/checker.py` — 新增每小时调度任务
- `backend/routers/price.py` — 新增 `/api/briefings` 接口

### 调度流程

```
每小时触发
  → fetch_recent_news(hours=1)  # 拉最近1小时新闻
  → build_prompt(news)          # 组装 prompt
  → call_claude_cli(prompt)     # 调用 Claude CLI
  → save_briefing(result)       # 存入 DB
```

### Prompt 设计

```
你是一位专业的黄金市场分析师。请根据以下最近1小时的相关新闻，生成一份简洁有力的金价分析简报。

【相关新闻】（共 N 条）
1. [来源] 新闻标题
2. [来源] 新闻标题
...

【要求】
1. 总结新闻反映的主要驱动因素（地缘政治、美元、利率等）
2. 指出最值得关注的1-2个事件
3. 给出你对短期金价走势的判断（偏多/偏空/中性）
4. 提示纸黄金投资者应注意什么

用中文回答，简洁有力，不超过200字。禁止使用<think>或</think>等推理标记。
```

### Claude CLI 调用方式

```python
import subprocess

def call_claude_cli(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        capture_output=True, text=True, timeout=60
    )
    # 解析返回，提取简报内容
```

### API 接口

**GET /api/briefings**

返回最近简报 + 近1小时新闻：

```json
{
  "briefings": [
    {
      "id": 1,
      "content": "简报内容...",
      "news_count": 5,
      "time_range": "09:00~10:00",
      "generated_at": "2026-04-04T10:00:00"
    }
  ],
  "news": [
    {
      "title": "新闻标题",
      "source": "来源",
      "published_at": "2026-04-04T15:30:00+08:00",
      "url": "https://..."
    }
  ],
  "time_window": "15:30~16:30"
}
```

- `briefings`：最近简报（日报 + 每小时简报），按生成时间倒序
- `news`：近1小时新闻（后端按 `published_at >= now-1h` 过滤），按发布时间倒序
- `time_window`：近1小时时间段标签

---

**POST /api/news/refresh**

手动抓取新闻并入库，无请求体，返回：

```json
{"count": 100, "message": "抓取到 100 条新闻已入库"}
```

---

## 前端设计

### Phase 1（测试阶段）

- 在现有页面底部或顶部新增临时区域
- 手动刷新按钮，调用 `/api/briefings` 展示
- 不改动现有布局

### Phase 2（替换阶段）

**布局**：左右分栏

```
┌─────────────────────────────────────────────────────────┐
│                    黄金行情 + 价格卡片                    │
├──────────────────────────┬────────────────────────────┤
│   🤖 AI 简报（左侧）      │   📰 相关资讯（右侧）         │
│                          │                             │
│  [今天 10:00]            │  10:30  来源  📈 金价升     │
│  简报内容...              │  新闻标题                    │
│                          │                             │
│  [今天 09:00]            │  09:15  来源  📉 金价降     │
│  简报内容...              │  新闻标题                    │
│  ...                     │  ...                        │
└──────────────────────────┴────────────────────────────┘
```

**样式**：
- 左右两栏，固定高度，可滚动
- 每条简报带时间标签
- 简报内容可折叠/展开
- 响应式：移动端上下排列

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/data/db.py` | 修改 | 新增表、新增函数 |
| `backend/alerts/checker.py` | 修改 | 新增每小时调度任务 |
| `backend/routers/price.py` | 修改 | 新增 `/api/briefings` 接口 |
| `frontend/index.html` | 修改 | Phase 2 左右分栏布局 |
| `frontend/js/app.js` | 修改 | 获取并渲染简报数据 |
| `frontend/css/style.css` | 修改 | 分栏样式 |

---

## 依赖

- Claude CLI（需安装并登录）
- 无需新增 Python 依赖
