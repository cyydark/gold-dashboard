# 实时金价·汇率·图表架构重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去掉数据库（SQLite），所有子系统改为纯 REST + 内存缓存驱动。前端全部替换为 REST 轮询，删除 SSE。

**Architecture:** 后端每个子系统独立——price、briefing、news 各有独立端点和内存缓存。前端用 `PollingManager` 替代 SSE，三套轮询独立运行，source 选择持久化到 localStorage。

**Tech Stack:** FastAPI（后端），Chart.js + 原生 fetch（前端），Python dict + TTL（缓存）

---

## 文件变更总览

### 新建文件
- `backend/core/cache.py` — 统一 TTL 缓存模块
- `frontend/js/polling.js` — PollingManager 替代 SSE

### 修改文件
- `backend/api/routes/price.py` — 合并 realtime/xau/au + 新增 chart/xau/au + fx 端点
- `backend/api/routes/briefing.py` — 改为内存缓存，无 DB 依赖
- `backend/api/routes/news.py` — 改为内存缓存，无 DB 依赖
- `backend/services/briefing_service.py` — 移除 DB 依赖
- `backend/services/news_service.py` — 移除 DB 依赖
- `backend/main.py` — 删除 `init_db()` 调用、删除所有 background workers
- `frontend/js/app.js` — 用 PollingManager 替代 SSE
- `frontend/js/chart/GoldChart.js` — 改为调用 `/api/chart/{xau,au}`
- `frontend/index.html` — 移除 SSE script，升级 JS 版本

### 删除文件
- `backend/data/db.py`
- `backend/api/routes/sse.py`
- `backend/repositories/briefing_repository.py`
- `backend/repositories/news_repository.py`
- `backend/repositories/price_repository.py`
- `backend/workers/briefing_worker.py`
- `backend/workers/news_worker.py`
- `backend/workers/price_worker.py`
- `frontend/js/sse.js`

---

## Task 1: 创建 backend/core/cache.py

**Files:**
- Create: `backend/core/cache.py`
- Test: 新文件无需测试

- [ ] **Step 1: 编写 cache.py**

```python
"""
内存 TTL 缓存模块。
每个缓存项：{"data": ..., "ts": 时间戳}
每次 get 时检查 TTL，过期返回 None。
"""
import time
from threading import Lock
from typing import Any


class TTLCache:
    """线程安全的 TTL 内存缓存。"""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            if time.monotonic() - item["ts"] > self._ttl:
                del self._store[key]
                return None
            return item["data"]

    def set(self, key: str, data: Any) -> None:
        with self._lock:
            self._store[key] = {"data": data, "ts": time.monotonic()}

    def clear(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear_all(self) -> None:
        with self._lock:
            self._store.clear()
```

- [ ] **Step 2: 提交**

```bash
git add backend/core/cache.py
git commit -m "feat(core): add TTLCache for in-memory caching

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 改造 backend/api/routes/price.py

**Files:**
- Modify: `backend/api/routes/price.py`
- Test: `backend/tests/test_price_routes.py`（新建）

- [ ] **Step 1: 新建测试文件**

```python
# backend/tests/test_price_routes.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_realtime_xau_comex():
    r = client.get("/api/realtime/xau/comex")
    assert r.status_code == 200
    d = r.json()
    assert "price" in d
    assert "change" in d
    assert d.get("unit") == "USD/oz"


def test_realtime_au_au9999():
    r = client.get("/api/realtime/au/au9999")
    assert r.status_code == 200
    d = r.json()
    assert "price" in d
    assert d.get("unit") == "CNY/g"


def test_realtime_fx_yfinance():
    r = client.get("/api/realtime/fx/yfinance")
    assert r.status_code == 200
    d = r.json()
    assert "price" in d
    assert "unit" in d


def test_chart_xau():
    r = client.get("/api/chart/xau?source=comex")
    assert r.status_code == 200
    d = r.json()
    assert "bars" in d
    assert isinstance(d["bars"], list)


def test_chart_au():
    r = client.get("/api/chart/au?source=au9999")
    assert r.status_code == 200
    d = r.json()
    assert "bars" in d
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/chenyanyu/DoSomeThing/gold-dashboard
pytest backend/tests/test_price_routes.py -v 2>&1 | head -40
```

预期：所有测试 FAIL（端点尚不存在）

- [ ] **Step 3: 重写 price.py**

用以下内容替换 `backend/api/routes/price.py` 的全部内容：

```python
"""Price API routes — realtime price, chart bars, FX rates."""
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query
from pydantic import BaseModel

BEIJING_TZ = timezone(timedelta(hours=8))

# ── XAU realtime fetchers ──────────────────────────────────────────
_XAU_FETCHERS = {
    "binance": ("backend.data.sources.binance_kline", "fetch_xauusd_realtime"),
    "sina":    ("backend.data.sources.sina_xau", "fetch_xauusd_realtime"),
    "metals":  ("backend.data.sources.metals_api", "fetch_xauusd_realtime"),
    "omkar":   ("backend.data.sources.omkar_cme", "fetch_xauusd_realtime"),
}
# comex 用 eastmoney_xauusd（东方财富 COMEX 行情）
_XAU_FETCHERS["comex"] = ("backend.data.sources.eastmoney_xauusd", "fetch_xauusd_realtime")

# ── AU realtime fetchers ───────────────────────────────────────────
_AU_FETCHERS = {
    "au9999":  ("backend.data.sources.eastmoney_au9999", "fetch_au9999_realtime"),
    "sina":    ("backend.data.sources.sina_au9999", "fetch_au9999_realtime"),
    "akshare": ("backend.data.sources.akshare_gold", "fetch_au_realtime"),
    "autd":    ("backend.data.sources.sina_autd", "fetch_autd_realtime"),
}

# ── FX fetchers ────────────────────────────────────────────────────
_FX_FETCHERS = {
    "yfinance": ("backend.data.sources.yfinance_fx", "fetch_usdcny"),
    "sina":     ("backend.data.sources.sina_fx", "fetch_usdcny"),
}

# ── Chart bar fetchers (return list of bars) ───────────────────────
_XAU_BAR_FETCHERS = {
    "comex":   ("backend.data.sources.eastmoney_xauusd", "fetch_xauusd_history"),
    "binance": ("backend.data.sources.binance_kline", "fetch_xauusd_kline"),
    "sina":    ("backend.data.sources.sina_xau", "fetch_xauusd_history"),
    "metals":  ("backend.data.sources.metals_api", "fetch_xauusd_history"),
    "omkar":   ("backend.data.sources.omkar_cme", "fetch_xauusd_history"),
}
_AU_BAR_FETCHERS = {
    "au9999":  ("backend.data.sources.eastmoney_au9999", "fetch_au9999_history"),
    "sina":    ("backend.data.sources.sina_au9999", "fetch_au9999_history"),
    "akshare": ("backend.data.sources.akshare_gold", "fetch_au_history"),
    "autd":    ("backend.data.sources.sina_autd", "fetch_autd_history"),
}

router = APIRouter(prefix="/api", tags=["price"])


def _fetch(source: str, fetchers: dict) -> dict | list | None:
    """调用指定 source 的 fetcher 模块，返回原始数据。失败返回 None。"""
    if source not in fetchers:
        return None
    mod_name, fn_name = fetchers[source]
    try:
        mod = __import__(mod_name, fromlist=[fn_name])
        return getattr(mod, fn_name)()
    except Exception:
        return None


def _build_xau_resp(bar: dict | None, now_ts: int) -> dict:
    """构造 XAUUSD 响应，bar 为 None 时返回错误结构。"""
    if bar is None:
        return {"error": "数据获取失败，请切换数据源", "price": None}
    return {
        "price": round(float(bar.get("price", bar.get("close", 0))), 2),
        "change": round(float(bar.get("change", 0)), 2),
        "pct": round(float(bar.get("pct", 0)), 4),
        "open": round(float(bar.get("open", bar["price"])), 2),
        "high": round(float(bar.get("high", bar["price"])), 2),
        "low": round(float(bar.get("low", bar["price"])), 2),
        "unit": "USD/oz",
        "ts": now_ts,
        "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


def _build_au_resp(bar: dict | None, now_ts: int) -> dict:
    if bar is None:
        return {"error": "数据获取失败，请切换数据源", "price": None}
    return {
        "price": round(float(bar.get("price", bar.get("close", 0))), 2),
        "change": round(float(bar.get("change", 0)), 2),
        "pct": round(float(bar.get("pct", 0)), 2),
        "open": round(float(bar.get("open", bar["price"])), 2),
        "high": round(float(bar.get("high", bar["price"])), 2),
        "low": round(float(bar.get("low", bar["price"])), 2),
        "unit": "CNY/g",
        "ts": now_ts,
        "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


def _build_fx_resp(bar: dict | None) -> dict:
    if bar is None:
        return {"error": "数据获取失败，请切换数据源", "price": None}
    return {
        "price": round(float(bar.get("price", bar.get("close", 0))), 4),
        "change": round(float(bar.get("change", 0)), 4),
        "pct": round(float(bar.get("pct", 0)), 4),
        "open": round(float(bar.get("open", bar["price"])), 4),
        "high": round(float(bar.get("high", bar["price"])), 4),
        "low": round(float(bar.get("low", bar["price"])), 4),
        "unit": "CNY/USD",
        "ts": bar.get("ts", int(time.time())),
    }


@router.get("/realtime/xau/{source}")
def get_xau_realtime(source: str):
    bar = _fetch(source, _XAU_FETCHERS)
    return _build_xau_resp(bar, int(time.time()))


@router.get("/realtime/au/{source}")
def get_au_realtime(source: str):
    bar = _fetch(source, _AU_FETCHERS)
    return _build_au_resp(bar, int(time.time()))


@router.get("/realtime/fx/{source}")
def get_fx_realtime(source: str):
    bar = _fetch(source, _FX_FETCHERS)
    return _build_fx_resp(bar)


@router.get("/chart/xau")
def get_chart_xau(source: str = Query(default="comex")):
    bars_raw = _fetch(source, _XAU_BAR_FETCHERS)
    if bars_raw is None:
        return {"bars": [], "source": source}
    # 标准化字段：统一用 close
    bars = []
    for b in bars_raw:
        bars.append({
            "time": b.get("time", b.get("ts", 0)),
            "open": round(float(b.get("open", b.get("close", 0))), 2),
            "high": round(float(b.get("high", b.get("close", 0))), 2),
            "low": round(float(b.get("low", b.get("close", 0))), 2),
            "close": round(float(b.get("close", b.get("price", 0))), 2),
        })
    return {"bars": bars, "source": source}


@router.get("/chart/au")
def get_chart_au(source: str = Query(default="au9999")):
    bars_raw = _fetch(source, _AU_BAR_FETCHERS)
    if bars_raw is None:
        return {"bars": [], "source": source}
    bars = []
    for b in bars_raw:
        bars.append({
            "time": b.get("time", b.get("ts", 0)),
            "open": round(float(b.get("open", b.get("close", 0))), 2),
            "high": round(float(b.get("high", b.get("close", 0))), 2),
            "low": round(float(b.get("low", b.get("close", 0))), 2),
            "close": round(float(b.get("close", b.get("price", 0))), 2),
        })
    return {"bars": bars, "source": source}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest backend/tests/test_price_routes.py -v 2>&1 | head -50
```

预期：PASS（如有源返回错误，HTTP 200 但 price=None，不算 FAIL）

- [ ] **Step 5: 提交**

```bash
git add backend/api/routes/price.py backend/tests/test_price_routes.py
git commit -m "feat(api): replace SSE with REST realtime + chart endpoints

- GET /api/realtime/xau/{source}
- GET /api/realtime/au/{source}
- GET /api/realtime/fx/{source}
- GET /api/chart/xau?source=...
- GET /api/chart/au?source=...
No DB dependency.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 删除 backend/api/routes/sse.py

**Files:**
- Delete: `backend/api/routes/sse.py`
- Modify: `backend/api/routes/__init__.py`（移除 sse router import）

- [ ] **Step 1: 检查 __init__.py 是否有 sse router 引用**

```bash
cat backend/api/routes/__init__.py
```

- [ ] **Step 2: 删除 sse.py**

```bash
rm backend/api/routes/sse.py
```

- [ ] **Step 3: 从 __init__.py 移除 sse router（如有）**

如果 `__init__.py` 有 `from . import sse`，删除该行

- [ ] **Step 4: 提交**

```bash
git add -A backend/api/routes/sse.py backend/api/routes/__init__.py
git commit -m "chore(api): remove SSE endpoint

SSE /stream is replaced by REST polling. sse.py deleted.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 更新 backend/main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 读取当前 main.py 内容**

```bash
cat backend/main.py
```

- [ ] **Step 2: 重写 lifespan 和 startup/shutdown**

替换 `backend/main.py`，保留 app 实例、异常处理器、CORS 和静态文件挂载，但：

1. **删除** `from backend.data.db import init_db`
2. **删除** `from backend.workers import ...` 所有 worker imports
3. **删除** `lifespan` 中的 `await init_db()` 调用
4. **删除** `lifespan` 中所有 `_news_refresh_loop`、`_price_bars_fetch_loop`、`_briefing_loop` 的启动
5. **删除** `sse` router 的注册

删除后，`lifespan` 只做 `yield`（空操作），`main.py` 变为纯静态文件服务器 + API 路由。

核心保留结构：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # 无需 startup/shutdown

app = FastAPI(lifespan=lifespan, ...)
app.include_router(price.router)
app.include_router(news.router)
app.include_router(briefing.router)
# sse router 已删除
```

- [ ] **Step 3: 提交**

```bash
git add backend/main.py
git commit -m "refactor(main): remove DB init and background workers

No more init_db(), no more background polling loops.
Static API server with price/news/briefing routers only.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 改造 backend/api/routes/briefing.py 为内存缓存

**Files:**
- Modify: `backend/api/routes/briefing.py`
- Modify: `backend/services/briefing_service.py`

- [ ] **Step 1: 读取当前 briefing.py 和 briefing_service.py**

```bash
cat backend/api/routes/briefing.py && echo "---" && cat backend/services/briefing_service.py
```

- [ ] **Step 2: 改写 briefing_service.py（新建缓存，移除 DB）**

用纯抓取 + LLM 分析替换：

```python
"""Briefing service — no DB, pure in-memory cache."""
import time
from backend.services.news_service import NewsService  # 重用 news service

# TTL: 1 小时
_CACHE_TTL = 3600
_cache: dict = {"ts": 0, "data": None, "news": []}


def get_briefing(days: int = 3) -> dict:
    """返回缓存的周报 + 新闻列表。缓存过期则重新生成。"""
    now = time.monotonic()
    if _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]
    # 重新生成
    news_svc = NewsService()
    news = news_svc.get_news(days=days)
    content = _generate_briefing(news, days)
    result = {
        "weekly": {
            "content": content,
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }
    _cache["data"] = result
    _cache["ts"] = now
    return result


def _generate_briefing(news: list, days: int) -> str:
    """调用 LLM 基于新闻生成分析文本。"""
    # TODO: 接入 LLM（参考原有实现）
    if not news:
        return "暂无足够新闻数据生成周报。"
    return f"近{days}日共{len(news)}条新闻，详情见列表。"


def _time_range(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    now = datetime.now(BEIJING_TZ)
    past = now - timedelta(days=days)
    return f"{past.strftime('%m月%d日')} - {now.strftime('%m月%d日')}"
```

- [ ] **Step 3: 简化 briefing.py 路由**

```python
"""Briefing API routes — backed by in-memory cache only."""
from fastapi import APIRouter, Query
from backend.services.briefing_service import get_briefing

router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings")
def get_briefings(days: int = Query(default=3, ge=1, le=30)):
    return get_briefing(days=days)


@router.post("/briefings/trigger")
def trigger_briefing():
    # 强制刷新：清除缓存后重新获取
    from backend.services.briefing_service import _cache
    _cache["data"] = None
    return get_briefing(days=3)
```

- [ ] **Step 4: 提交**

```bash
git add backend/api/routes/briefing.py backend/services/briefing_service.py
git commit -m "refactor(briefing): replace DB with in-memory cache (TTL 1h)

No more news_repository dependency. News fetched on demand.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 改造 backend/api/routes/news.py 为内存缓存

**Files:**
- Modify: `backend/api/routes/news.py`
- Modify: `backend/services/news_service.py`

- [ ] **Step 1: 读取当前 news.py 和 news_service.py**

```bash
cat backend/api/routes/news.py && echo "---" && cat backend/services/news_service.py
```

- [ ] **Step 2: 改写 news_service.py（内存缓存，无 DB）**

```python
"""News service — no DB, pure in-memory cache."""
import time
from typing import Any

# TTL: 30 分钟
_CACHE_TTL = 1800
_cache: dict[str, Any] = {"ts": 0, "data": []}

# 新闻来源配置（复用原有配置）
NEWS_SOURCES = [
    "backend.data.sources.briefing",
]

# 同步获取新闻的函数列表（需实现 fetch_news()）
def _get_news_from_sources() -> list:
    items = []
    for src in NEWS_SOURCES:
        try:
            mod = __import__(src, fromlist=["fetch_news"])
            fn = getattr(mod, "fetch_news", None)
            if fn:
                result = fn()
                if isinstance(result, list):
                    items.extend(result)
        except Exception:
            pass
    return items


def get_news(days: int = 1) -> list:
    """返回缓存的新闻列表。缓存过期则重新抓取。"""
    now = time.monotonic()
    if _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]
    items = _get_news_from_sources()
    _cache["data"] = items
    _cache["ts"] = now
    return items
```

- [ ] **Step 3: 简化 news.py 路由**

```python
"""News API routes — backed by in-memory cache only."""
from fastapi import APIRouter, Query
from backend.services.news_service import get_news

router = APIRouter(prefix="/api", tags=["news"])

# 重新导出 limiter（其他模块可能依赖）
from backend.api.limiter import limiter

@router.get("/news")
def get_news_endpoint(days: int = Query(default=1, ge=1, le=30)):
    return {"news": get_news(days=days)}


@router.post("/news/refresh")
@limiter.limit("5/minute")
def refresh_news():
    from backend.services.news_service import _cache
    _cache["data"] = []
    _cache["ts"] = 0
    return {"news": get_news(days=1)}
```

- [ ] **Step 4: 提交**

```bash
git add backend/api/routes/news.py backend/services/news_service.py
git commit -m "refactor(news): replace DB with in-memory cache (TTL 30min)

No more news_repository dependency.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: 创建前端 frontend/js/polling.js

**Files:**
- Create: `frontend/js/polling.js`

- [ ] **Step 1: 编写 PollingManager**

```javascript
/**
 * PollingManager — replaces SSEClient.
 * Three independent polling channels: card-prices, chart-bars, news.
 * Each channel polls at its own interval and persists source choices.
 */
export class PollingManager {
  constructor() {
    this._timers = {};
    this._lastPrices = {};
    this._lastChartData = { xau: null, au: null };
    this._onPriceUpdate = null;
    this._onChartUpdate = null;
    this._onNewsUpdate = null;

    // Source defaults (权威性排序第一个)
    this._sources = {
      xau:  localStorage.getItem("source_xau")  || "comex",
      au:   localStorage.getItem("source_au")   || "au9999",
      fx:   localStorage.getItem("source_fx")   || "yfinance",
      xauChart: localStorage.getItem("source_xau_chart") || "comex",
      auChart:  localStorage.getItem("source_au_chart")  || "au9999",
    };
  }

  // ── Event callbacks ────────────────────────────────────────────────

  onPriceUpdate(fn)    { this._onPriceUpdate = fn; }
  onChartUpdate(fn)    { this._onChartUpdate = fn; }
  onNewsUpdate(fn)     { this._onNewsUpdate = fn; }

  // ── Source accessors ───────────────────────────────────────────────

  getSource(key) { return this._sources[key]; }

  setSource(key, value) {
    this._sources[key] = value;
    localStorage.setItem("source_" + key, value);
    // Restart the relevant timer if running
    if (this._timers[key]) {
      this.stop(key);
      this.start(key);
    }
    if (key === "xau" || key === "au" || key === "fx") {
      this._pollPrices();
    }
    if (key === "xauChart") {
      this._pollChart();
    }
    if (key === "auChart") {
      this._pollChart();
    }
  }

  // ── Start / Stop ───────────────────────────────────────────────────

  start(channel) {
    if (this._timers[channel]) return;
    if (channel === "prices") {
      this._pollPrices();
      this._timers.prices = setInterval(() => this._pollPrices(), 10000);
    } else if (channel === "chart") {
      this._pollChart();
      this._timers.chart = setInterval(() => this._pollChart(), 30000);
    } else if (channel === "news") {
      this._pollNews();
      this._timers.news = setInterval(() => this._pollNews(), 30 * 60 * 1000);
    }
  }

  stop(channel) {
    if (this._timers[channel]) {
      clearInterval(this._timers[channel]);
      delete this._timers[channel];
    }
  }

  stopAll() {
    Object.keys(this._timers).forEach(k => this.stop(k));
  }

  // ── Private pollers ────────────────────────────────────────────────

  async _pollPrices() {
    const [xau, au, fx] = await Promise.allSettled([
      fetch(`/api/realtime/xau/${this._sources.xau}`).then(r => r.json()),
      fetch(`/api/realtime/au/${this._sources.au}`).then(r => r.json()),
      fetch(`/api/realtime/fx/${this._sources.fx}`).then(r => r.json()),
    ]);

    const result = {};
    if (xau.status === "fulfilled" && xau.value.price != null) {
      result.XAUUSD = xau.value;
      this._lastPrices.xau = xau.value;
    } else if (this._lastPrices.xau) {
      result.XAUUSD = { ...this._lastPrices.xau, error: "获取失败" };
    }
    if (au.status === "fulfilled" && au.value.price != null) {
      result.AU9999 = au.value;
      this._lastPrices.au = au.value;
    } else if (this._lastPrices.au) {
      result.AU9999 = { ...this._lastPrices.au, error: "获取失败" };
    }
    if (fx.status === "fulfilled" && fx.value.price != null) {
      result.USDCNY = fx.value;
      this._lastPrices.fx = fx.value;
    } else if (this._lastPrices.fx) {
      result.USDCNY = { ...this._lastPrices.fx, error: "获取失败" };
    }

    if (Object.keys(result).length > 0 && this._onPriceUpdate) {
      this._onPriceUpdate(result);
    }
  }

  async _pollChart() {
    const [xau, au] = await Promise.allSettled([
      fetch(`/api/chart/xau?source=${this._sources.xauChart}`).then(r => r.json()),
      fetch(`/api/chart/au?source=${this._sources.auChart}`).then(r => r.json()),
    ]);

    if (this._onChartUpdate) {
      this._onChartUpdate({
        xau: xau.status === "fulfilled" ? xau.value : null,
        au:  au.status  === "fulfilled" ? au.value  : null,
      });
    }
  }

  async _pollNews() {
    try {
      const r = await fetch("/api/news");
      const d = await r.json();
      if (this._onNewsUpdate) this._onNewsUpdate(d.news || []);
    } catch (_) {}
  }
}

window.PollingManager = PollingManager;
```

- [ ] **Step 2: 提交**

```bash
git add frontend/js/polling.js
git commit -m "feat(frontend): add PollingManager replacing SSEClient

Three independent channels: prices (10s), chart (30s), news (30min).
Source choices persisted to localStorage.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: 更新 frontend/js/app.js

**Files:**
- Modify: `frontend/js/app.js`
- Modify: `frontend/js/chart/GoldChart.js`

- [ ] **Step 1: 改写 app.js — 用 PollingManager 替代 SSE**

用以下内容替换 `frontend/js/app.js` 全文：

```javascript
/**
 * Main app: price cards + dual gold chart + news.
 * All data driven by PollingManager (REST polling, no SSE).
 */
import { GoldChart } from "./chart/GoldChart.js";
import { PollingManager } from "./polling.js";

const polling = new PollingManager();
let chart = null;

/** Animate a number change with a flash effect */
function animatePriceChange(element, newValue) {
  if (!element) return;
  const oldValue = element.textContent;
  if (oldValue !== newValue) {
    element.style.transform = 'scale(1.05)';
    element.style.transition = 'transform 0.15s ease-out';
    setTimeout(() => {
      element.textContent = newValue;
      element.style.transform = 'scale(1)';
    }, 50);
  }
}

/** Show toast notification */
function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
window.showToast = showToast;

/** Update a price card with new data */
function updatePriceCard(symbol, data) {
  if (!data) return;

  const skeletonEl = document.getElementById(`skeleton-${symbol}`);
  const cardEl = document.getElementById(`card-${symbol}`);
  if (skeletonEl && cardEl) {
    skeletonEl.style.display = 'none';
    cardEl.style.display = 'block';
  }

  const priceEl = document.getElementById(`price-${symbol}`);
  const changeEl = document.getElementById(`change-${symbol}`);
  const card = document.getElementById(`card-${symbol}`);
  const openEl = document.getElementById(`open-${symbol}`);
  const highEl = document.getElementById(`high-${symbol}`);
  const lowEl = document.getElementById(`low-${symbol}`);
  if (!priceEl) return;

  if (data.error) {
    showToast(`${symbol}：${data.error}`, "error");
    return;
  }

  animatePriceChange(priceEl, `${data.price} ${data.unit || ""}`);

  const hasChange = data.change != null && data.pct != null;
  if (hasChange) {
    const sign = data.change >= 0 ? "+" : "";
    const changeText = `${sign}${data.change} (${sign}${data.pct}%)`;
    animatePriceChange(changeEl, changeText);
    changeEl.className = `price-card__change price-card__change--${data.change >= 0 ? "up" : "down"}`;
    if (card) {
      card.classList.remove("price-card--up", "price-card--down");
      const animClass = data.change >= 0 ? "price-card--up" : "price-card--down";
      card.classList.add(animClass);
      setTimeout(() => card.classList.remove(animClass), 600);
    }
  } else {
    changeEl.textContent = "";
    changeEl.className = "price-card__change";
    if (card) card.classList.remove("price-card--up", "price-card--down");
  }

  if (data.open != null && data.high != null && data.low != null) {
    if (openEl) openEl.textContent = data.open;
    if (highEl) highEl.textContent = data.high;
    if (lowEl) lowEl.textContent = data.low;
  }
}

window.onPriceUpdate = function(data) {
  if (!data) return;
  const el = document.getElementById("last-update");
  if (el) {
    const ts = data.XAUUSD?.ts || data.AU9999?.ts || data.USDCNY?.ts;
    if (ts) {
      const d = new Date(ts * 1000);
      el.textContent = `更新于 ${d.toLocaleTimeString("zh-CN", {hour:"2-digit",minute:"2-digit",second:"2-digit",timeZone:"Asia/Shanghai"})} 北京时间`;
    }
  }
  for (const sym of ["XAUUSD", "AU9999", "USDCNY"]) {
    if (data[sym]) updatePriceCard(sym, data[sym]);
  }
};

function _timeAgo(tsSec) {
  if (!tsSec) return "未知";
  const diffMs = Date.now() - tsSec * 1000;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}小时前`;
  return `${Math.floor(diffHr / 24)}天前`;
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

async function loadBriefings() {
  const weeklyEl = document.getElementById("weekly-content");
  const newsEl = document.getElementById("briefing-news-list");
  const weeklyTimeEl = document.getElementById("weekly-time");
  const newsCountEl = document.getElementById("news-count");
  const briefingSkeleton = document.getElementById("briefing-skeleton");
  const briefingContent = document.getElementById("briefing-content");
  const newsSkeleton = document.getElementById("news-skeleton");
  if (!weeklyEl) return;

  try {
    const res = await fetch("/api/briefings?days=3");
    const data = await res.json();
    const weeklyData = data.weekly;
    const news = data.news || [];

    if (briefingSkeleton) briefingSkeleton.style.display = 'none';
    if (briefingContent) briefingContent.style.display = 'block';
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    if (newsEl) newsEl.style.display = 'block';

    if (weeklyData) {
      weeklyTimeEl.textContent = weeklyData.time_range || "";
      weeklyEl.innerHTML = `<span class="briefing__daily-text">${escapeHtml(weeklyData.content || "")}</span>`;
    } else {
      weeklyTimeEl.textContent = "";
      weeklyEl.innerHTML = '<div class="state-message">暂无周报</div>';
    }

    if (newsEl) {
      if (newsCountEl) newsCountEl.textContent = `${data.news_count || news.length}条`;
      if (news.length === 0) {
        newsEl.innerHTML = '<div class="state-message">暂无资讯</div>';
      } else {
        newsEl.innerHTML = news.map((n, index) => `
          <a class="news-item" href="${escapeHtml(n.url || "#")}" target="_blank" rel="noopener" style="animation-delay: ${index * 50}ms">
            <div class="news-item__meta">
              <span class="news-item__source">${escapeHtml(n.source || "")}</span>
              <span>·</span>
              <span>${escapeHtml(n.published_at ? _timeAgo(n.published_ts) : (n.time_ago || ""))}</span>
            </div>
            <div class="news-item__title">${escapeHtml(n.title || n.title_en || "")}</div>
          </a>`).join("");
      }
    }

    if (chart) chart.setNews(news);
  } catch (e) {
    if (briefingSkeleton) briefingSkeleton.style.display = 'none';
    if (briefingContent) briefingContent.style.display = 'block';
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    if (newsEl) newsEl.style.display = 'block';
    weeklyEl.innerHTML = '<div class="state-message">加载失败</div>';
    if (newsEl) newsEl.innerHTML = '<div class="state-message">加载失败</div>';
  }
}

const XAU_LEGEND = {
  comex:   "COMEX GC00Y",
  binance: "XAUTUSDT (Binance)",
  sina:    "Sina 伦敦金 (hf_XAU)",
  metals:  "LBMA Gold (Metals-API)",
  omkar:   "CME Gold (Omkar)",
};

async function reloadChart() {
  const selXau = document.getElementById("sel-xau");
  const selAu = document.getElementById("sel-au");
  const legendXau = document.getElementById("legend-xau");

  const xau = selXau ? selXau.value : "comex";
  const au  = selAu ? selAu.value  : "au9999";

  if (legendXau) {
    legendXau.textContent = XAU_LEGEND[xau] || "COMEX GC00Y";
  }

  polling.setSource("xauChart", xau);
  polling.setSource("auChart", au);
  chart.xauSource = xau;
  chart.auSource = au;
  await chart.load();
}

window.addEventListener("DOMContentLoaded", async () => {
  // Wire up card source selectors
  const srcXau = document.getElementById("src-xau");
  const srcAu = document.getElementById("src-au");
  if (srcXau) {
    srcXau.value = polling.getSource("xau");
    srcXau.addEventListener("change", () => polling.setSource("xau", srcXau.value));
  }
  if (srcAu) {
    srcAu.value = polling.getSource("au");
    srcAu.addEventListener("change", () => polling.setSource("au", srcAu.value));
  }

  chart = new GoldChart();

  // Chart source selectors
  const selXau = document.getElementById("sel-xau");
  const selAu = document.getElementById("sel-au");
  if (selXau) selXau.addEventListener("change", reloadChart);
  if (selAu) selAu.addEventListener("change", reloadChart);

  // Plug PollingManager into app
  polling.onPriceUpdate(window.onPriceUpdate);
  polling.onChartUpdate(({ xau, au }) => {
    if (xau) chart.loadXauFromCache(xau);
    if (au)  chart.loadAuFromCache(au);
  });

  // Start polling
  polling.start("prices");
  polling.start("chart");
  loadBriefings();
  polling.start("news");

  await chart.load();
  chart.warmup();
});
```

- [ ] **Step 2: 更新 GoldChart.js — 接受 PollingManager 注入的缓存数据**

在 `GoldChart` 类中新增两个方法：

```javascript
/** Called by PollingManager with fresh chart data */
loadXauFromCache(data) {
  if (!data || !data.bars || data.bars.length === 0) return;
  const pts = insertGaps(data.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })));
  if (this.chart && this.chart.data.datasets[0]) {
    this.chart.data.datasets[0].data = pts;
    this._updateScales(0);
    this.chart.update("none");
    this._updateNowLine();
  }
}

loadAuFromCache(data) {
  if (!data || !data.bars || data.bars.length === 0) return;
  const pts = insertGaps(data.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })));
  if (this.chart && this.chart.data.datasets[1]) {
    this.chart.data.datasets[1].data = pts;
    this._updateScales(1);
    this.chart.update("none");
  }
}
```

同时修改 `warmup()` 方法，从 REST 端点拉取：

```javascript
warmup() {
  fetch(`/api/chart/xau?source=${this.xauSource}`).catch(() => {});
  fetch(`/api/chart/au?source=${this.auSource}`).catch(() => {});
}
```

同时修改 `load()` 方法，把 `fetch(/api/history/${xauSymbol})` 改为：

```javascript
const [xauRes, auRes] = await Promise.all([
  fetch(`/api/chart/xau?source=${this.xauSource}`),
  fetch(`/api/chart/au?source=${this.auSource}`),
]);
```

返回值字段从 `d.time * 1000` / `d.close` 读取（已在 Task 7 的 `_pollChart` 中处理）。

- [ ] **Step 3: 提交**

```bash
git add frontend/js/app.js frontend/js/chart/GoldChart.js
git commit -m "refactor(frontend): replace SSE with PollingManager

- PollingManager: 3 independent channels (prices 10s, chart 30s, news 30min)
- Card source selectors wired up
- GoldChart accepts cache injection
- No more SSE connection

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 更新 frontend/index.html + 删除 frontend/js/sse.js

**Files:**
- Modify: `frontend/index.html`
- Delete: `frontend/js/sse.js`

- [ ] **Step 1: 更新 index.html**

移除：
```html
<script src="/static/js/sse.js?v=3"></script>
```

升级版本号：
```html
<script type="module" src="/static/js/app.js?v=22"></script>
```

- [ ] **Step 2: 删除 sse.js**

```bash
rm frontend/js/sse.js
```

- [ ] **Step 3: 提交**

```bash
git add frontend/index.html
git rm frontend/js/sse.js
git commit -m "chore(frontend): remove sse.js, update index.html

SSE script tag removed from index.html.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: 删除 DB 相关文件

**Files:**
- Delete: `backend/data/db.py`
- Delete: `backend/repositories/briefing_repository.py`
- Delete: `backend/repositories/news_repository.py`
- Delete: `backend/repositories/price_repository.py`
- Delete: `backend/workers/briefing_worker.py`
- Delete: `backend/workers/news_worker.py`
- Delete: `backend/workers/price_worker.py`

- [ ] **Step 1: 逐一删除并验证 import 不报错**

```bash
# 删除前先确认没有其他文件依赖 db.py
grep -r "from backend.data.db\|from backend.repositories\|from backend.workers" backend/ --include="*.py" | grep -v __pycache__
```

如果还有引用，先处理完再删。

- [ ] **Step 2: 删除文件**

```bash
git rm backend/data/db.py \
       backend/repositories/briefing_repository.py \
       backend/repositories/news_repository.py \
       backend/repositories/price_repository.py \
       backend/workers/briefing_worker.py \
       backend/workers/news_worker.py \
       backend/workers/price_worker.py
```

- [ ] **Step 3: 提交**

```bash
git commit -m "chore!: remove DB layer and background workers

- Deleted: db.py, all repositories, all workers
- System is now stateless REST API + in-memory cache
- SQLite files (alerts.db, gold.db) no longer created

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: 清理空目录 + 确认主应用启动正常

**Files:**
- Modify: `backend/repositories/__init__.py`
- Modify: `backend/workers/__init__.py`

- [ ] **Step 1: 检查空目录**

```bash
ls backend/repositories/
ls backend/workers/
```

如果只剩 `__init__.py`，检查其内容是否导入了已删除的模块，如有则清空。

- [ ] **Step 2: 启动服务验证**

```bash
cd /Users/chenyanyu/DoSomeThing/gold-dashboard
pkill -f "uvicorn" 2>/dev/null || true
uvicorn backend.main:app --host 0.0.0.0 --port 18000
```

验证：
```
curl http://localhost:18000/api/health          # {"status":"ok"}
curl http://localhost:18000/api/realtime/xau/comex  # 有 price 字段
curl http://localhost:18000/api/realtime/au/au9999  # 有 price 字段
curl http://localhost:18000/api/chart/xau?source=comex  # 有 bars 字段
```

- [ ] **Step 3: 提交**

```bash
git commit -m "chore: clean up empty repository/worker dirs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Playwright E2E 验证

**Files:**
- Test: 用 Playwright 验证前端功能

- [ ] **Step 1: 启动后端**

```bash
pkill -f "uvicorn" 2>/dev/null; sleep 1
cd /Users/chenyanyu/DoSomeThing/gold-dashboard
uvicorn backend.main:app --host 0.0.0.0 --port 18000 &
sleep 3
```

- [ ] **Step 2: Playwright 验证**

```python
# backend/tests/e2e_test.py
from playwright.sync_api import sync_playwright

def test_price_cards_load():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://localhost:18000", wait_until="load")
        page.wait_for_selector("#card-XAUUSD", state="visible", timeout=15000)
        assert page.is_visible("#card-XAUUSD")
        price = page.text_content("#price-XAUUSD")
        print(f"XAUUSD price: {price}")
        assert price and price != "--"
        browser.close()

def test_chart_source_switch():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://localhost:18000", wait_until="load")
        page.wait_for_selector("#priceChart", state="visible", timeout=15000)
        # Switch to Sina
        page.select_option("#sel-xau", "sina")
        page.wait_for_timeout(5000)
        browser.close()
```

```bash
python -m playwright install chromium --quiet 2>/dev/null
cd /Users/chenyanyu/DoSomeThing/gold-dashboard
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.goto('http://localhost:18000', wait_until='load')
    page.wait_for_selector('#card-XAUUSD', state='visible', timeout=15000)
    print('✅ Cards loaded:', page.text_content('#price-XAUUSD'))
    page.wait_for_selector('#priceChart', state='visible', timeout=5000)
    print('✅ Chart visible')
    b.close()
"
```

- [ ] **Step 3: 提交测试**

```bash
git add backend/tests/e2e_test.py
git commit -m "test(e2e): add Playwright test for card + chart loading

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 实现顺序

按 Task 编号顺序执行：1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

每完成一个 Task 提交一次。Task 2（后端 price.py）是最核心的改动，建议第一个完成并验证后再继续。

**Plan complete and saved to `docs/superpowers/plans/2026-04-06-realtime-gold-architecture-plan.md`.**
