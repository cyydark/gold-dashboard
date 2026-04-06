# 实时金价·汇率·图表架构重构设计

**日期：** 2026-04-06
**状态：** 设计中
**目标：** 去掉数据库（SQLite），所有子系统改为纯 REST + 内存缓存驱动

---

## 1. 设计原则

1. **无 DB** — 不使用 SQLite，不使用 ORM，无持久化存储
2. **完全独立** — 三张卡片 + 图表各自独立，互不干扰
3. **后端职责单一** — 后端只做数据获取和格式化，失败直接返回错误，不重试，不 fallback
4. **前端兜底** — 前端负责轮询、失败提示、用户选择持久化
5. **权威排序** — 各数据源按权威性 + 稳定性排序，用于默认选择和失败提示

---

## 2. 系统架构

```
数据源 ──→ 后端 API（轻量，无 DB）──→ 前端 PollingManager ──→ UI

各子系统独立轮询，独立记忆用户选择（localStorage）
```

---

## 3. 子系统详细设计

### 3.1 卡片实时价格

**轮询间隔：** 10 秒

| 卡片 | 端点 | 可选源 |
|------|------|--------|
| XAU/USD | `GET /api/realtime/xau/{source}` | comex, metals, sina, binance, omkar |
| AU9999 | `GET /api/realtime/au/{source}` | au9999, sina, autd, akshare |
| USDCNY | `GET /api/realtime/fx/{source}` | yfinance, sina |

**返回格式：**
```json
{
  "price": 4722.5,
  "change": 15.3,
  "pct": 0.32,
  "open": 4710.0,
  "high": 4730.0,
  "low": 4705.0,
  "unit": "USD/oz",
  "ts": 1743891600
}
```

**失败处理：** 返回 HTTP 500 + 错误信息，前端显示上一次成功数据 + 错误提示，允许用户手动切换源。

---

### 3.2 图表历史K线

**轮询间隔：** 30 秒

| 图表线 | 端点 | 可选源 |
|--------|------|--------|
| XAU/USD | `GET /api/chart/xau?source=comex` | comex, sina, metals, binance, omkar |
| AU9999 | `GET /api/chart/au?source=au9999` | au9999, sina, autd, akshare |

**返回格式（近72小时5分钟K线）：**
```json
{
  "bars": [
    { "time": 1743891000, "open": 4710.0, "high": 4715.0, "low": 4708.0, "close": 4712.0 },
    ...
  ]
}
```

**实时更新：** 每次轮询时，用最新价格补入当前正在形成的5分钟K线。

**废弃旧端点：** `GET /api/history/{symbol}` → 删除

---

### 3.3 SSE 废弃

**删除端点：** `GET /stream`

前端不再使用 SSE，全部替换为 REST 轮询。

---

### 3.4 新闻列表

**缓存 TTL：** 30 分钟

**端点：** `GET /api/news`

- 数据来源：各新闻 RSS/API（新浪财经、东方财富等）
- 存储：Python dict + 时间戳，无持久化
- 首次请求或缓存过期时抓取，否则返回缓存
- 前端可手动刷新

---

### 3.5 AI 周报

**缓存 TTL：** 1 小时

**端点：** `GET /api/briefings?days=3`

- 数据来源：基于新闻列表内容调用 LLM 分析
- 存储：Python dict + 时间戳，无持久化
- 首次请求或缓存过期时重新分析，否则返回缓存
- 前端显示缓存时间戳

---

## 4. 数据源权威性排序

### XAU/USD（USD/oz）
1. **COMEX** — 纽约商品期货交易所，黄金期货GC00Y，最权威
2. **LBMA (Metals-API)** — 伦敦金银市场协会每日定盘价，权威但非实时
3. **Sina 伦敦金** — 新浪 hf_XAU，国内访问稳定
4. **Binance XAUTUSDT** — 币安金本位合约，流动性好，实时
5. **CME (Omkar)** — 芝加哥商业交易所，需要 API Key

### AU9999（CNY/g）
1. **东方财富 AU9999** — 实物黄金现货，国内最权威现价
2. **Sina AU9999** — 新浪 Au99.99，备用
3. **黄金 T+D** — 上海金交所延期合约
4. **沪金期货 AU0 (AkShare)** — 沪期货主力合约

### USDCNY
1. **yfinance** — 美元兑离岸人民币，广泛使用
2. **Sina** — 新浪在岸汇率，国内访问稳定

> 排序用于：首次加载默认值 + 用户切换失败时提示下一个可用源

---

## 5. 前端 PollingManager

```javascript
class PollingManager {
  // 三个独立 timer，互不干扰
  pollCard(source, callback)      // 10 秒
  pollChart(source, callback)     // 30 秒
  pollNews(callback)              // 30 分钟

  // localStorage 持久化用户选择
  saveSource(key, source)
  loadSource(key)  // 无值则用默认排序第一个
}
```

**卡片切换逻辑：**
- 用户切换源 → 更新 localStorage → 停止当前轮询 → 启动新源轮询
- 切换失败 → 显示错误提示 + 建议切换到排序中的下一个源

---

## 6. 后端需要改造的文件

| 文件 | 改动 |
|------|------|
| `backend/api/routes/sse.py` | **删除整文件**，迁移 `GET /api/realtime/{xau,au,fx}/{source}` 到 price.py |
| `backend/api/routes/price.py` | 新增 `/api/chart/{xau,au}` 端点；保留 `/api/briefings` 改为内存缓存 |
| `backend/api/routes/news.py` | 改为内存缓存，无 DB |
| `backend/services/price_service.py` | 移除 DB 依赖，纯转发源模块数据 |
| `backend/data/sources/*.py` | 不变，继续使用 |
| `backend/data/db.py` | **删除** |
| `backend/data/models.py` | **删除** |

---

## 7. 需要确认的残留依赖

以下功能需在实现前确认 scope：

- [ ] `alerts.db`（已有 `.gitignore`，确认不再需要后删除相关代码）
- [ ] 历史数据超过72小时的查看需求（无 DB 则无法保留）

---

## 8. 不在此次重构范围

- 新闻抓取的具体源选择（保持现有逻辑）
- AI 周报的分析 Prompt 逻辑
- 前端 UI 样式和交互（仅重构数据层）
