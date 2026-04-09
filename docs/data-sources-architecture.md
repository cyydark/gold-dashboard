# 数据源架构文档

> 本文档说明 gold-dashboard 所有数据源的设计决策、数据流和模块关系。
> 与 `graphify` 知识图谱配套：图谱节点对应的 rationale 在此归档。

---

## 一、架构概览

```
外部网站（Sina/Binance/EastMoney/YFinance等）
        ↓ HTTP 请求
  backend/data/sources/*.py    ← 各数据源抓取模块
        ↓
  backend/api/routes/price.py   ← 动态路由，source → fetcher 映射
        ↓ REST
  frontend/PollingManager       ← 三通道轮询（价格 10s / 图表 30s / 新闻 30min）
        ↓ 回调 → EventBus
  frontend/js/app.js           ← 协调层
        ↓
  frontend/js/modules/         ← priceUpdate / newsUpdate / briefingUpdate
        ↓
  frontend/js/chart/GoldChart.js ← Chart.js 渲染
        ↓
  屏幕
```

---

## 二、价格数据源

### 2.1 插件化架构

所有数据源实现**相同接口**，切换只需改字典配置，无需改业务代码：

```python
# backend/api/routes/price.py
_XAU_FETCHERS = {
    "sina":    ("backend.data.sources.sina_xau",               "fetch_xauusd_realtime"),
    "comex":   ("backend.data.sources.sina_xau",               "fetch_xauusd_realtime"),
    "binance": ("backend.data.sources.binance_kline",         "fetch_xauusd_realtime"),
}
```

> **设计决策**：为什么用字典配置而不是类继承？
> 因为每个数据源返回字段名不同（`price` vs `close`），用 `fetchers[source]` 动态分发比抽象基类更简洁。

### 2.2 各数据源详情

#### 国际金价 XAUUSD

| source 参数 | 模块 | API | 说明 |
|------------|------|-----|------|
| `comex` | `sina_xau.py` | `hq.sinajs.cn` (hf_XAU) | 伦敦金，现货基准 |
| `binance` | `binance_kline.py` | `binance.com/api/v3/klines` | XAUTUSDT，5分钟K线 |
| `sina` | `sina_xau.py` | `hq.sinajs.cn` (hf_XAU) | 与 comex 同源，作为备用 |

> **设计决策**：`binance_kline` 用途？
> 仅用于**存储**（`fetch_xauusd_kline`），实时价由 `sina_xau` 提供。
> Binance 优点：5分钟K线数据最完整（~3.5天 × 288根）；缺点：XAUTUSDT 不是现货，有溢价/折价。

#### 国内金价 AU9999

| source 参数 | 模块 | API | 说明 |
|------------|------|-----|------|
| `au9999` | `sina_au9999.py` | `hq.sinajs.cn` (gds_AU9999) | 现货，实时快照 |
| `eastmoney` | `eastmoney_au9999_price.py` | `push2.eastmoney.com` (118.AU9999) | 东方财富现货，更新频率高 |
| `sina_au0` | `sina_au0_1m.py` | `stock2.finance.sina.com.cn` (AU0) | 上期所 AU0 期货，1分钟K线 |

#### 汇率 USDCNY

| source 参数 | 模块 | API | 说明 |
|------------|------|-----|------|
| `yfinance` | `yfinance_fx.py` | Yahoo Finance | 离岸人民币，5分钟粒度 |
| `sina` | `sina_fx.py` | `hq.sinajs.cn` (fx_susdcny) | 在岸人民币，实时快照 |

---

## 三、新闻数据源

### 3.1 健康检查

每个数据源在 `backend/api/routes/health.py` 中有对应的健康检查函数，
通过 `/api/health/sources` 统一返回各源状态（`ok`, `latency_ms`, `error`）。

### 3.2 数据源列表

| 数据源 | 模块 | 类型 | 说明 |
|--------|------|------|------|
| 新浪财经 | `sina_*.py` | 价格（复用） | 黄金/外汇实时价 |
| Aastocks | `aastocks.py` | 新闻 | 香港黄金新闻，SSR 页面 + 翻页 API |
| 富途牛牛 | `futu.py` | 新闻 | 要闻（SSR）+ 快讯，需 `Referer` 头 |
| 马新社 Bernama | `bernama.py` | 新闻 | 马来西亚黄加坡 gold futures 新闻 |
| CNBC | `cnbc.py` | 新闻 | 国际财经 |
| RSSHUB 本地 | `local_news.py` | 新闻 | RSSHUB 聚合，需本地 `localhost:18080` |

> **设计决策**：为什么需要多个新闻源？
> 单源容易因网站改版（HTML 结构变化、API 签名失效）静默断流。多源并行，任何一个活着就能展示新闻。

> **设计决策**：`local_news.py` 依赖 `localhost:18080` 是什么？
> RSSHUB（一个开源 RSS 服务），在本地或服务器上运行，将任意网页转为 RSS。
> 如果 RSSHUB 不可用，该源静默降级，不影响其他源。

---

## 四、AI 简报三层管道

```
新闻（多源合并）
    ↓
Layer 1: 新闻分析（当前金价方向、核心驱动）
    ↓（K线交叉验证）
Layer 2: 行情验证（新闻结论是否与实际走势吻合）
    ↓（Layer1+Layer2 汇总）
Layer 3: 金价预期（涨/跌、目标价位、触发条件）
```

### 4.1 三级缓存

| 层级 | TTL | 刷新条件 |
|------|-----|---------|
| 新闻 | 10 分钟 | 自动过期 |
| Layer 1 | 30 分钟 | 自动过期 |
| Layer 2 | 60 分钟 | 自动过期 |
| Layer 3 | 15 分钟 | 自动过期 |

> **设计决策**：为什么三层分开缓存而不是一起过期？
> 新闻变化最频繁（10min），技术面验证次之（60min），价格预测最慢（15min）。
> 分开缓存保证：新闻更新后 Layer1 立刻重跑，但 Layer2/3 可以复用旧 Layer1 结果。

### 4.2 LLM 调用

优先使用 **Anthropic 官方 Python SDK**（`ANTHROPIC_API_KEY`），无 key 时 fallback 到 `claude CLI`。

```python
# backend/services/briefing_llm.py
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
# SDK 自动处理重试、超时、错误分类
```

---

## 五、模块关系（与图谱对应）

```
backend/data/sources/
  ├── binance_kline.py      — 国际金价 K线存储 + 实时 ticker
  ├── sina_xau.py          — 伦敦金实时 + K线（复用 EastMoney）
  ├── sina_au9999.py        — 国内 AU9999 实时
  ├── sina_au0_1m.py        — 上期所 AU0 期货 1min K线
  ├── eastmoney_au9999.py   — 国内 AU9999 K线
  ├── eastmoney_au9999_price.py — 国内 AU9999 实时价格
  ├── eastmoney_xauusd.py   — COMEX 黄金期货 K线
  ├── yfinance_fx.py        — 离岸人民币
  ├── sina_fx.py            — 在岸人民币
  ├── briefing.py           — AI 简报 prompt 构建 + LLM 调用
  ├── bernama.py            — 马新社黄金新闻
  ├── futu.py               — 富途牛牛新闻
  ├── aastocks.py           — Aastocks 黄金新闻
  ├── cnbc.py               — CNBC 财经新闻
  └── local_news.py         — RSSHUB 聚合新闻

backend/services/
  ├── briefing_cache.py     — 三级缓存（news/L1/L2/L3）
  ├── briefing_llm.py       — LLM 调用封装（SDK + CLI fallback）
  ├── briefing_service.py   — 编排层 + SSE 流式输出
  └── news_service.py      — 新闻聚合（DB + scraper fallback）

backend/api/routes/
  ├── price.py              — 价格 + 图表 REST API（动态路由）
  ├── news.py               — 新闻 REST API
  ├── briefing.py           — AI 简报 REST API
  ├── briefing_sse.py       — AI 简报 SSE 流式 API
  └── health.py             — 数据源健康检查

frontend/js/
  ├── polling.js            — PollingManager（三通道轮询）
  ├── chart/
  │   ├── GoldChart.js      — Chart.js 双轴图表
  │   ├── plugins/hover.js  — 十字光标 + tooltip
  │   ├── plugins/zoom.js    — 滚轮缩放 + 拖拽平移
  │   └── utils/time.js     — 双时区时间格式化
  ├── modules/
  │   ├── priceUpdate.js    — 价格卡片渲染（动画、颜色分配）
  │   ├── newsUpdate.js     — 新闻列表渲染
  │   └── briefingUpdate.js  — AI 简报渲染 + SSE
  └── utils/
      └── eventBus.js        — 事件总线（替代 PollingManager 回调）
```

---

## 六、已知的孤立节点

以下模块在图谱中连接较少（0-1 条边），但不代表不重要：

| 模块 | 孤立原因 | 说明 |
|------|---------|------|
| `db.py` | 只被 `news_repo.py` 和 `briefing_repo.py` 直接调用 | SQLite 连接池，工具类 |
| `config.py` | 只被 `main.py` 导入 | Pydantic Settings，零依赖 |
| `limiter.py` | 只被 `main.py` 引用 | SlowAPI 限速器，注入到 app.state |
| `constants.py` | 只含宏定义 | `REFRESH_INTERVAL`、`CLI_TIMEOUT` |

> **行动项**：这些模块在后续迭代中应增加有意义的边：
> - `db.py` → 通过健康检查接口产生连接
> - `config.py` → 文档节点增加对各数据源模块的 `references` 边
