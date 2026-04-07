# 数据源规范文档

**日期**：2026-04-06
**项目**：gold-dashboard

---

## 数据源总览

| 类型 | 用途 | 数据源 |
|------|------|--------|
| 新闻 | 最新资讯列表 | BERNAMA、富途牛牛、AASTOCKS、CNBC |
| 国内金价 | AU9999 实时 + K线 | Sina (AU9999 实时) / Eastmoney (K线) |
| 国际金价 | XAU/USD 实时 + K线 | Sina (实时+伦敦金) / Eastmoney (COMEX) / Binance |
| 汇率 | USDCNY 实时 + K线 | Sina / Yahoo Finance |

---

## 新闻源

### 1. BERNAMA

**文件**：`backend/data/sources/bernama.py`

**来源**：马来西亚国家通讯社 BernamaBiz 黄金期货新闻搜索页
`https://www.bernama.com/en/search_news.php?q=gold`

**数据格式**：
```python
{
    "title": str,        # 英文标题
    "title_en": str,     # 同上
    "url": str,          # 原始链接
    "source": str,      # "BERNAMA"
    "published_ts": int, # Unix UTC 时间戳
    "published": str,    # "YYYY-MM-DD"
}
```

**特点**：
- 英文新闻为主
- 关键词过滤：gold, XAU, silver, bullion 等
- TTL：5 分钟

---

### 2. 富途牛牛

**文件**：`backend/data/sources/futu.py`

**来源**：
- 要闻（重要新闻）：`https://news.futunn.com/zh/main`（SSR 嵌入 HTML）
- 快讯（7×24）：`/api/get-flash-list`（富途内部 API）

**数据格式**：
```python
{
    "title": str,        # 原文标题（中文优先）
    "title_en": str,     # 英文标题（如有）
    "url": str,          # 原始链接
    "source": str,       # "富途牛牛"
    "published_ts": int, # Unix UTC 时间戳
    "published": str,    # "YYYY-MM-DD"
}
```

**特点**：
- 中文新闻为主
- 黄金关键词双重过滤（标题 + 正文）
- 并发请求要闻 + 快讯，合并去重
- TTL：5 分钟

---

### 3. AASTOCKS

**文件**：`backend/data/sources/aastocks.py`

**来源**：AAStocks 财经网黄金新闻搜索
`https://www.aastocks.com/chinese/stocks/news/afn-search.aspx`

**数据格式**：
```python
{
    "title": str,        # 英文标题
    "title_en": str,     # 同上
    "url": str,          # 原始链接
    "source": str,       # "AASTOCKS"
    "published_ts": int, # Unix UTC 时间戳
    "published": str,    # "YYYY-MM-DD"
}
```

**特点**：
- 英文新闻为主
- 宽泛关键词过滤（gold 相关词汇）
- 排除噪音关键词（bitcoin, tesla 等）
- TTL：5 分钟

---

### 4. CNBC

**文件**：`backend/data/sources/cnbc.py`

**来源**：CNBC Commodities RSS JSON API
`https://search.cnbc.com/rs/search/combinedcms/view.json?partnerId=wrss01&id=10000664`

**数据格式**：
```python
{
    "title": str,        # 英文标题
    "title_en": str,     # 同上
    "url": str,          # 原始链接
    "source": str,       # "CNBC"
    "published_ts": int, # Unix UTC 时间戳
    "published": str,    # "YYYY-MM-DD"
}
```

**特点**：
- 英文新闻为主
- 关键词过滤：gold, XAU, silver, bullion 等
- 排除噪音关键词（bitcoin, cryptocurrency 等）
- TTL：5 分钟

---

## 价格数据源

### 4. 国内金价 — AU9999

**实时（Sina）**：`backend/data/sources/sina_au9999.py`
- 源：`hq.sinajs.cn`（symbol `gds_AU9999`）
- 品种：沪金 AU9999（SGE）
- 单位：CNY/g

**实时（Eastmoney）**：`backend/data/sources/eastmoney_au9999_price.py`
- 源：`push2.eastmoney.com`（secid `118.AU9999`）
- 品种：沪金 AU9999（SGE）
- 单位：CNY/g
- 涨跌额基于本地缓存计算

**K线**：`backend/data/sources/eastmoney_au9999.py`
- 源：`push2his.eastmoney.com`（secid `118.AU9999`）
- 品种：AU9999 分钟K线
- 用途：图表展示

---

### 5. 国际金价 — XAU/USD

**实时 + 伦敦金**：`backend/data/sources/sina_xau.py`
- 源：`hq.sinajs.cn`（symbol `hf_XAU`）
- 品种：伦敦金现货（London Fix）
- 单位：USD/oz

**COMEX 期货**：`backend/data/sources/eastmoney_xauusd.py`
- 源：`push2his.eastmoney.com`（secid `101.GC00Y`）
- 品种：COMEX 黄金期货主连 GC00Y
- 单位：USD/oz
- 用途：图表 K 线展示

---

### 6. 汇率 — USDCNY

**实时（Sina）**：`backend/data/sources/sina_fx.py`
- 源：`hq.sinajs.cn`（symbol `fx_susdcny`）
- 品种：在岸人民币 USDCNY
- 单位：CNY/USD

**K线（Yahoo Finance）**：`backend/data/sources/yfinance_fx.py`
- 源：Yahoo Finance `USDCNY=X`
- 品种：离岸人民币
- 用途：图表 K 线（5 分钟粒度，约 70 天历史）

---

## 数据模型规范

### NewsItem（新闻条目）

```python
{
    "title": str,        # 标题，优先中文，英文兜底
    "title_en": str,     # 英文标题（可选）
    "url": str,          # 原始链接，可为空
    "source": str,       # 来源名称（如 "BERNAMA"、"富途牛牛"）
    "published_ts": int, # Unix UTC 时间戳（北京时间 00:00 为当天）
    "published": str,    # "YYYY-MM-DD" 格式
}
```

### PriceBar（价格条）

```python
{
    "time": int,     # Unix UTC 时间戳（或 bar open 时间）
    "open": float,
    "high": float,
    "low": float,
    "close": float,
    "volume": float,  # 可选
}
```

### RealtimePrice（实时价格）

```python
{
    "price": float,   # 最新价
    "change": float,  # 涨跌额
    "pct": float,     # 涨跌幅（%）
    "open": float,    # 开盘价
    "high": float,    # 当日最高
    "low": float,     # 当日最低
    "unit": str,      # 单位："USD/oz" | "CNY/g" | "CNY/USD"
    "ts": int,        # Unix UTC 时间戳
}
```

---

## 通用规范

### 时间处理
- 所有时间统一使用北京时间（UTC+8）
- `published_ts` 存 Unix UTC 时间戳（`datetime.now(BEIJING_TZ).timestamp()`）
- `published` 存 `YYYY-MM-DD` 字符串用于展示

### 缓存
- 新闻源 TTL：300 秒（5 分钟）
- 价格实时数据：无缓存，每次请求直接抓取
- Briefing 缓存：新闻 10 分钟，AI 分析 1 小时

### 错误处理
- 单个新闻源失败不影响其他源（`try/except` 隔离）
- 价格请求失败返回 `{"error": "数据获取失败，请切换数据源"}`

### 新增数据源

1. 在 `backend/data/sources/` 创建新文件，命名规范：`{source}_{type}.py`
2. 实现标准接口（见下方"接口规范"）
3. 在 `news_service.py` 的 `_fetch_news_from_sources()` 或 `price.py` 的 fetchers dict 中注册
4. 前端选择器同步更新（`index.html`、`polling.js`）

### 接口规范

**新闻源**：
```python
def fetch_xxx_news() -> list[dict]:
    """返回新闻列表，每条格式见 NewsItem"""
```

**价格实时**：
```python
def fetch_xxx_realtime() -> dict | None:
    """返回 RealtimePrice 格式，失败返回 None"""
```

**价格K线**：
```python
def fetch_xxx_history() -> list[dict] | None:
    """返回 PriceBar 列表，失败返回 None"""
```
