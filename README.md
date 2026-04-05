# 黄金行情分析仪表盘 (Gold Dashboard)

实时黄金价格监控与行情分析平台，覆盖国际黄金（XAU/USD）、国内黄金（AU9999）及美元兑人民币汇率，支持 K 线图表、新闻资讯、AI 简报。

![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Chart.js](https://img.shields.io/badge/Chart.js-4.4-orange)

---

## 功能特性

### 实时价格
- **国际黄金** XAU/USD (USD/oz) — Binance XAUTUSDT 5m K线
- **国内黄金** AU9999 (CNY/g) — fx678 / 上海黄金交易所
- **美元/人民币** USDCNY — yfinance
- 数据每 5 分钟自动同步（Server-Sent Events 30s 推送最新价）

### K 线图表
- Chart.js 双轴折线图（国际金价 vs 国内金价）
- 72 小时 5 分钟 K 线
- 鼠标悬停十字线：显示北京时间、美东时间、国际金价、国内金价
- 支持鼠标滚轮缩放、拖拽平移、双击重置

### 新闻资讯
- 富途牛牛 RSS 新闻源
- AI 简报：每小时汇总 + 每日整体摘要（Claude API 生成）
- 近 1 小时新闻实时展示

### AI 简报
- **近 12 小时逐时简报**：每小时自动生成，一句话判断方向
- **上一日整体摘要**：每日 08:05 生成，汇总全天走势与驱动因素
- **新闻来源**：每条简报关联对应时段原始新闻，可点击跳转原文

---

## 技术架构

```
Browser ← SSE/HTTP → FastAPI ←→ 数据源（可插拔配置）
                             ├── Binance XAUTUSDT 5m  → XAUUSD
                             ├── fx678 AU9999 5m   → AU9999
                             └── yfinance USDCNY 5m → USDCNY
                          ↕
                      SQLite (price_bars / news / ai_briefings / alerts)
                          ↕
                   asyncio (定时任务 + 简报生成)
```

### 目录结构

```
gold-dashboard/
├── backend/
│   ├── main.py              # FastAPI 入口 + lifespan 管理
│   ├── requirements.txt     # Python 依赖
│   ├── routers/
│   │   ├── price.py        # 价格/历史数据 API
│   │   ├── alert.py        # 预警 CRUD API
│   │   ├── sse.py          # Server-Sent Events 流
│   │   └── rss.py          # RSS 订阅源
│   ├── data/
│   │   ├── db.py          # SQLite 操作
│   │   └── sources/        # 可插拔数据源
│   │       ├── __init__.py      # SOURCES 配置表
│   │       ├── binance_kline.py  # Binance XAUTUSDT 5m → XAUUSD
│   │       ├── fx678_au9999.py  # fx678 SGE 5m  → AU9999
│   │       └── yfinance_fx.py   # yfinance USDCNY=X 5m → USDCNY
│   ├── alerts/
│   │   ├── engine.py      # 预警引擎
│   │   └── checker.py      # 简报生成调度器
│   └── analysis/
│       └── indicators.py   # MA / RSI / MACD 指标
├── frontend/
│   ├── index.html          # 单页应用入口
│   ├── css/style.css       # 深色主题样式
│   └── js/
│       ├── app.js         # 主逻辑：价格卡片 + 简报
│       ├── chart.js        # Chart.js 双轴图表 + 十字线悬浮
│       └── sse.js          # SSE 客户端
├── run.sh                  # 启动脚本
└── .env                    # 环境变量（不提交）
```

---

## 快速开始

### 前置依赖

- Python 3.14
- Node.js（可选，用于前端开发）

### 安装

```bash
# 克隆项目
git clone https://github.com/cyydark/gold-dashboard.git
cd gold-dashboard

# 安装 Python 依赖
pip install -r backend/requirements.txt
```

### 启动

```bash
./run.sh
# 或直接
uvicorn backend.main:app --reload --port 18000
```

访问 http://localhost:18000

---

## API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/prices` | GET | 当前价格 |
| `/api/history/{symbol}` | GET | K 线历史（XAUUSD / AU9999 / USDCNY） |
| `/api/news` | GET | 新闻资讯（?days=1） |
| `/api/news/refresh` | POST | 手动抓取新闻入库 |
| `/api/briefings` | GET | AI 简报 + 近 1 小时新闻 |
| `/api/briefings/trigger` | POST | 手动触发简报生成 |
| `/api/alerts/` | GET | 预警列表 |
| `/api/alerts/` | POST | 创建预警规则 |
| `/api/alerts/{id}` | DELETE | 删除预警 |
| `/stream` | GET | SSE 实时流（30s 间隔） |
| `/api/health` | GET | 健康检查 |

---

## 数据源

可插拔架构，配置于 `backend/data/sources/__init__.py` 的 `SOURCES` 字典。

| 数据 | Symbol | 数据源 | 粒度 | 历史深度 |
|------|--------|--------|------|----------|
| 国际金价 | XAUUSD | Binance `binance_kline.py` | 5m | ~3.5 天 |
| 国内金价 | AU9999 | fx678 `fx678_au9999.py` | 5m | ~5 天 |
| 汇率 | USDCNY | yfinance `yfinance_fx.py` | 5m | ~70 天 |

切换数据源：修改 `SOURCES` 字典对应条目即可，main.py 无需改动。

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
```

---

## License

MIT
