# 流式 AI 分析接口设计

> **Goal:** 将三层 AI 分析从"全部生成完再返回"改为流式实时推送，用户最早 15-20 秒看到内容，同时合并 Layer 1+2 减少 AI 调用次数。

---

## 架构概览

```
浏览器                    FastAPI (SSE)                  Claude CLI
                          ┌──────────────────────────────┐
EventSource ─────────────► │ GET /api/briefings/stream    │
                          │   ?days=3                    │
                          │                              │
                          │  1. 检查缓存 → 有则直接返回   │
                          │     完成 JSON，跳过流式       │
                          │                              │
                          │  2. 无缓存 → 并发拉取：      │
                          │     - 新闻列表                │
                          │     - Kline 数据              │
                          │     - 当前价格                │
                          │                              │
                          │  3. 生成 Layer 1+2：        │
                          │     claude -p [prompt]        │
                          │     --output-format stream-json │
                          │     --verbose                 │
                          │     逐 token SSE推送给前端     │
                          │                              │
                          │  4. Layer 1+2完成后          │
                          │     并发生成 Layer 3         │
                          │     同上逐 token推送          │
                          │                              │
                          │  5. 全部推送完毕 → 存入缓存   │
                          └──────────────────────────────┘
```

---

## 接口设计

### GET /api/briefings/stream

**Query Params:**
- `days` (int, default=3): 分析天数

**Response:** `text/event-stream` (SSE)

每个事件格式：
```
event: token
data: {"block":"l12","chunk":"现在金价"}
```

```
event: token
data: {"block":"l12","chunk":"处于高位"}
```

Layer 分界标记：
```
event: block-done
data: {"block":"l12","done":true}

event: token
data: {"block":"l3","chunk":"预期方向"}
```

结束标记：
```
event: done
data: {"blocks":{"l12":"完整L12内容","l3":"完整L3内容"}}
```

**缓存命中时**（直接返回非流式）：
```
event: cached
data: {"blocks":{"l12":"...","l3":"..."}}
```

---

## 后端实现

### 文件改动

- **新增** `backend/api/routes/briefing_sse.py`
  - `GET /api/briefings/stream` SSE endpoint
  - FastAPI `StreamingResponse` with `text/event-stream`
  - 并发拉取新闻 + Kline + 价格
  - 构造合并 prompt（见下文）
  - `asyncio.create_subprocess_exec` 调用 `claude -p` 流式读取 stdout
  - 逐 token 解析 JSON line，SSE push
  - Layer 3 完成后存缓存

- **修改** `backend/services/briefing_service.py`
  - `get_streaming_briefing(days)` 生成器函数
  - `get_cached_briefing(days)` 返回缓存完整文本

### Layer 1+2 合并 Prompt

将原来 Layer 1 和 Layer 2 的两个独立 AI 调用合并为一个 Prompt，让 AI 同时输出新闻分析和行情验证：

```
用大白话分析黄金走势，结合新闻和实际行情数据。不要任何markdown格式。

【新闻来源】（共{news_count}条，当前金价 ${current_price} USD/oz）
{news_list}

【实际行情数据】
{kline_summary}

分两部分输出：

【分析结论】
...

【金价预期】
...
```

### Layer 3 Prompt（独立）

```
基于以上分析结论，给出最简单的判断：

【接下来涨还是跌】
说清楚。

【能涨/跌到多少】
给个大概区间。

【什么时候见效】
大概多久？

【什么情况下变卦】
最容易打破预期的一件事是什么？
```

前端收到 `【分析结论】` 之前的内容填入 L1/L2 block，`【金价预期】` 部分填入 L3 block（注意：L3 内容在流式推送 `【金价预期】` 标题后开始填充）。

前端收到 `【分析结论】` 之前的内容填入 L1/L2 block，之后填入 L3 block。

### SSE 推送实现

```python
async def stream_claude(prompt: str, block: str, queue: asyncio.Queue):
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={**os.environ},
    )
    async for line in proc.stdout:
        data = json.loads(line)
        if data.get("type") == "result":
            await queue.put(("token", block, data["result"]["text"]))
        elif data.get("type") == "subtype" and data.get("subtype") == "end":
            await queue.put(("done", block, None))
```

---

## 前端实现

### 渲染逻辑

```
1. 发起 EventSource("/api/briefings/stream?days=3")
2. 收到 cached 事件 → 直接渲染完整内容，跳过流式
3. 收到 token 事件 → 追加到对应 block 实时显示
4. 收到 block-done 事件 → 该 block 渲染完毕
5. 收到 done 事件 → 关闭 EventSource
```

### Block 结构（不变）

```html
<div id="block-l12">
  <div class="analysis-block__header">📊 新闻分析 + 行情验证</div>
  <div class="analysis-block__body" id="body-l12"></div>
</div>
<div id="block-l3">
  <div class="analysis-block__header">🎯 金价预期</div>
  <div class="analysis-block__body" id="body-l3"></div>
</div>
```

### 错误处理

- 超时 / 连接断开 → 显示"加载中断，重试？"按钮
- 任意 block 失败 → 降级显示已成功部分 + 失败提示

---

## 缓存策略

- **缓存 Key**: `f"briefing:{days}"`
- **缓存内容**: `{"l12": "...完整L12文本...", "l3": "...完整L3文本...", "news": [...], "ts": 1744000000}`
- **TTL**: 30 分钟（取 Layer 1 缓存时间）
- **命中时**: SSE 返回单个 `event: cached` 事件，前端直接渲染，不走流式

---

## 兼容性

- 保留 `GET /api/briefings/layer1`, `/layer2`, `/layer3` 三个独立 endpoint
- 供调试或未来单独按需加载使用
- 新建 `/api/briefings/stream` 替换前端默认调用路径

---

## 性能目标

- 无缓存首次加载: 15-25 秒开始看到内容（一次 AI 调用即开始流式）
- 有缓存命中: < 100ms 返回完整内容
- 相比现有方案（60 秒全黑屏），首屏体验从 60s → ~20s
