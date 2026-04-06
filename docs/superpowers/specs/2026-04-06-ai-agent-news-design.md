# AI 多 Agent 并发新闻搜索 + 金价分析

**日期**：2026-04-06
**项目**：gold-dashboard
**状态**：草稿

---

## 背景

现有新闻采集方案依赖固定 3 个新闻源（BERNAMA、富途、AASTOCKS），存在覆盖有限、噪音多、有延迟等问题。

新方案：AI 多 Agent 并发从 MiniMax 搜索金价相关新闻，完成后汇总分析。

---

## 架构

```
用户点击「刷新资讯」
        │
        ▼
┌──────────────────────────────────┐
│     briefing_service.py           │
│     asyncio.gather()             │
│     并发 3 个子 agent             │
└──────────┬───────────────────────┘
           │
  ┌────────┴────────┐
  ▼                 ▼
Agent A          Agent B
地缘政治          央行宏观
claude -p        claude -p
+MCP web_search  +MCP web_search
  │                 │
  │              Agent C
  │            市场动态
  │         claude -p
  │         +MCP web_search
  │            │
  └─────┬──────┘
        ▼
   去重 + 合并
        │
        ▼
 主分析 Agent
 claude -p
 MiniMax MCP
 搜索结果分析
        │
        ▼
 最新资讯（3路合并新闻列表）
 AI金价分析（主分析结果）
        │
        ▼
     前端展示
```

---

## MCP 配置

文件路径：`~/.claude/mcp_minimax.json`（项目级 MCP 配置）

```json
{
  "mcpServers": {
    "MiniMax": {
      "type": "stdio",
      "command": "/Users/chenyanyu/.local/bin/uvx",
      "args": ["minimax-coding-plan-mcp", "-y"],
      "env": {
        "MINIMAX_API_KEY": "<from env>",
        "MINIMAX_API_HOST": "https://api.minimaxi.com"
      }
    }
  }
}
```

调用方式：
```bash
claude -p "<prompt>"
  --mcp-config ~/.claude/mcp_minimax.json
  --dangerously-skip-permissions
  --output-format text
```

---

## 搜索维度与 Query

| Agent | 搜索 Query | 目标 |
|-------|-----------|------|
| A（地缘政治） | `黄金 地缘政治 战争 制裁 最新新闻` | 地缘风险驱动 |
| B（央行宏观） | `美联储 利率 央行 黄金 宏观 最新` | 货币政策影响 |
| C（市场动态） | `黄金价格 黄金ETF 黄金期货 行情 最新` | 市场情绪与技术面 |

每路返回 3-5 条新闻（标题+摘要+时间）。

---

## 搜索 Agent Prompt（子 agent）

```
你是一位黄金市场资讯搜索助手。请使用 web_search 工具搜索以下内容：

【搜索任务】
{query}

请返回 3-5 条最新相关新闻，每条包含：
- 标题
- 发布时间
- 内容摘要（50字以内）
- 原始链接（可选）

搜索要求：
1. 优先返回中文新闻，其次英文
2. 发布时间在近 7 天内
3. 内容必须与黄金价格直接相关

直接输出搜索结果，无需解释。
```

---

## 主分析 Agent Prompt

```
你是一位专业黄金市场分析师。基于以下从多个权威来源搜索到的最新新闻，请评估当前金价走势。

【搜索来源汇总】
{merged_news}

评估原则：
1. 时效性：越近期的新闻权重越高
2. 重要性分级：地缘政治/突发风险 ★★★ > 央行政策/宏观经济 ★★ > 市场情绪/技术面 ★
3. 综合判断，给出金价走势预期

请严格按以下4行格式输出，无任何解释、前言或分节符号：
【金价走势】震荡偏强/震荡偏弱/上涨/下跌/区间震荡——20字以内一句话概括核心逻辑
【重点关注】近期最值得关注的2-3条新闻（标注来源，30字以内）
★★★ 因素一（地缘政治/突发风险）：一句话影响分析
★★ 因素二（央行政策/宏观经济）：一句话影响分析
```

---

## 数据流

```
search_agent_A() ─┐
                  │
search_agent_B() ─┼─► merge_results() ──► analyze_agent() ──► 返回给前端
                  │
search_agent_C() ─┘
```

### 并发数量
- 3 个搜索 agent 并发执行（asyncio.gather）
- 主分析 agent 串行，等待所有搜索完成后执行

### 缓存策略
| 数据 | TTL | 说明 |
|------|-----|------|
| 新闻列表 | 10 分钟 | 搜索结果缓存，避免频繁调用 |
| AI 分析 | 30 分钟 | 较重，缓存更久 |

---

## API 端点

### `POST /api/news/refresh`

强制刷新新闻 + AI 分析。

- 并发 3 路搜索 → 合并 → 主分析
- 响应：新闻列表 + AI 分析内容

```json
{
  "news": [
    {
      "title": "国际金价突破4690美元",
      "source": "新浪财经",
      "published": "2026-04-06",
      "summary": "国际现货黄金...",
      "url": "https://..."
    }
  ],
  "analysis": {
    "content": "【金价走势】...\n★★★ 因素一..."
  },
  "news_count": 12
}
```

### `POST /api/briefings/briefing/refresh`

仅重新分析，不刷新新闻。

- 使用现有缓存的新闻列表
- 重新调用主分析 agent

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 单个搜索 agent 超时（30s） | 返回空列表，继续用其他 agent 结果 |
| 全部 agent 失败 | 返回缓存（如果有）；无缓存则返回 "搜索失败，请重试" |
| 主分析超时（60s） | 返回已合并的新闻，AI 分析区域显示 "分析生成中..." |
| MiniMax API 限流 | 指数退避重试，最多重试 3 次 |

---

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/data/sources/minimax_news.py` | 新增 | MiniMax MCP agent 封装：subprocess 调用 claude -p + MCP |
| `backend/services/briefing_service.py` | 重构 | asyncio 并发管理多 agent，结果合并，TTL 缓存 |
| `backend/api/routes/briefing.py` | 调整 | 端点参数确认 |
| `docs/superpowers/specs/2026-04-06-ai-agent-news-design.md` | 新增 | 本文档 |

---

## 依赖

- Claude Code CLI（已安装）
- MiniMax API Key（已配置）
- Python 3.11+ asyncio（标准库）
- 无新增 Python 依赖

---

## 成本估算

| 操作 | 调用次数 | Token 消耗 | 预估成本 |
|------|---------|-----------|---------|
| 搜索 A/B/C（并发） | 3 次/刷新 | ~500 input + ~300 output × 3 | ~忽略（MiniMax 搜索便宜） |
| 主分析 | 1 次/刷新 | ~2000 input + ~500 output | ~可忽略 |

MiniMax 搜索 API 按量计费，每次约 ¥0.01-0.05，每次刷新成本极低。
