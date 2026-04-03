# Playwright 性能优化设计方案

## 背景

当前 `backend/data/sources/international.py` 中有两处 Playwright 调用，每次调用都冷启动 Chromium，导致严重延迟：

1. **`_fetch_gf_once()`** — 获取 GCW00:COMEX 历史 K 线，依赖 Playwright 捕获 `x-goog-ext-*` auth header 后再通过 `requests` Replay，平均耗时 15-25 秒
2. **`fetch_news()`** — 爬取 Google Finance 黄金页面的新闻链接，等 DOM 渲染 + 提取链接，平均耗时 10-15 秒

优化目标：**保留 Google Finance 作为唯一数据源**，仅改变 Playwright 调用方式。

**Demo 验证结果：**
- 浏览器启动 + 捕获：~12秒（一次性）
- 缓存 auth header 后，requests 重放：~0.35秒/请求
- 1D 窗口：1021 根 K线 ✓；5D 窗口：211 根 ✓；30D 窗口：24 根 ✓

---

## 设计方案

### 1. 单一 Persistent Chromium 实例

所有 Playwright 操作共用一个 Chromium 实例，由 `BrowserManager` 统一管理生命周期：

```
BrowserManager (persistent chromium, 启动一次)
├── K线 auth header 获取：用 expect_request() 捕获
└── 新闻爬取：用 page.goto() + DOM 解析
```

优势：只占用一个 Chrome 进程（~200MB），无需区分两种浏览器生命周期，逻辑更简单。

### 2. Auth Header 缓存（K 线加速）

**认证机制分析：**
- Google Finance batchexecute API 必须带 `x-goog-ext-*` header 才能返回 200
- 不带该 header → Google RPC 错误码 4（认证 token 缺失）→ 400
- 该 header 值每次浏览器会话不同（格式：`x-goog-ext-{id}-jspb: ["HK","ZZ","{base64}"]`）
- 该 header 在浏览器会话存活期内有效（至少 2 小时），与 session cookie 无关

**改动：**
- 模块级缓存 `_gf_auth_cache: dict = {"url": None, "body": None, "auth_header": None, "timestamp": 0.0}`
- 获取前检查缓存是否存在且未过期（TTL = 2 小时）
- 若缓存未命中：启动 Chromium，捕获后存入缓存，不关闭浏览器
- 后续 K 线请求全部走 `requests` + 缓存 auth header

**Body 编码注意：**
- `body_template` 必须是原始 URL-encoded 字符串（直接从 Playwright `post_data` 捕获）
- 使用前：`urllib.parse.unquote(body_template)` → 替换 window 参数 → `new_body.encode("utf-8")` 直接发送
- **禁止** `requests.post(data={"f.req": new_body})`（会自动重新编码导致 400）

### 3. 新闻爬取（复用 Chromium）

**现状：**
- `fetch_news()` 每次调用都 `sync_playwright() → p.chromium.launch() → browser.close()`

**改动：**
- `BrowserManager` 启动后保持 persistent Chromium 在 `app.state.chromium_browser` 引用中
- `fetch_news()` 接收 `browser` 参数，不再 `launch()`/`close()`
- 若 `browser` 参数为 `None`，回退到原有每次启动方式（保持兼容）

### 4. BrowserManager 生命周期

```python
class BrowserManager:
    _instance: BrowserManager | None = None

    def __init__(self):
        self._browser = None

    def launch(self) -> None:
        """在 FastAPI startup 时调用，启动 persistent Chromium."""
        ...

    def close(self) -> None:
        """在 FastAPI shutdown 时调用，关闭 Chromium."""
        ...

    @property
    def browser(self):
        return self._browser
```

在 `main.py` lifespan 中：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    bm = BrowserManager()
    bm.launch()
    app.state.browser = bm.browser
    yield
    bm.close()
```

### 5. 错误处理

| 场景 | 行为 |
|------|------|
| Chromium launch 失败 | 回退到每次 `sync_playwright()` 方式 |
| auth header 捕获超时（25s） | 返回缓存或 `None`，不阻塞服务 |
| requests 重放收到 403/400 | invalidate auth cache，重试一次；若再次失败，记录 WARNING |
| 新闻爬取异常 | 回退到每次启动方式，保留原有逻辑 |

---

## 文件改动清单

| 文件 | 改动内容 |
|------|----------|
| `backend/data/sources/international.py` | 1. 新增 `_gf_auth_cache` 及 TTL；2. 重构 `_fetch_gf_once()` 使用缓存；3. `fetch_news()` 新增 `browser` 参数 |
| `backend/alerts/checker.py` | 透传 `browser` 给 `fetch_news()` |
| `backend/main.py` | lifespan 中启动/关闭 `BrowserManager`；`app.state.browser` 挂载 Chromium 实例 |
| `backend/routers/price.py` | 透传 `request.app.state.browser` |
| `backend/data/sources/browser.py` | 新增 `BrowserManager` 类 |

---

## 测试计划

1. **K线冷启动**：清空缓存，手动触发一次 K 线请求，记录耗时（目标 < 15 秒，含浏览器启动）
2. **K线热请求**：5 分钟内再次触发，验证走 requests 缓存路径（目标 < 1 秒）
3. **Auth header 失效重试**：手动 invalidate 缓存，验证自动重新捕获逻辑
4. **新闻爬取**：手动触发新闻刷新，记录耗时（目标 < 5 秒）
5. **回退机制**：模拟 Chromium 不可用，验证每次启动方式仍可工作
6. **并发测试**：K线和新闻同时触发，验证无竞争条件

---

## 风险评估

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| auth header 在缓存期内失效（403） | 中 | 中 | 捕获 403 后主动 invalidate 并重试一次 |
| Chromium 进程异常退出 | 低 | 高 | BrowserManager 检测到 `_browser is None` 时重建 |
| Google Finance 页面结构变化 | 低 | 高 | 缓存失效后自动重试；完全失败时返回 None |
| 多 worker 进程同时启动 Chromium | 中 | 中 | uvicorn 用 `--workers 1` 或单例锁 |
