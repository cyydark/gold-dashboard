# 黄金行情分析仪表盘 (Gold Dashboard)

实时黄金价格监控与行情分析平台，覆盖国际黄金（XAU/USD）、国内黄金（AU9999）及美元兑人民币汇率，支持 K 线图表、多源新闻资讯、AI 简报。

![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Chart.js](https://img.shields.io/badge/Chart.js-4.4-orange)

---

## 功能特性

### 实时价格
- **国际黄金** XAU/USD (USD/oz) — Binance XAUTUSDT 或 COMEX GC00Y（可切换）
- **国内黄金** AU9999 (CNY/g) — EastMoney
- **美元/人民币** USDCNY — yfinance
- 数据每 6 分钟自动同步（Server-Sent Events 30s 推送最新价）

### K 线图表
- Chart.js 双轴折线图（国际金价 vs 国内金价）
- 72 小时 5 分钟 K 线
- 鼠标悬停十字线：显示北京时间、美东时间、国际金价、国内金价
- 支持鼠标滚轮缩放、拖拽平移、双击重置

### 新闻资讯
- 多源新闻：富途牛牛、Bernama（英文）、BitcoinWorld、Aastocks
- AI 金价影响评估：每条新闻自动标注方向（上升/下降/中性）及关注级别
- 黄金关键词过滤，保留高相关性内容

### AI 简报
- **每小时简报**：每小时 01 分自动生成，分析上一小时新闻
- **每日综合摘要**：每日 08:00（北京时间）汇总近 7 天新闻
- 每条简报关联原始新闻，可点击跳转原文

---

## 技术架构

```
Browser ← SSE/HTTP → FastAPI ←→ 数据层（可插拔配置）
                          │
              ┌───────────┼────────────────┐
              │           │                │
           API Routes  Repository      asyncio Workers
           (routes/)    (repositories/)  (_news_refresh_loop)
                          │                _price_bars_fetch_loop
                       SQLite             _briefing_loop
                   (alerts.db)
```

### 目录结构

```
gold-dashboard/
├── backend/
│   ├── api/
│   │   ├── limiter.py       # 限流中间件（slowapi）
│   │   ├── models.py        # 统一 API 响应模型
│   │   ├── dependencies.py  # 依赖注入
│   │   └── routes/          # 路由 (price, news, briefing, sse)
│   ├── services/            # Service 层（业务逻辑）
│   ├── repositories/        # Repository 层（数据访问，aiosqlite）
│   ├── data/
│   │   ├── db.py            # 数据库初始化 + 迁移
│   │   ├── constants.py     # 全局配置常量
│   │   └── sources/         # 可插拔数据源
│   │       ├── eastmoney_xauusd.py  # COMEX XAUUSD
│   │       ├── binance_kline.py     # Binance XAUTUSDT
│   │       ├── eastmoney_au9999.py  # AU9999
│   │       ├── yfinance_fx.py       # USDCNY
│   │       ├── futu.py              # 富途新闻
│   │       ├── bernama.py            # 马来西亚英文新闻
│   │       ├── bitcoinworld.py       # BitcoinWorld 新闻
│   │       ├── aastocks.py          # Aastocks 新闻
│   │       ├── briefing.py           # AI 简报生成
│   │       └── news_evaluation.py   # AI 新闻评估
│   ├── alerts/                # 预警系统
│   │   └── checker.py        # 定时简报调度
│   ├── workers/              # 后台 Worker（可选独立进程）
│   ├── main.py              # FastAPI 入口 + asyncio workers
│   └── config.py            # 配置管理（pydantic-settings）
├── frontend/
│   ├── index.html           # 单页应用入口
│   ├── css/style.css        # 样式
│   └── js/                  # 前端脚本
├── docs/                    # 设计文档
├── start.sh                # 启动脚本
└── README.md
```

---

## 快速开始

### 前置依赖

- Python 3.14

### 安装依赖

```bash
pip install -r backend/requirements.txt
```

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
| `/api/prices` | GET | 当前价格 | 全局 30/min |
| `/api/history/{symbol}` | GET | K 线历史（XAUUSD / AU9999 / USDCNY） | 全局 30/min |
| `/api/news` | GET | 新闻资讯（?days=1~30） | 全局 30/min |
| `/api/news/refresh` | POST | 手动抓取新闻入库 | 5/min |
| `/api/briefings` | GET | AI 简报 + 近 7 天新闻（?days=1~30） | 全局 30/min |
| `/api/briefings/trigger` | POST | 手动触发简报生成 | 3/hour |
| `/stream` | GET | SSE 实时流（30s 间隔） | — |
| `/api/health` | GET | 健康检查 | — |

---

## 数据源

### 价格数据

可插拔架构，配置于 `backend/data/sources/__init__.py` 的 `SOURCES` 字典。

| 数据 | Symbol | 数据源 | 粒度 | 历史深度 |
|------|--------|--------|------|----------|
| 国际金价（可切换） | XAUUSD | `eastmoney_xauusd.py` (COMEX GC00Y) | 5m | ~3.5 天 |
| 国际金价（可切换） | XAUUSD_BINANCE | `binance_kline.py` (Binance XAUTUSDT) | 5m | ~3.5 天 |
| 国内金价 | AU9999 | `eastmoney_au9999.py` | 5m | ~5 天 |
| 汇率 | USDCNY | `yfinance_fx.py` | 5m | ~70 天 |

切换 XAUUSD 数据源：调用 `POST /api/xau-source`（`binance` 或 `comex`）。

### 新闻数据

配置于 `backend/data/sources/__init__.py` 的 `NEWS_SOURCES` 字典。

| 来源 | 模块 | 语言 |
|------|------|------|
| 富途牛牛 | `futu.py` | 中文 |
| Bernama | `bernama.py` | 英文 |
| BitcoinWorld | `bitcoinworld.py` | 英文 |
| Aastocks | `aastocks.py` | 英文 |

---

## 配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `CORS_ORIGINS` | 允许的来源（逗号分隔） | `http://localhost:3000,http://localhost:8000` |
| `FRONTEND_PATH` | 前端静态文件路径 | `./frontend` |
| `OPENAI_API_KEY` | Claude API 密钥 | — |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | — |

---

## 开发

### 前端热重载

```bash
# 修改 frontend/ 后直接刷新浏览器即可
# FastAPI 静态文件服务会自动提供最新文件
```

### 数据库

```bash
# 查看价格数据
sqlite3 backend/alerts.db "SELECT symbol, COUNT(*) FROM price_bars GROUP BY symbol;"

# 查看新闻数量
sqlite3 backend/alerts.db "SELECT source, COUNT(*) FROM news_items GROUP BY source;"
```

---

## License

MIT
