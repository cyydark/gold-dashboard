# AI 三层分析提示词设计

**日期**: 2026-04-08
**状态**: 已批准
**目标**: 重新设计 AI 分析的两段提示词为三层递进架构

---

## 1. 背景与目标

现有系统只有两层分析（新闻分析 + 交叉验证），两者并列展示，用户无法感知认知递进关系。
本次改版将扩展为三层，层层递进，最终输出一个带有置信度的综合金价预期。

---

## 2. 整体架构

```
Layer 1: 新闻分析
  输入: 新闻标题 + 发布时间 + 当前金价
  输出: 结构化新闻叙事报告
         ↓ Layer 1 结论（作为 Layer 2 输入）
Layer 2: 行情交叉验证
  输入: Layer 1 输出 + Binance Kline 聚合数据
  输出: 结构化验证报告（一致/矛盾/信号不足）
         ↓ Layer 1 + Layer 2 结论（作为 Layer 3 输入）
Layer 3: 金价预期
  输入: Layer 1 + Layer 2 完整输出
  输出: 前瞻性预测报告（方向 + 目标价 + 置信度）
```

三层**顺序执行**，最终展示 Layer 2 + Layer 3，Layer 1 作为底层依据（可折叠）。

---

## 3. Layer 1 — 新闻分析

### 3.1 输入

| 字段 | 来源 | 说明 |
|------|------|------|
| `news_list` | 新闻服务 | 近 3 日标题列表，每条含 title + published_ts |
| `current_price` | Binance ticker | XAUUSD 当前价格，注入 prompt |

### 3.2 Prompt 模板

```
你是一位专业黄金市场分析师。基于近3日{news_count}条新闻（当前金价 ${current_price} USD/oz），请评估当前金价走势。

{news_list}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【走势判断】
上涨/震荡/下跌——逻辑一句话

【核心驱动】
★★★ 地缘/风险：（一行）
★★ 央行/宏观：（一行）
★ 市场/技术：（一行）

【时效性】
近24h重点新闻对走势的影响权重说明

【置信度】
高/中/低，理由一句话
```

### 3.3 输出格式约束

- 每行以 `【】` 分区标识开头
- 无 Markdown 格式
- 中文输出
- 空格和换行严格按模板

---

## 4. Layer 2 — 行情交叉验证

### 4.1 输入

| 字段 | 来源 | 说明 |
|------|------|------|
| Layer 1 输出 | 全文 | 结构化新闻分析报告 |
| Kline 聚合数据 | Binance 5M K线 | 经 `aggregate_kline_for_prompt()` 处理 |

### 4.2 Prompt 模板

```
你是一位专业黄金市场分析师。请将以下 Layer 1 新闻分析结论与 Layer 2 实际行情数据进行交叉对比，判断新闻判断是否与实际走势吻合。

【Layer 1 - 新闻分析结论】
{layer1_output}

【Layer 2 - Binance XAUUSD 日线聚合数据（5M K线）】
{kline_summary}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【验证结果】
一致 / 矛盾 / 信号不足

【实际走势】
从 Kline 数据提取的趋势描述（一句话）

【分歧说明】
如验证结果为"矛盾"，说明新闻预判与实际走势的差异；否则留空或写"无明显分歧"

【验证置信度】
高/中/低，理由一句话
```

---

## 5. Layer 3 — 金价预期

### 5.1 输入

| 字段 | 来源 | 说明 |
|------|------|------|
| Layer 1 输出 | 全文 | 新闻叙事报告 |
| Layer 2 输出 | 全文 | 验证结果报告 |

Layer 3 **必须**以 Layer 1 + Layer 2 为主要输入，不得单独依赖新闻或 Kline 数据。

### 5.2 Prompt 模板

```
你是一位专业黄金市场分析师。基于以下 Layer 1 新闻分析与 Layer 2 行情验证的结论，给出短期金价走势预期。

【Layer 1 - 新闻分析结论】
{layer1_output}

【Layer 2 - 行情验证结论】
{layer2_output}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【方向预期】
短期（1-3日）方向：上涨/震荡/下跌，理由一句话

【价格目标】
支撑位：XXX USD/oz
压力位：XXX USD/oz

【时间框架】
预期生效窗口：X-X日

【风险提示】
可能推翻预期的关键事件（1-2条）

【综合置信度】
高/中/低
理由：基于 Layer 2 验证一致性（或矛盾程度）说明
```

---

## 6. 调用流程（Python）

```python
# Step 1: Layer 1 — 新闻分析（并发获取 Kline）
news_analysis = await generate_daily_briefing_from_news(news)
kline_data = await fetch_kline()  # asyncio.to_thread

# Step 2: Layer 2 — 交叉验证
cross_validation = await generate_cross_validation(news_analysis, kline_data)

# Step 3: Layer 3 — 金价预期（依赖前两层）
price_forecast = await generate_price_forecast(news_analysis, cross_validation)
```

三层均为 `async def`，通过 `call_claude_cli()` 调用 `claude -p` 命令。

---

## 7. 前端展示调整

### 7.1 三区块结构

| 区块 | 对应层级 | 顺序 | 样式 |
|------|---------|------|------|
| 🎯 金价预期 | Layer 3 | 最上方 | 重点展示，含目标价、置信度 |
| 📊 行情验证 | Layer 2 | 中间 | 金色主色调，高亮展示 |
| 📰 新闻分析 | Layer 1 | 最下方 | 灰色背景，默认收起，点击展开 |

### 7.2 展示优先级（3 → 2 → 1）

- **Layer 3（金价预期）**：最上方，重点展示，含方向、支撑/压力位、综合置信度
- **Layer 2（行情验证）**：中间，高亮展示，含验证结果、实际走势、验证置信度
- **Layer 1（新闻分析）**：最下方，灰色背景，默认收起，用户点击展开查看详情

综合置信度以颜色/图标高亮（金色 = 高，橙色 = 中，灰色 = 低）

### 7.3 API 响应格式

```json
{
  "weekly": {
    "layer3_price_forecast": "【方向预期】...",
    "layer2_cross_validation": "【验证结果】...",
    "layer1_news_analysis": "【走势判断】...",
    "confidence": "高/中/低",
    "time_range": "04月05日 - 04月08日",
    "news_count": 74
  }
}
```

---

## 8. 错误处理

| 场景 | 降级行为 |
|------|---------|
| Layer 1 失败 | 返回"暂无新闻分析"，Layer 2/3 跳过 |
| Layer 2 Kline 获取失败 | Layer 2 降级为"信号不足"，Layer 3 仍可运行（置信度降为"低"）|
| Layer 3 失败 | 返回空，Layer 1+2 仍展示 |

---

## 9. 实施清单

- [ ] 修改 `backend/data/sources/briefing.py`：新增 `PRICE_FORECAST_TEMPLATE` 和 `generate_price_forecast()`
- [ ] 修改 `backend/services/briefing_service.py`：三层调用流程，`_generate_analysis` 扩展为三层
- [ ] 修改 `frontend/js/app.js`：三区块 DOM 渲染，调整 `_showBriefing()` 
- [ ] 修改 `frontend/index.html`：新增"金价预期"区块 DOM
- [ ] 修改 `frontend/css/style.css`：Layer 1 收起样式、Layer 3 展示样式
- [ ] 更新 `backend/api/routes/briefing.py`：API 响应格式对齐新字段
- [ ] 测试：三层均正常输出，前端三区块正确渲染
