# 黄金行情分析仪表盘 (Gold Dashboard)

实时黄金价格监控与行情分析平台，覆盖国际黄金（COMEX GCW00）、国内黄金（AU9999）及美元兑人民币汇率，支持 K 线图表、新闻资讯、价格预警。

![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Chart.js](https://img.shields.io/badge/Chart.js-4.4-orange)

---

## 功能特性

### 实时价格
- **国际黄金** COMEX GCW00 (USD/oz) — Yahoo Finance
- **国内黄金** AU9999 (CNY/g) — 上海黄金交易所
- **美元/人民币** USD/CNY 汇率
- 数据每 30 秒自动刷新（Server-Sent Events）

### K 线图表
- Chart.js 双轴折线图（国际金价 vs 国内金价）
- 支持 1 天 / 5 天 / 月 时间范围切换
- 新闻 emoji 标注 + 虚线定位

### 新闻资讯
- 抓取华尔街见闻等 RSS 新闻源
- AI 简报：每小时汇总 + 每日整体摘要（Claude CLI 生成）
- 近1小时新闻实时展示

### AI 简报
- **近12小时逐时简报**：每小时自动生成，一句话判断方向
- **上一日整体摘要**：每日08:05生成，汇总全天走势与驱动因素
- **新闻来源**：每条简报关联对应时段原始新闻，可点击跳转原文

### 价格预警
- 设置高价/低价阈值，突破即触发
- 预警历史记录（SQLite 持久化）

---

## 技术架构

```
Browser ← SSE/HTTP → FastAPI ←→ 数据源
                             ├── yfinance       (国际金价/汇率)
                             ├── akshare        (国内金价)
                             └── RSSHub         (新闻 RSS)
                          ↕
                      SQLite (预警/新闻/简报)
                          ↕
                   APScheduler (定时任务 + 简报生成)
```

### 目录结构

```
gold-dashboard/
├── backend/
│   ├── main.py              # FastAPI 入口 + lifespan 管理
│   ├── requirements.txt      # Python 依赖
│   ├── routers/
│   │   ├── price.py         # 价格/历史数据/简报 API
│   │   ├── alert.py         # 预警 CRUD API
│   │   ├── sse.py           # Server-Sent Events 流
│   │   └── rss.py           # RSS 订阅源
│   ├── data/
│   │   ├── models.py        # Pydantic 数据模型
│   │   ├── db.py            # SQLite 操作
│   │   └── sources/
│   │       ├── international.py  # yfinance + RSS 新闻
│   │       ├── domestic.py        # akshare 国内金价
│   │       └── briefing.py        # AI 简报生成（Claude CLI）
│   ├── analysis/
│   │   └── indicators.py    # MA / RSI / MACD 指标
│   ├── alerts/
│   │   ├── engine.py        # 预警引擎
│   │   └── checker.py       # APScheduler 调度器
│   └── tests/               # 单元测试 (pytest)
├── frontend/
│   ├── index.html           # 单页应用入口
│   ├── css/style.css        # 深色主题样式
│   └── js/
│       ├── app.js           # 主逻辑：价格卡片 + 简报
│       ├── chart.js         # Chart.js 双轴图表 + emoji 标注
│       └── sse.js           # SSE 客户端
├── run.sh                   # 启动脚本
└── .env                     # 环境变量（不提交）
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

### 配置

创建 `.env` 文件：

```env
# RSSHub 地址（用于新闻抓取）
RSSHUB_BASE=http://192.168.2.200:11200

# 默认汇率（CNY/USD，用于国内金价换算）
DEFAULT_CNY_RATE=6.87
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
| `/api/history/{symbol}` | GET | K 线历史（?days=1/5/30） |
| `/api/news` | GET | 新闻资讯（?days=1） |
| `/api/news/refresh` | POST | 手动抓取新闻入库 |
| `/api/briefings` | GET | AI 简报 + 近1小时新闻 |
| `/api/briefings/trigger` | POST | 手动触发简报生成 |
| `/api/alerts/` | GET | 预警列表 |
| `/api/alerts/` | POST | 创建预警规则 |
| `/api/alerts/{id}` | DELETE | 删除预警 |
| `/api/alerts/triggered` | GET | 已触发预警 |
| `/stream` | GET | SSE 实时流（30s 间隔） |
| `/api/health` | GET | 健康检查 |

---

## 数据源

| 数据 | 来源 |
|------|------|
| 国际金价 GCW00 | Yahoo Finance (`yfinance`) |
| 国内金价 AU9999 | 上海黄金交易所 (`akshare`) |
| 汇率 USD/CNY | Yahoo Finance (`yfinance`) |
| K 线历史 | Binance XAUT/USDT K线 |
| 新闻资讯 | 华尔街见闻 RSS（RSSHub 代理） |

---

## 开发

### 运行测试

```bash
pytest backend/tests/ -v
```

### 前端热重载

```bash
# 修改 frontend/ 后直接刷新浏览器即可
# FastAPI 静态文件服务会自动提供最新文件
```

---

## License

MIT
