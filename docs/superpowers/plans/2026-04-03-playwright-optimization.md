# Playwright 性能优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Playwright 冷启动浏览器（15-25秒）优化为 persistent browser + auth header 缓存（< 1秒热请求）

**Architecture:**
- 新增 `BrowserManager` 单例，统一管理 Chromium 生命周期（启动一次，常驻进程）
- `_fetch_gf_once()` 增加 auth header 缓存（TTL=2h），缓存命中时走纯 requests（~0.35秒）
- `fetch_news()` 复用 BrowserManager 的 browser，不再每次 launch/close
- BrowserManager 在 FastAPI lifespan 启动/关闭，checker.py 通过单例访问

**Tech Stack:** Playwright (sync_api), threading.Lock, FastAPI lifespan, aiosqlite

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/data/sources/browser.py` | **NEW** — BrowserManager 单例，线程安全，lazy init |
| `backend/data/sources/international.py` | 修改 — auth 缓存 + `_fetch_gf_once` 重构 + `fetch_news(browser)` 参数 |
| `backend/alerts/checker.py` | 修改 — `_refresh_news()` 透传 BrowserManager 单例 |
| `backend/main.py` | 修改 — lifespan 启动/关闭 BrowserManager |

---

## Task 1: 创建 BrowserManager 单例

**Files:**
- Create: `backend/data/sources/browser.py`
- Test: `backend/tests/test_browser.py`

- [ ] **Step 1: 创建 `backend/data/sources/browser.py`**

```python
"""BrowserManager: 统一管理 Playwright Chromium 生命周期（单例，线程安全）."""
import logging
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class BrowserManager:
    """线程安全的 Chromium 单例管理器。"""
    _instance: "BrowserManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "BrowserManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._browser = None
        self._playwright = None
        self._initialized = True

    def launch(self) -> None:
        """启动 persistent Chromium（幂等，重复调用无害）。"""
        with self._lock:
            if self._browser is not None:
                return
            try:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    executable_path=CHROME_PATH,
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
                logger.info("BrowserManager: Chromium launched")
            except Exception as e:
                logger.warning(f"BrowserManager: launch failed: {e}")
                self._browser = None

    def close(self) -> None:
        """关闭 Chromium（幂等）。"""
        with self._lock:
            if self._browser is not None:
                try:
                    self._browser.close()
                    self._browser = None
                except Exception as e:
                    logger.warning(f"BrowserManager: close error: {e}")
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                    self._playwright = None
                except Exception as e:
                    logger.warning(f"BrowserManager: playwright stop error: {e}")
            logger.info("BrowserManager: Chromium closed")

    @property
    def browser(self):
        """返回 browser 实例，若未启动则 lazy launch。"""
        with self._lock:
            if self._browser is None:
                self.launch()
            return self._browser

    def get_new_context(self):
        """每次调用创建新 context（隔离）。"""
        return self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
```

- [ ] **Step 2: 创建 `backend/tests/test_browser.py`**

```python
"""Tests for BrowserManager."""
import pytest
import threading
import time
from backend.data.sources.browser import BrowserManager


def test_singleton():
    """验证 BrowserManager 是单例。"""
    b1 = BrowserManager()
    b2 = BrowserManager()
    assert b1 is b2


def test_thread_safety():
    """验证多线程访问不崩溃（不验证真实浏览器启动，只验证锁机制）。"""
    results = []
    errors = []

    def get_browser():
        try:
            bm = BrowserManager()
            # 不真正启动浏览器，只验证 lock 不冲突
            results.append(id(bm))
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=get_browser) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(set(results)) == 1  # 同一实例


def test_launch_close_idempotent():
    """验证 launch/close 幂等。"""
    bm = BrowserManager()
    bm.launch()
    bm.launch()  # 重复 launch 不报错
    bm.close()
    bm.close()  # 重复 close 不报错
```

- [ ] **Step 3: 运行测试验证**

Run: `cd /Users/chenyanyu/telegram-claude-bot/gold-dashboard && python -m pytest backend/tests/test_browser.py -v`
Expected: 3 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/data/sources/browser.py backend/tests/test_browser.py
git commit -m "feat(browser): add thread-safe BrowserManager singleton

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 添加 auth header 缓存并重构 `_fetch_gf_once()`

**Files:**
- Modify: `backend/data/sources/international.py`（在文件顶部 `_TTL` 定义区域附近添加 `_gf_auth_cache`，在 `_fetch_gf_once` 函数内重构逻辑）
- No new test file (复用现有 `demo_cdp.py` 端到端验证)

- [ ] **Step 1: 在 `international.py` 顶部添加 auth 缓存变量（在 `_xau_cache` 附近）**

在 `_xau_cache = {"data": None, "timestamp": 0.0}` 后添加：

```python
# Google Finance auth header 缓存（TTL 2小时，避免每次都启动浏览器）
_gf_auth_cache: dict = {
    "url": None,         # batchexecute URL（含完整 query string）
    "body": None,        # 原始 URL-encoded POST body
    "auth_header": None, # (header_name, header_value)
    "timestamp": 0.0,
}
_AUTH_CACHE_TTL = 7200  # 2小时
```

- [ ] **Step 2: 添加 `_ensure_auth_header()` 函数（在 `_fetch_gf_once` 前）**

```python
def _ensure_auth_header() -> bool:
    """确保 _gf_auth_cache 有效。返回 True=已就绪，False=失败（缓存或新获取均不可用）。"""
    now = time.time()
    if _gf_auth_cache["auth_header"] and (now - _gf_auth_cache["timestamp"]) < _AUTH_CACHE_TTL:
        return True

    # 缓存未命中或已过期，通过 BrowserManager 获取
    from backend.data.sources.browser import BrowserManager
    bm = BrowserManager()
    browser = bm.browser
    if browser is None:
        logger.warning("_ensure_auth_header: browser unavailable")
        return False

    try:
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        with page.expect_request(lambda r: "AiCwsd" in r.url, timeout=25000) as req_info:
            page.goto(
                "https://www.google.com/finance/quote/GCW00:COMEX",
                wait_until="domcontentloaded",
                timeout=20000,
            )
        req = req_info.value
        _gf_auth_cache["url"] = req.url
        _gf_auth_cache["body"] = req.post_data or ""
        for name, val in req.headers.items():
            if name.startswith("x-goog-ext"):
                _gf_auth_cache["auth_header"] = (name, val)
                break
        _gf_auth_cache["timestamp"] = time.time()
        logger.info(f"GF auth header cached: {_gf_auth_cache['auth_header'][0]}")
        context.close()
        return bool(_gf_auth_cache["auth_header"])
    except Exception as e:
        logger.warning(f"_ensure_auth_header failed: {e}")
        return False
```

- [ ] **Step 3: 添加 `_invalidate_auth_cache()` 函数**

```python
def _invalidate_auth_cache() -> None:
    """主动 invalidate auth cache（收到 403 时调用）。"""
    _gf_auth_cache["auth_header"] = None
    _gf_auth_cache["timestamp"] = 0.0
    logger.info("GF auth cache invalidated")
```

- [ ] **Step 4: 重构 `_fetch_gf_once()` 为 `_fetch_gf_with_cached_auth()`**

将原 `_fetch_gf_once()` 函数签名改为 `_fetch_gf_with_cached_auth(window: int)`，在函数开头：

```python
def _fetch_gf_with_cached_auth(window: int) -> list[dict] | None:
    """用缓存的 auth header 发 GF batchexecute 请求，失败时 invalidate 并重试一次。"""
    if not _ensure_auth_header():
        return None

    url = _gf_auth_cache["url"]
    body = _gf_auth_cache["body"]
    auth_header = _gf_auth_cache["auth_header"]
    assert url and body and auth_header

    # 替换 window 参数并发送
    decoded = urllib.parse.unquote(body)
    if window != 1:
        decoded = re.sub(r'\],\d+,', '],' + str(window) + ',', decoded, count=1)

    header_name, header_value = auth_header
    headers = {
        header_name: header_value,
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Referer": "https://www.google.com/finance/quote/GCW00:COMEX",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    def _do_request() -> str:
        resp = requests.post(url, data=decoded.encode("utf-8"), headers=headers, timeout=15)
        if resp.status_code == 400:
            body2 = resp.text
            if '"e",4' in body2:  # auth error code
                _invalidate_auth_cache()
                return "AUTH_ERROR"
        resp.raise_for_status()
        return resp.text

    raw = _do_request()
    if raw == "AUTH_ERROR":
        # 重试一次（auth 失效后重新获取）
        if not _ensure_auth_header():
            return None
        raw = _do_request()
        if raw == "AUTH_ERROR":
            return None

    return _parse_gf_raw(raw)
```

- [ ] **Step 5: 更新 `fetch_gf_xauusd_history()` 调用新的函数名**

在 `fetch_gf_xauusd_history()` 中，将 `records = _fetch_gf_once(window)` 改为 `records = _fetch_gf_with_cached_auth(window)`。

- [ ] **Step 6: 端到端验证**

Run: `cd /Users/chenyanyu/telegram-claude-bot/gold-dashboard && python3 -c "
from backend.data.sources.international import fetch_gf_xauusd_history
import time

# 第一次（冷启动）
t0 = time.time()
bars = fetch_gf_xauusd_history(1)
print(f'Cold: {time.time()-t0:.1f}s, bars={len(bars)}')

# 第二次（热请求，应走缓存）
t1 = time.time()
bars2 = fetch_gf_xauusd_history(1)
print(f'Hot:  {time.time()-t1:.3f}s, bars={len(bars2)}')
print('PASS' if bars and bars2 else 'FAIL')
"`
Expected: Cold ~12s, Hot < 1s

- [ ] **Step 7: 提交**

```bash
git add backend/data/sources/international.py
git commit -m "perf(international): add auth header cache, reuse requests for GF batchexecute

- Add _gf_auth_cache with 2h TTL
- Add _ensure_auth_header() + _invalidate_auth_cache()
- Rename _fetch_gf_once -> _fetch_gf_with_cached_auth with retry-on-403
- Cold ~12s, hot < 1s

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 重构 `fetch_news()` 复用 BrowserManager

**Files:**
- Modify: `backend/data/sources/international.py`（修改 `fetch_news()` 函数签名和内部逻辑）

- [ ] **Step 1: 修改 `fetch_news()` 签名和实现**

将 `def fetch_news() -> list[dict]:` 改为：

```python
def fetch_news(browser=None) -> list[dict]:
    """Scrape related news from Google Finance GCW00:COMEX page.

    Args:
        browser: Playwright Browser instance. If None, launches a temporary one.
                 Reusing the same browser avoids cold-start overhead.
    """
    global _news_cache, _news_timestamp
    now = time.time()
    if _news_cache and (now - _news_timestamp) < _NEWS_TTL:
        return sorted(_news_cache, key=lambda x: _time_ago_minutes(x["time_ago"]))

    _scrape_sync = _build_news_scraper()

    def do_scrape(br):
        return _scrape_sync(br)

    if browser is not None:
        parsed = do_scrape(browser)
    else:
        from backend.data.sources.browser import BrowserManager
        bm = BrowserManager()
        br = bm.browser
        if br is None:
            logger.warning("fetch_news: no browser available")
            return _news_cache if _news_cache else []
        parsed = do_scrape(br)

    # ... 后续 save news + return 逻辑保持不变 ...
```

将 `_scrape_sync` 的 Playwright 逻辑抽取为 `_build_news_scraper()` → 返回一个接收 `browser` 参数的闭包：

```python
def _build_news_scraper():
    """返回可复用的新闻爬取函数（接收 browser 参数）。"""
    def scrape(browser) -> list[dict]:
        if browser is None:
            return []
        with browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        ) as context:
            page = context.new_page()
            page.goto(
                "https://www.google.com/finance/quote/GCW00:COMEX?comparison=USD-CNY",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            page.wait_for_timeout(10000)
            # ... 后续 DOM 解析逻辑完全保持不变 ...
            return news
    return scrape
```

- [ ] **Step 2: 端到端验证**

Run: `cd /Users/chenyanyu/telegram-claude-bot/gold-dashboard && python3 -c "
from backend.data.sources.international import fetch_news
import time
t0 = time.time()
news = fetch_news()
print(f'News: {time.time()-t0:.1f}s, count={len(news)}')
print('PASS' if news else 'FAIL')
"`
Expected: < 5s

- [ ] **Step 3: 提交**

```bash
git add backend/data/sources/international.py
git commit -m "perf(international): reuse BrowserManager in fetch_news()

- Add browser parameter to fetch_news()
- Extract DOM scrape logic into _build_news_scraper()
- Falls back to BrowserManager singleton if no browser passed

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 集成 BrowserManager 到 FastAPI lifespan

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/alerts/checker.py`

- [ ] **Step 1: 修改 `main.py` lifespan**

在 `backend/main.py` 顶部添加：

```python
from backend.data.sources.browser import BrowserManager
```

修改 `lifespan`：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Launch persistent Chromium (non-blocking, runs in bg thread)
    import threading
    def launch_browser():
        BrowserManager().launch()
    threading.Thread(target=launch_browser, daemon=True).start()

    # Pre-fetch news immediately so first request is fast
    from backend.alerts.checker import _refresh_news
    asyncio.create_task(_refresh_news())

    start_scheduler(interval_sec=30)
    logger.info("Gold Dashboard started")
    yield
    # Shutdown
    BrowserManager().close()
    scheduler.shutdown()
```

- [ ] **Step 2: 修改 `checker.py` 中的 `_refresh_news()`**

`fetch_news` 已支持 `browser=None` 回退到 BrowserManager 单例，无需改动 `checker.py`。确认一下即可。

在 `backend/alerts/checker.py` 中，确认 `_fetch_news` 的调用方式：

```python
# 当前代码（保持不变，fetch_news 会自动用 BrowserManager 单例）：
news = await loop.run_in_executor(None, _fetch_news)
```

无需改动 —— `fetch_news(browser=None)` 会自动从 BrowserManager 获取 browser。

- [ ] **Step 3: 启动服务验证**

Run: `cd /Users/chenyanyu/telegram-claude-bot/gold-dashboard && timeout 15 python -c "
import sys
sys.path.insert(0, '.')
from backend.main import app
import asyncio
# 验证 lifespan 不报错
from backend.main import lifespan
print('lifespan import OK')
" 2>&1`

- [ ] **Step 4: 提交**

```bash
git add backend/main.py backend/alerts/checker.py
git commit -m "feat(main): integrate BrowserManager lifecycle in FastAPI lifespan

- BrowserManager launches in startup (daemon thread)
- BrowserManager closes in shutdown
- fetch_news() via checker uses BrowserManager singleton (no change needed)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 最终端到端验证

- [ ] **Step 1: 启动服务，手动触发 K 线请求**

Run: `cd /Users/chenyanyu/telegram-claude-bot/gold-dashboard && ./run.sh &`
Wait 15s for startup, then:

```bash
curl -s http://localhost:18000/api/history/XAUUSD?days=1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'bars: {len(d[\"bars\"])}, xMin: {d[\"xMin\"]}')"
```

Expected: `bars: ~1000, xMin: <timestamp>`（< 1s response）

- [ ] **Step 2: 检查服务日志无 ERROR**

Expected: 无 Python traceback

- [ ] **Step 3: 提交最终状态**

```bash
git add -A && git commit -m "chore: playwright optimization complete

- BrowserManager singleton with thread-safe lazy launch
- GF auth header cache (2h TTL) -> requests replay
- fetch_news() reuses persistent Chromium
- Cold: ~12s, Hot: < 1s, News: < 5s

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 风险 & 降级

| 场景 | 行为 |
|------|------|
| Chromium 启动失败 | `BrowserManager().browser` 返回 `None`，`fetch_news` 回退到临时启动 |
| Auth header 收到 403 | `_invalidate_auth_cache()` + 重试一次 |
| 多 uvicorn worker | **单 worker 模式**（`--workers 1`），避免多个 Chromium 进程 |
