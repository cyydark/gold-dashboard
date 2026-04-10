# 黄金行情分析仪表盘 (Gold Dashboard)

实时黄金价格监控与行情分析平台，覆盖国际黄金（XAU/USD）、国内黄金（AU9999）及美元兑人民币汇率，支持 K 线图表、多源新闻资讯、AI 简报（SSE 流式输出）。

![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Chart.js](https://img.shields.io/badge/Chart.js-4.4-orange)

---

## 功能特性

### 实时价格
- **国际黄金** XAU/USD (USD/oz) — COMEX GC00Y / Binance XAUTUSDT / Sina hf_XAU（前端可切换）
- **国内黄金** AU9999 (CNY/g) — EastMoney + Sina
- **美元/人民币** USDCNY — yfinance + Sina
- 价格轮询：前端 10s / 图表 30s / 新闻 30min

### K 线图表
- Chart.js 双轴折线图（国际金价 vs 国内金价）
- 72 小时 5 分钟 K 线
- 鼠标悬停十字线：显示北京时间、美东时间、国际金价、国内金价
- 支持鼠标滚轮缩放、拖拽平移、双击重置

### 新闻资讯
- 多源新闻：富途牛牛、Bernama（马来西亚英文）、Aastocks（港股）、CNBC、RSSHUB 本地聚合
- 黄金关键词过滤，保留高相关性内容

### AI 简报（两层分析 + REST 返回）
- **Layer 1**：新闻 + K 线 → 分析结论（新闻与走势是否吻合）
- **Layer 2**：从同一 AI 响应中解析金价预期（方向、目标区间、见效时间、变卦条件）
- 两次 AI 调用合并为一次，响应写入 in-memory 缓存（TTL 3h），REST 接口直接读取，无 SSE 流式

---

## 技术架构

```
Browser ← HTTP → FastAPI
                      │
         ┌────────────┼─────────────┐
         │            │             │
      API Routes  Services      Workers
     (routes/)   (services/)  (news_worker)
                      │
           Data Sources (可插拔 sources/)
```

---

## 目录结构

```
gold-dashboard/
├── backend/
│   ├── api/
│   │   ├── limiter.py       # 限流中间件（slowapi）
│   │   ├── models.py        # 统一 API 响应模型
│   │   └── routes/          # 路由
│   │       ├── price.py          # 价格接口（realtime/chart）
│   │       ├── news.py           # 新闻接口
│   │       ├── briefing.py       # AI 简报接口
│   │       ├── briefing_sse.py   # SSE 流式简报
│   │       └── health.py         # 健康检查 + 数据源探测
│   ├── services/            # 业务逻辑层
│   │   ├── briefing_service.py  # AI 简报编排（in-memory）
│   │   ├── briefing_cache.py    # 两层 in-memory 缓存（TTL 3h）
│   │   ├── news_service.py      # 新闻聚合
│   │   └── price_service.py     # 价格逻辑（REST 模式）
│   ├── data/
│   │   ├── db.py            # 数据库初始化
│   │   ├── constants.py     # 全局配置常量
│   │   └── sources/         # 可插拔数据源
│   │       ├── eastmoney_xauusd.py   # COMEX GC00Y K 线
│   │       ├── binance_kline.py      # Binance XAUTUSDT
│   │       ├── sina_xau.py           # Sina 伦敦金快照
│   │       ├── eastmoney_au9999*.py  # AU9999
│   │       ├── yfinance_fx.py         # USDCNY
│   │       ├── sina_au*.py           # AU9999/AU0 快照
│   │       ├── sina_fx.py             # Sina USDCNY
│   │       ├── briefing.py            # AI 简报生成（Claude CLI）
│   │       ├── futu.py                # 富途新闻
│   │       ├── bernama.py             # Bernama 新闻
│   │       ├── aastocks.py           # Aastocks 新闻
│   │       ├── cnbc.py               # CNBC 新闻
│   │       └── local_news.py         # RSSHUB 聚合
│   ├── workers/
│   │   └── news_worker.py        # 后台新闻定时入库（15min）
│   ├── main.py                # FastAPI 入口
│   └── config.py              # 配置管理（pydantic-settings）
├── frontend/
│   ├── index.html             # 单页应用入口
│   ├── css/style.css          # 样式
│   └── js/
│       ├── app.js             # 应用入口
│       ├── polling.js         # 三通道轮询管理器
│       ├── chart/             # Chart.js 图表
│       ├── modules/           # 功能模块（价格/简报/新闻）
│       └── utils/             # EventBus
├── .env.example          # 环境变量模板
├── start.sh             # 服务管理脚本
├── run.sh               # 开发热重载脚本
└── README.md
```

---

## 快速开始

### 前置依赖

- Python 3.14
- Claude CLI（用于 AI 简报生成）：`claude --version` 确认已安装

### 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 配置

复制环境变量模板并填入实际值：

```bash
cp backend/.env.example backend/.env
```

主要配置项说明见下方「配置」章节。

### 启动服务

```bash
./start.sh start
```

访问 http://localhost:18000

### 管理命令

```bash
./start.sh start    # 启动服务
./start.sh stop     # 停止服务
./start.sh restart  # 重启服务
./start.sh status   # 查看状态
./start.sh logs    # 查看日志
```

---

## API 接口

| 端点 | 方法 | 说明 | 限流 |
|------|------|------|------|
| `/` | GET | 前端页面 | — |
| `/api/prices` | GET | 当前价格（预留） | — |
| `/api/realtime/xau/{source}` | GET | XAUUSD 实时价（source: comex/sina/binance） | 30/min |
| `/api/realtime/au/{source}` | GET | AU9999 实时价（source: eastmoney/sina） | 30/min |
| `/api/realtime/fx/{source}` | GET | USDCNY 实时价（source: yfinance/sina） | 30/min |
| `/api/chart/xau` | GET | XAUUSD K 线历史 | 30/min |
| `/api/chart/au` | GET | AU9999 K 线历史 | 30/min |
| `/api/news` | GET | 新闻资讯（?days=1~30） | 30/min |
| `/api/briefings` | GET | AI 简报 + 近 N 天新闻（?days=1~30） | 30/min |
| `/api/briefings/stream` | GET | 同 /briefings，返回 JSON | 30/min |
| `/api/briefings/news/refresh` | POST | 强制刷新新闻（预热缓存） | 5/min |
| `/api/briefings/briefing/refresh` | POST | 强制刷新简报缓存 | 3/hour |
| `/api/health` | GET | 服务健康检查 | — |
| `/api/health/sources` | GET | 各数据源连通性探测 | — |

---

## 数据源

### 价格数据

| 数据 | Symbol | 数据源 | 粒度 | 历史深度 |
|------|--------|--------|------|----------|
| 国际金价（可切换） | XAUUSD | COMEX GC00Y (EastMoney) | 5m | ~3.5 天 |
| 国际金价（可切换） | XAUUSD | Binance XAUTUSDT | 5m | ~3.5 天 |
| 国际金价（可切换） | XAUUSD | Sina hf_XAU | 实时 | — |
| 国内金价 | AU9999 | EastMoney + Sina | 5m | ~5 天 |
| 汇率 | USDCNY | yfinance | 日线 | ~70 天 |

切换数据源：前端价格卡片下拉选择，前端轮询管理器切换 source 参数。

### 新闻数据

| 来源 | 模块 | 语言 |
|------|------|------|
| 富途牛牛 | `futu.py` | 中文 |
| Bernama | `bernama.py` | 英文（马来西亚） |
| Aastocks | `aastocks.py` | 英文（港股） |
| CNBC | `cnbc.py` | 英文 |
| RSSHUB 聚合 | `local_news.py` | 中英（Bloomberg/FX Street/Investing.com） |

---

## 配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥（Claude CLI 从 shell 环境读取，无需在此设置） | — |
| `ANTHROPIC_BASE_URL` | Anthropic API 地址 | `https://api.minimaxi.com/anthropic` |
| `EASTMONEY_UT` | EastMoney 公开标识符 | 内置默认值 |
| `RSSHUB_URL` | RSSHUB RSS 聚合服务地址 | `http://localhost:18080/news` |
| `CORS_ORIGINS` | 允许的来源（逗号分隔） | `localhost:3000,localhost:8000` |
| `FRONTEND_PATH` | 前端静态文件路径 | `./frontend` |
| `BINANCE_SSL_VERIFY` | Binance SSL 验证（`1`=验证，`0`=跳过） | `1` |

---

## 开发

### 前端热重载

```bash
./run.sh          # 自动重载后端 + 前端直刷新
```

### 数据源探测

```bash
curl http://localhost:18000/api/health/sources | python3 -m json.tool
```

### 数据库

```bash
# 查看价格数据条数
sqlite3 backend/alerts.db "SELECT symbol, COUNT(*) FROM price_bars GROUP BY symbol;"

# 查看新闻数量
sqlite3 backend/alerts.db "SELECT source, COUNT(*) FROM news_items GROUP BY source;"
```

---

## License

MIT
