# 两层 AI 分析设计

## 目标

在现有单层新闻分析基础上，增加第二层行情交叉验证，输出更可靠的金价判断。

## 架构

```
新闻列表 ──→ [Step 1: 新闻分析] ──→ 初步结论
              (Claude CLI)            ↓
                                   [Step 2: 交叉验证]
Kline 数据 ←── [获取 Kline 数据]        (Claude CLI)
(binance 5M)       (并发)              ↓
                                 最终交叉验证结论
                                       ↓
                              前端分两段展示
```

外层并发、内层串行：
- Step 1 新闻分析 和 Kline 数据获取 **并发**执行
- Step 2 交叉验证 等 Step 1 结论出来后**串行**执行

## Step 1: 新闻分析

- **输入**：新闻标题列表
- **模型**：Claude CLI (`claude -p`)
- **输出**：初步新闻判断（利多/利空/中性 + 核心逻辑）
- **Prompt**：沿用现有 `DAILY_PROMPT_TEMPLATE`

## Step 2: 行情交叉验证

- **输入**：Step 1 结论 + Binance 5M K线聚合数据
- **模型**：Claude CLI (`claude -p`)
- **数据源**：Binance XAUTUSDT 5M K线（`binance_kline.fetch_xauusd_kline`）
- **聚合范围**：近 2 日
- **聚合格式**（输入 prompt）：
  - 每日开/收/高/低 + 涨跌幅
  - 整体趋势方向（上涨/下跌/震荡）
  - 波动幅度（最高-最低）
  - 尾盘走势（最后1-2小时方向）
- **输出**：
  - 一致 → "✓ 新闻判断与走势吻合"
  - 矛盾 → "⚠ 新闻判断与走势相悖，建议修正为..."
  - 信号不足 → "当前走势无明确方向，新闻判断暂作参考"

## 缓存策略

- 新闻 TTL：10 分钟（不变）
- 分析 TTL：1 小时（不变）
- Step 1 和 Step 2 共用同一 `_analysis_cache`，缓存键包含两部分结果

## API 响应

`/api/briefings` 返回结构：

```json
{
  "weekly": {
    "content": "Step 2 最终交叉验证结论",
    "news_analysis": "Step 1 新闻分析结果",
    "cross_validation": "Step 2 行情交叉验证结果"
  },
  "news": [...],
  "news_count": N
}
```

## 涉及文件

| 文件 | 改动 |
|------|------|
| `backend/data/sources/briefing.py` | 新增 Step 2 prompt + `generate_cross_validation()` |
| `backend/services/briefing_service.py` | 并发执行 Step1+Kline，顺序执行 Step2，合并返回两字段 |
| `frontend/js/app.js` | 渲染 `news_analysis` 和 `cross_validation` 两个区块 |
| `frontend/index.html` / CSS | 两段展示样式 |

## 错误处理

- Step 1 失败 → 返回 "新闻分析失败，暂无法生成简报"
- Kline 获取失败 → Step 2 降级为纯新闻分析
- Step 2 失败 → 返回 Step 1 结果，前端降级展示
