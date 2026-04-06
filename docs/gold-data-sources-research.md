# 金价数据源调研报告

> 调研时间：2026-04-06
> 目的：为国际金价和国内金价寻找更合适的数据源

---

## 一、当前项目数据源

### 1.1 国际金价 (XAU/USD)

| 数据源 | 模块 | API | 问题 |
|--------|------|-----|------|
| COMEX 黄金期货主连 | `eastmoney_xauusd.py` | `push2his.eastmoney.com` (101.GC00Y) | 期货主连，非现货；仅 ~2 交易天数据 |
| Binance XAUTUSDT | `binance_kline.py` | `binance.com/api/v3/klines` | 代币化黄金信托，有溢价/折价；仅 ~3.5 天数据 |

### 1.2 国内金价 (AU9999)

| 数据源 | 模块 | API | 状态 |
|--------|------|-----|------|
| SGE AU9999 | `eastmoney_au9999.py` | `push2.eastmoney.com` (118.AU9999) | ✅ 稳定，SGE 现货基准 |

### 1.3 汇率 (USDCNY)

| 数据源 | 模块 | API | 问题 |
|--------|------|-----|------|
| Yahoo Finance | `yfinance_fx.py` | yfinance 库 | 依赖第三方库，Yahoo API 不稳定 |

---

## 二、参考项目数据源分析

### 2.1 来源

> GitHub: `PiaoyangGuohai1/GoldPrice` — `Sources/main.swift`

### 2.2 Swift 项目数据源

| 数据源 | API 端点 | 数据类型 | 状态 |
|--------|----------|----------|------|
| 民生银行金价 | `api.jdjygold.com/gw/generic/hj/h5/m/latestPrice` | 银行零售金条价 | ✅ 可用，但溢价 5% |
| 工商银行金价 | `api.jdjygold.com/gw2/.../icbcLatestPrice?productSku=2005453243` | 银行零售金条价 | ✅ 可用 |
| 浙商银行金价 | `api.jdjygold.com/gw2/.../stdLatestPrice?productSku=1961543816` | 银行零售金条价 | ✅ 可用 |
| 国际金价（伦敦金） | `hq.sinajs.cn/list=hf_XAU,hf_GC` | Tick 快照 | ⚠️ 需 Referer 头 |

### 2.3 Sina `hf_XAU` 完整字段

```
GET https://hq.sinajs.cn/list=hf_XAU,hf_GC
Header: Referer: https://finance.sina.com.cn

返回格式:
var hq_str_hf_XAU="4675.99,4675.99,4670.50,4685.30,4662.10,4662.10,20260406 15:30:00,4675.99";
```

| 索引 | 字段 | 示例值 | 说明 |
|------|------|--------|------|
| 0 | 当前价 | 4675.99 | USD/盎司 |
| 1 | 昨收价 | 4675.99 | 主要昨收 |
| 2 | 开盘价 | 4670.50 | 今日开盘 |
| 3 | 最高价 | 4685.30 | 今日最高 |
| 4 | 最低价 | 4662.10 | 今日最低 |
| 5 | 最低价2 | 4662.10 | 备用 |
| 6 | 时间戳 | 20260406 15:30:00 | 数据时间 |
| 7 | 昨收价备份 | 4675.99 | 与 parts[1] 一致 |

**Swift 项目实际提取**：price, yesterdayPrice, changeAmount, changeRate（均从上述字段计算）

### 2.4 `hf_XAU` vs `hf_GC` 对比

| 字段 | `hf_XAU` | `hf_GC` |
|------|----------|---------|
| 名称 | 伦敦金（现货） | 纽约金（期货） |
| 单位 | USD/盎司 | USD/盎司 |
| 数据性质 | 新浪换算现货价 | COMEX 期货价格 |

### 2.5 `hf_XAU` 局限性

- ✅ 当前价格
- ✅ 开盘/最高/最低/昨收
- ✅ 数据时间
- ✅ 涨跌幅（可计算）
- ❌ **历史 K 线数据** — 无，仅单点快照
- ❌ 成交量
- ❌ 买价/卖价 (Bid/Ask)
- ❌ 需加 Referer 请求头

> **结论**：`hq.sinajs.cn/list=hf_XAU` 只提供实时 Tick 数据，**不提供 K 线历史数据**，无法用于绘制图表。

### 2.6 京东金融银行金价局限性

银行 API（如 `jdjygold.com`）返回的是**银行零售金条价格**，而非 SGE 大盘现货价：

| 类型 | 价格 | 差异 |
|------|------|------|
| SGE AU9999 现货 | ~979 元/克 | 基准 |
| 银行零售金条 | ~1033 元/克 | 溢价 ~5.5% |

不适合作为"国内金价大盘价"，仅适合展示银行渠道零售价。

---

## 三、可选替代数据源

### 3.1 国际金价

| 优先级 | 数据源 | 数据类型 | 免费额度 | 备注 |
|--------|--------|----------|----------|------|
| ⭐ 1 | **Metals-API** | LBMA Gold AM/PM，每日两次定盘 | 100 请求/月 | 权威现货基准，需注意请求频率 |
| ⭐ 2 | **Metals.dev** | LBMA Gold AM/PM + 5年历史 | 100 请求/月 | 更稳定，1.49$/月起 |
| 3 | MetalpriceAPI | LBMA Gold | 注册免费 | 官方标注"Delayed market data" |
| 4 | Sina `hf_XAU` | Tick 快照 | 无限制 | 需加 Referer 头，仅实时价无K线 |

> **推荐**：LBMA Gold Price 是全球黄金现货的权威基准价，每天 10:30 AM 和 3:00 PM 伦敦时间两次定盘。

### 3.2 国内金价

| 优先级 | 数据源 | 数据类型 | 免费额度 | 备注 |
|--------|--------|----------|----------|------|
| ⭐ 1 | **EastMoney SGE AU9999**（当前） | SGE 现货，实时 | 无限制 | ✅ 最优，保留 |
| 2 | 极速数据 (jisuapi.com) | SGE + SHFE 多品种 | 100 次/天 | 需注册，有限额 |

> 国内银行零售 API（jdjygold.com）**不适合**作为大盘价使用。

### 3.3 汇率

| 优先级 | 数据源 | 备注 |
|--------|--------|------|
| ⭐ 1 | Metals-API / Metals.dev（同一 API） | 同来源减少依赖 |
| 2 | exchangerate.host | 100/月，免费 |
| 3 | yfinance（当前） | 备选，依赖较少 |

---

## 四、建议方案

### 短期（不换架构，立即可用）

```
国际金价:
  主: EastMoney COMEX GC00Y (当前) ← K线数据，保留
  备: Sina hf_XAU ← 实时价格补充，需加 Referer 头

国内金价:
  主: EastMoney SGE AU9999 (当前) ← SGE现货，最优，保留

汇率:
  续用 yfinance USDCNY
```

### 中期（更稳定的数据质量）

```
国际金价:
  主: Metals-API LBMA Gold AM/PM ← 权威现货基准
  备: EastMoney COMEX GC00Y ← K线保留

国内金价:
  保持 EastMoney SGE AU9999

汇率:
  改用 Metals-API 或 exchangerate.host
```

> ⚠️ Metals-API 免费额度 100/月，按 6 分钟刷新间隔计算约 240 次/天，不够用。需降低刷新频率（如 15-30 分钟）或升级付费方案。

---

## 五、Sina hf_XAU 接入方式

```python
import requests

def fetch_sina_xau():
    headers = {"Referer": "https://finance.sina.com.cn"}
    resp = requests.get(
        "https://hq.sinajs.cn/list=hf_XAU,hf_GC",
        headers=headers,
        timeout=10
    )
    resp.encoding = "gbk"
    text = resp.text
    # 解析 hf_XAU（伦敦金）
    # parts[0]=当前价, [1]=昨收, [2]=开盘, [3]=最高, [4]=最低, [6]=时间
    return text
```

> 注意：直接 GET 不带 Referer 会返回 403 Forbidden。

---

## 六、第三个参考项目数据源分析

### 6.1 来源

> GitHub: `wooship/GoldPriceApp` — `GoldApiComService.kt`

### 6.2 数据源

**Base URL**: `https://api.gold-api.com/`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/price/{symbol}` | GET | ❌ 无需 | 实时价格 |
| `/history/XAU` | GET | ✅ 需要 `x-api-key` | 历史价格 |
| `/symbols` | GET | ❌ 无需 | 可用品种列表 |
| `/ohlc/XAU` | GET | ✅ 需要 `x-api-key` | OHLC 数据 |

### 6.3 可用品种（无需认证）

| 品种代码 | 名称 | 类型 |
|----------|------|------|
| XAU | Gold | 贵金属 |
| XAG | Silver | 贵金属 |
| XPT | Platinum | 贵金属 |
| XPD | Palladium | 贵金属 |
| HG | Copper | 工业金属 |
| BTC | Bitcoin | 加密货币 |
| ETH | Ethereum | 加密货币 |
| 20 个货币对 | — | 外汇 |

### 6.4 实时价格响应 (`/price/XAU`)

```json
{
  "currency": "USD",
  "currencySymbol": "$",
  "exchangeRate": 1.0,
  "name": "Gold",
  "price": 4672.60,
  "symbol": "XAU",
  "updatedAt": "2026-04-06T02:22:15Z",
  "updatedAtReadable": "a few seconds ago"
}
```

**可用字段**：当前价格、货币、汇率、时间戳

**缺失字段**：
- ❌ 开盘价 / 最高价 / 最低价
- ❌ 成交量
- ❌ 昨收价
- ❌ K 线历史
- ❌ CNY 换算（`?currency=CNY` 返回 404）

### 6.5 历史数据 (`/history/XAU`)

- 需要 API Key（`x-api-key` 请求头）
- 免费版：10 请求/小时
- Pro 版（$10/月）：无限请求，含分钟/小时聚合数据

### 6.6 定价方案

| 套餐 | 价格 | 实时价格 | 历史API | 分钟K线 |
|------|------|----------|---------|---------|
| Free | $0/月 | ✅ 无限请求 | 10 次/小时 | ❌ |
| Pro | $10/月 | ✅ 无限请求 | ✅ 无限请求 | ✅ 分钟/小时 |

### 6.7 gold-api.com 优点

- ✅ **实时价格完全免费，无限请求**，无速率限制
- ✅ **CORS 开启**，可直接从网页端调用
- ✅ **多数据源自动切换**，主源失效自动降级
- ✅ 支持 XAU/XAG/XPT/XPD 等多种贵金属

### 6.8 gold-api.com 局限性

- ❌ **无历史 K 线**（免费版）
- ❌ **无 OHLC**（需认证）
- ❌ **无 CNY 货币换算**（currency=CNY 返回 404）
- ❌ **历史数据需要 Pro 版**（$10/月）
- ❌ 数据来源未公开披露（不如 LBMA 权威）

### 6.9 与 Kotlin 项目的关联

```kotlin
// Kotlin 项目实际使用方式
GET https://api.gold-api.com/price/{symbol}  // 无认证，实时价格
GET https://api.gold-api.com/history/XAU      // 需 x-api-key
```

---

## 七、数据源横向对比总结

### 7.1 国际金价（XAU/USD）

| 数据源 | 实时价格 | K线历史 | 免费额度 | 权威性 | 备注 |
|--------|----------|---------|----------|--------|------|
| **EastMoney COMEX**（当前） | ✅ | ✅ 分钟K | 无限 | ⭐⭐ | 期货主连，非现货 |
| **Sina hf_XAU** | ✅ | ❌ | 无限 | ⭐⭐ | 需 Referer，无K线 |
| **gold-api.com** | ✅ | ❌（Pro） | 实时无限 | ⭐⭐ | 无速率限制 |
| **Metals-API** | ✅ | ✅ | 100/月 | ⭐⭐⭐⭐ | LBMA Gold，需注意限额 |
| **Metals.dev** | ✅ | ✅ 5年 | 100/月 | ⭐⭐⭐⭐ | LBMA Gold |
| **Binance XAUTUSDT**（当前） | ✅ | ✅ | 有限制 | ⭐⭐ | 代币，非实物金 |

### 7.2 国内金价

| 数据源 | 数据类型 | 免费额度 | 备注 |
|--------|----------|----------|------|
| **EastMoney AU9999**（当前） | SGE 现货 | 无限 | ✅ 最优 |
| jdjygold.com 银行API | 银行零售价 | 无限 | 溢价 ~5.5% |
| 极速数据 jisuapi.com | SGE + SHFE | 100次/天 | 需注册 |

### 7.3 综合推荐

```
国际金价:
  主: EastMoney COMEX ← K线数据，保留
  补充: gold-api.com ← 实时价格备选（免费无限，无需认证）

国内金价:
  主: EastMoney SGE AU9999 ← SGE现货，最优，保留

中期升级:
  国际: Metals-API (LBMA Gold) ← 权威现货基准，需付费或降低刷新频率
```

> **gold-api.com** 非常适合作为**免费实时价格兜底数据源**，因为实时端点完全免费、无速率限制、多数据源自动降级，且 CORS 开启可直接前端调用。但不适合作为 K 线来源。

---

## 八、GitHub 开源项目数据源调研

> 调研范围：GitHub 搜索 gold-price、gold-dashboard、gold-tracker 等关键词，筛选活跃且代码完整的项目。

### 8.1 项目总览

| # | 项目 | 数据源 | 技术栈 | 特点 |
|---|------|--------|--------|------|
| 1 | `datangguoji/gold_price_sniffer` | 5huangjin.com | Python/Flask | 三市场：伦敦金+纽约金+上海金延期 |
| 2 | `hej-sky/gold-price` | Sina 财经 | Python/Playwright | 新浪三端点（网页+API+期货页） |
| 3 | `omkarcloud/gold-price-api` | CME 芝加哥商品交易所 | Python | 实时金价，5000次/月免费，99.99% SLA |
| 4 | `hudsonengineer/gold-price` | metals.live API | Spring Boot | WebSocket 推送，30秒刷新 |
| 5 | `goldpriceapidb/gold-price` | Metals-API + GoldAPI + 网页抓取 | Node.js/MongoDB | 多源聚合，50国货币换算 |
| 6 | `xdec/gold-price-api` | Metals-API + GoldAPI | Python | 多 API 包装器 |
| 7 | `Anuchacha/gold-price-dashboard` | 泰国金银协会 | Python/Streamlit | 泰国本地金价 |
| 8 | `Chainarate/gold-price-dashboard` | 泰国多家经纪商 | Python/Flask | 12秒刷新，多经纪商聚合 |
| 9 | `namtrhg/vn-gold-price-api` | 越南 SJC/DOJI/PNJ | Node.js | 越南本地金价网页抓取 |
| 10 | `sjsakib/gold-price` | 孟加拉 BAJUS | Go/Colly | 孟加拉本地金价 |
| 11 | `pcloves/JdGold` | 京东金融 | Java | 中国金价+微信推送 |

### 8.2 新发现的重要数据源

#### 8.2.1 5huangjin.com — 三市场数据聚合（最重要发现）

```
GET https://www.5huangjin.com/data/jin.js
```

| 字段代码 | 市场 | 数据类型 | 来源标注 |
|----------|------|----------|---------|
| `hq_str_hf_XAU` | 伦敦金（现货） | 美元/盎司 | 伦敦黄金交易市场 |
| `hq_str_hf_GC` | 纽约金（期货） | 美元/盎司 | 纽约商品交易所 |
| `hq_str_gds_AUTD` | 上海金延期（AUTD） | 人民币/克 | 上海黄金交易所 |

> 来源明确标注：国际金价数据来自**伦敦黄金交易市场**（现货）和**纽约商品交易所**（期货），人民币数据来自**上海黄金交易所**。

**优点**：
- ✅ 三市场数据一次获取
- ✅ 伦敦金 = 现货，最权威
- ✅ 上海金延期 = 国内大宗现货价（不是零售价）
- ✅ 免费，无需认证

**缺点**：
- ❌ 无历史 K 线，仅实时快照
- ❌ 需解析 JS 格式数据

#### 8.2.2 CME Gold Price API（omkarcloud）

```
GET https://gold-price-api.omkar.cloud/price
Header: x-api-key: YOUR_KEY
```

```json
{"price_usd": 5030.7, "updated_at": "2026-02-09T10:12:49+00:00"}
```

| 套餐 | 价格 | 请求次数 |
|------|------|----------|
| Free | $0 | 5,000/月 |
| Starter | $25 | 100,000/月 |
| Grow | $75 | 1,000,000/月 |
| Scale | $150 | 10,000,000/月 |

- ✅ 数据来源：**CME 芝加哥商品交易所**
- ✅ 99.99% 上线 SLA
- ✅ 免费 5000次/月，够每分钟刷新
- ❌ 期货价格，非现货
- ❌ 单一品种（只有 XAU/USD）
- ❌ 只有价格，无 OHLC

#### 8.2.3 metals.live API

```
GET https://api.metals.live/v1/spot/gold
```
- 被 `hudsonengineer/gold-price` 项目直接使用
- Spring Boot WebFlux + WebSocket 实时推送
- 刷新间隔：30秒（可配置）

#### 8.2.4 各国本地金价数据源

| 国家 | 数据源 | 机构 |
|------|--------|------|
| 泰国 | `goldtraders.or.th` | 泰国金银协会 |
| 泰国 | `ylgbullion.co.th/api/price/gold` | YLG Bullion |
| 越南 | SJC/DOJI/PNJ 官网 | 越南主要金商 |
| 孟加拉 | `bajus.org/gold-price` | 孟加拉金银协会 |
| 伊朗 | Navasan.net / tgju.org | 伊朗贵金属网站 |

### 8.3 GitHub 项目数据源模式总结

| 数据源类型 | 出现频率 | 说明 |
|-----------|----------|------|
| Sina 财经（新浪） | 高 | 国内最常用，API 稳定 |
| Metals-API / Metals.dev | 高 | 国际贵金属基准 |
| CME（通过 omkarcloud 包装） | 中 | 期货，5000次/月免费 |
| 5huangjin.com | 中 | 三市场数据聚合 |
| 网页抓取（BeautifulSoup/Playwright/Selenium） | 高 | 各国本地金价主要方式 |
| gold-api.com | 低 | 免费无限，但来源不透明 |

---

## 九、综合数据源最终推荐

### 9.1 国际金价（XAU/USD）

| 优先级 | 数据源 | 类型 | 优点 | 缺点 |
|--------|--------|------|------|------|
| ⭐ 1 | **5huangjin.com** (`jin.js`) | 伦敦现货金 | 三市场一次取，伦敦=现货最权威 | 无K线，仅快照 |
| ⭐ 2 | **EastMoney COMEX GC00Y**（当前） | CME 期货主连 | K线数据完善 | 期货，非现货 |
| ⭐ 3 | **omkarcloud CME API** | CME 期货 | 5000次/月免费，SLA 99.99% | 期货，无K线 |
| 4 | **Metals-API LBMA Gold** | LBMA 定盘价 | 权威现货基准，需注意限额 | 免费额度有限 |
| 5 | **gold-api.com** | 多源聚合 | 免费无限，CORS开启 | 个人项目，不透明 |

### 9.2 国内金价

| 优先级 | 数据源 | 类型 | 优点 |
|--------|--------|------|------|
| ⭐ 1 | **EastMoney SGE AU9999**（当前） | SGE 现货 | 最优，实时，无限，免费 |
| 2 | **5huangjin.com** `gds_AUTD` | 上海金延期 | 三市场一次取，AUTD是大宗现货 |
| 3 | Sina `njs_gold` | 黄金T+D | 新浪API，无需抓取 |

### 9.3 推荐组合方案

```
国际金价:
  主(K线): EastMoney COMEX GC00Y ← 保留，当前的K线来源
  主(现货): 5huangjin.com jin.js ← 新增，伦敦现货金，三市场一次取
  备(实时): omkarcloud CME API ← 新增，5000次/月免费

国内金价:
  主: EastMoney SGE AU9999 ← 保留，SGE现货最优
  备: 5huangjin.com AUTD 或 Sina njs_gold

汇率:
  主: Metals-API / Metals.dev 同一API
  备: 继续用 yfinance
```

> **5huangjin.com 是本次调研最大发现** — 唯一一个免费、实时、同时覆盖"伦敦现货金 + 纽约期货金 + 上海金延期"三市场的数据源，且数据来源明确标注为伦敦黄金市场和上海黄金交易所。

---

## 十、5huangjin.com 深度调研（子线程并行调研）

### 10.1 数据来源

| 信息项 | 详情 |
|--------|------|
| **运营主体** | 个人备案（ICP 15019818-4），备案人：田洋 |
| **国际金价来源** | 伦敦黄金市场（现货）、COMEX/NYMEX（期货）— 官网明确标注 |
| **国内金价来源** | 上海黄金交易所（SGE）— 官网明确标注 |
| **免责声明** | "数据仅供参考，对使用结果不承担责任" |
| **数据获取方式** | 推断通过新浪财经等第三方聚合，未直连交易所 |

### 10.2 实时数据能力

**`jin.js` 完整数据覆盖（10个品种）：**

| 品种 | 变量名 | 市场 | 单位 |
|------|--------|------|------|
| 黄金 | `hq_str_hf_XAU` | 伦敦现货金 ✅ | USD/盎司 |
| 黄金 | `hq_str_hf_GC` | COMEX 期货 | USD/盎司 |
| 白银 | `hq_str_hf_XAG` | 伦敦现货 | USD/盎司 |
| 白银 | `hq_str_hf_SI` | COMEX 期货 | USD/盎司 |
| 铂金 | `hq_str_hf_XPT` | 伦敦现货 | USD/盎司 |
| 钯金 | `hq_str_hf_XPD` | 伦敦现货 | USD/盎司 |
| 黄金T+D | `hq_str_gds_AUTD` | SGE 延期 | CNY/克 |
| 白银T+D | `hq_str_gds_AGTD` | SGE 延期 | CNY/克 |
| 黄金期货 | `hq_str_nf_AU0` | SHFE 期货 | CNY/克 |
| 白银期货 | `hq_str_nf_AG0` | SHFE 期货 | CNY/克 |

**`hf_XAU` 完整字段解析（14字段）：**

| 索引 | 字段 | 示例值 | 说明 |
|------|------|--------|------|
| 0 | 当前价 | 4651.71 | USD/盎司 |
| 1 | 昨收价 | 4675.990 | |
| 2 | 开盘价 | 4651.71 | |
| 3 | 买价 Bid | 4652.06 | |
| 4 | 最高价 | 4671.60 | |
| 5 | 最低价 | 4600.79 | |
| 6 | 报价时间 | 10:42:00 | HH:MM:SS |
| 7 | 昨结算价 | 4675.99 | |
| 8 | 今结算价 | 4652.28 | |
| 9 | 成交量 | 0 | |
| 10 | 买量 | 0 | |
| 11 | 卖量 | 0 | |
| 12 | 交易日期 | 2026-04-06 | |
| 13 | 备注 | 伦敦金收盘价仅供参考 | |

**接口能力评估：**

| 维度 | 评分 | 说明 |
|------|------|------|
| 更新频率 | ✅ 5秒 | 自动刷新 |
| 品种覆盖 | ✅ | 10个品种，中美英三市场 |
| 数据精度 | ✅ | 2-3位小数，含买/卖价 |
| 认证需求 | ✅ | 完全免费，无需注册 |
| **CORS** | ❌ | **不支持跨域**，需后端代理 |
| 频率限制 | ✅ | 无明确限制 |
| 国内访问 | ✅ | 国内服务器，182ms响应 |

### 10.3 K线能力评估

**结论：❌ 不提供任何K线数据**

| 问题 | 答案 |
|------|------|
| K线图 | ❌ **无** — 仅提供线形走势图 |
| 分钟K | ❌ 无 |
| 小时K | ❌ 无 |
| 日K | ❌ 无 — 仅预设"1天"走势线图 |
| 历史数据范围 | 预设30分钟/60分钟/6小时/1天/5天/1年/10年 |
| API接口 | ❌ **无** — 非面向开发者网站 |
| 数据下载 | ❌ 不支持 |

### 10.4 综合评估

```
实时价格:   ✅ 优秀 — 5秒刷新，含买/卖价，10个品种
数据权威性: ⚠️ 中等 — 来源标注清晰，但个人运营无保证
K线能力:   ❌ 无   — 仅有预设线图，无法做K线图表
接入门槛:   ⚠️ 需后端代理 — 不支持CORS

结论：5huangjin.com 是优秀的"实时价格快照"数据源，
     但无法替代 EastMoney 提供 K 线图表能力。
```

### 10.5 对项目的价值

| 用途 | 是否满足 |
|------|---------|
| 实时国际金价（买/卖价） | ✅ **满足** — 伦敦现货金，含Bid/Ask |
| 国内金价实时 | ✅ **满足** — SGE AU T+D，人民币/克 |
| K线图表 | ❌ 不满足 |
| 作为备援数据源 | ✅ **满足** — 三市场一次取，无需认证 |

**建议接入方式**：
- 后端代理转发 `jin.js` 数据（解决 CORS 问题）
- 用于**实时价格展示**（替代 Sina hf_XAU，优势是含 Bid/Ask）
- **K线仍依赖 EastMoney COMEX**（无法替代）

---

## 十一、继续寻找带K线的金价数据源

> 本章节持续更新，寻找能同时提供实时价格和K线历史数据的源。
