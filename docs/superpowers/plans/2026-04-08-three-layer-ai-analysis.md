# 三层 AI 分析实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 分析从两层扩展为三层递进架构（新闻分析 → 行情验证 → 金价预期），前端按 3→2→1 顺序展示，每层独立刷新独立展示。

**Architecture:**
- 后端：`briefing.py` 新增 Layer 3 prompt + 函数；`briefing_service.py` 三层独立 cache + 独立 TTL，前端逐层加载即展示。
- 前端：`app.js` 每层独立骨架屏；`index.html` + `style.css` 三区块结构和样式。
- 三层均为 `async def`，通过 `call_claude_cli()` 调用 `claude -p`。

**Tech Stack:** Python FastAPI, Claude CLI (`claude -p`), JavaScript (Vanilla), HTML/CSS

---

## 错误处理与独立刷新

每层独立缓存、独立 TTL，允许逐层展示：

| 层级 | TTL | 说明 |
|------|-----|------|
| Layer 1 | 30 分钟 | 新闻分析变化较慢 |
| Layer 2 | 60 分钟 | Kline 验证相对稳定 |
| Layer 3 | 15 分钟 | 价格预期最需新鲜度 |

各层失败降级行为：
- Layer 1 失败 → 显示"暂无新闻分析"，L2/L3 跳过
- Layer 2 Kline 获取失败 → L2 降级为"信号不足"，L3 仍可运行（置信度低）
- Layer 3 失败 → 显示空，L1+L2 仍展示

前端：每层有独立骨架屏（skeleton），逐层加载完成即展示，无需等待全部完成。

---

## 文件变更总览

| 文件 | 变更 |
|------|------|
| `backend/data/sources/briefing.py` | 重写 Layer 1/2 prompt，更新输出格式；新增 `PRICE_FORECAST_TEMPLATE` + `generate_price_forecast()` |
| `backend/services/briefing_service.py` | 三层独立 cache + 独立 TTL；`_generate_analysis` 三层顺序调用；`get_briefing` 响应格式 `layer3/layer2/layer1/confidence` |
| `frontend/js/app.js` | 每层独立骨架屏和渲染；`_showBriefing()` 按 L3→L2→L1 渲染；`renderBriefing()` 支持 `【】` 格式高亮 |
| `frontend/index.html` | 三区块 DOM（id: `block-layer3`, `block-layer2`, `block-layer1`）；独立 skeleton |
| `frontend/css/style.css` | `.analysis-block--layer3/2/1` 样式；`.analysis-block__body--collapsed` 折叠；置信度颜色 |

---

## Task 1: 后端 — 更新 Layer 1 + Layer 2 Prompt，新增 Layer 3（`briefing.py`）

**Files:**
- Modify: `backend/data/sources/briefing.py`

**Steps:**

- [ ] **Step 1: 重写 `DAILY_PROMPT_TEMPLATE`**

替换现有的 `DAILY_PROMPT_TEMPLATE` 为：

```python
DAILY_PROMPT_TEMPLATE = """你是一位专业黄金市场分析师。基于近3日{news_count}条新闻（当前金价 ${current_price} USD/oz），请评估当前金价走势。

{news_list}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【走势判断】
上涨/震荡/下跌——逻辑一句话

【核心驱动】
★★★ 地缘/风险：（一行）
★★ 央行/宏观：（一行）
★ 市场/技术：（一行）

【时效性】
近24h重点新闻对走势的影响权重说明

【置信度】
高/中/低，理由一句话"""
```

- [ ] **Step 2: 更新 `generate_daily_briefing_from_news()` 函数签名**

```python
async def generate_daily_briefing_from_news(news: list[dict], current_price: str = "N/A") -> str:
    """Generate daily briefing text from news using Claude CLI."""
    if not news:
        return "暂无足够新闻数据生成日报。"
    news_list = _build_news_list(news)
    prompt = DAILY_PROMPT_TEMPLATE.format(
        news_count=len(news),
        news_list=news_list,
        current_price=current_price,
    )
    return call_claude_cli(prompt)
```

- [ ] **Step 3: 重写 `CROSS_VALIDATION_TEMPLATE`**

替换现有模板为：

```python
CROSS_VALIDATION_TEMPLATE = """你是一位专业黄金市场分析师。请将以下 Layer 1 新闻分析结论与 Layer 2 实际行情数据进行交叉对比，判断新闻判断是否与实际走势吻合。

【Layer 1 - 新闻分析结论】
{layer1_output}

【Layer 2 - Binance XAUUSD 日线聚合数据（5M K线）】
{kline_summary}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【验证结果】
一致 / 矛盾 / 信号不足

【实际走势】
从 Kline 数据提取的趋势描述（一句话）

【分歧说明】
如验证结果为"矛盾"，说明新闻预判与实际走势的差异；否则留空或写"无明显分歧"

【验证置信度】
高/中/低，理由一句话"""
```

- [ ] **Step 4: 更新 `generate_cross_validation()` 调用**

```python
async def generate_cross_validation(layer1_output: str, kline_data: list[dict]) -> str:
    """Step 2: cross-validate news analysis against Kline data."""
    kline_summary = aggregate_kline_for_prompt(kline_data)
    prompt = CROSS_VALIDATION_TEMPLATE.format(
        layer1_output=layer1_output,
        kline_summary=kline_summary,
    )
    try:
        return call_claude_cli(prompt)
    except BriefingGenerationError:
        return ""
```

- [ ] **Step 5: 新增 `PRICE_FORECAST_TEMPLATE` 和 `generate_price_forecast()`**

在 `CROSS_VALIDATION_TEMPLATE` 之后、`_shanghai_ts` 之前新增：

```python
PRICE_FORECAST_TEMPLATE = """你是一位专业黄金市场分析师。基于以下 Layer 1 新闻分析与 Layer 2 行情验证的结论，给出短期金价走势预期。

【Layer 1 - 新闻分析结论】
{layer1_output}

【Layer 2 - 行情验证结论】
{layer2_output}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【方向预期】
短期（1-3日）方向：上涨/震荡/下跌，理由一句话

【价格目标】
支撑位：XXX USD/oz
压力位：XXX USD/oz

【时间框架】
预期生效窗口：X-X日

【风险提示】
可能推翻预期的关键事件（1-2条）

【综合置信度】
高/中/低
理由：基于 Layer 2 验证一致性说明"""


async def generate_price_forecast(layer1_output: str, layer2_output: str) -> str:
    """Step 3: Generate price forecast based on Layer 1 + Layer 2 conclusions."""
    prompt = PRICE_FORECAST_TEMPLATE.format(
        layer1_output=layer1_output,
        layer2_output=layer2_output,
    )
    try:
        return call_claude_cli(prompt)
    except BriefingGenerationError:
        return ""
```

- [ ] **Step 6: Commit**

```bash
git add backend/data/sources/briefing.py
git commit -m "feat: update prompts to structured 4-zone format, add Layer 3 forecast prompt"
```

---

## Task 2: 后端 — 三层独立 Cache + 独立 TTL（`briefing_service.py`）

**Files:**
- Modify: `backend/services/briefing_service.py`

**Steps:**

- [ ] **Step 1: 更新 Cache 结构和 TTL 常量**

将文件顶部的常量和 cache 变量替换为：

```python
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_NEWS_TTL = 600          # 10 minutes
_LAYER1_TTL = 1800      # 30 minutes
_LAYER2_TTL = 3600      # 60 minutes
_LAYER3_TTL = 900       # 15 minutes

_news_cache: dict = {"ts": 0, "data": None}

# Per-layer independent caches
_layer1_cache: dict = {"ts": 0, "data": ""}
_layer2_cache: dict = {"ts": 0, "data": ""}
_layer3_cache: dict = {"ts": 0, "data": ""}
```

- [ ] **Step 2: 新增 `_fetch_current_price()` 辅助函数**

```python
def _fetch_current_price() -> str:
    """Fetch current XAUUSD price for Layer 1 prompt injection."""
    try:
        from backend.data.sources import binance_kline
        ticker = binance_kline._fetch_ticker()
        if ticker:
            return str(ticker["price"])
    except Exception:
        pass
    return "N/A"
```

- [ ] **Step 3: 新增独立 cache getter/setter 函数**

```python
def _get_layer1(news: list[dict], days: int, current_price: str) -> str:
    """Layer 1 cache with 30-min TTL."""
    if (
        _layer1_cache["data"] != ""
        and (time.time() - _layer1_cache["ts"]) < _LAYER1_TTL
    ):
        return _layer1_cache["data"]
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer1 = asyncio.run(mod.generate_daily_briefing_from_news(news, current_price))
    _layer1_cache["data"] = layer1
    _layer1_cache["ts"] = time.time()
    return layer1


def _get_layer2(layer1: str, kline_data: list[dict] | None) -> str:
    """Layer 2 cache with 60-min TTL. Falls back to 'signal insufficient' if kline unavailable."""
    if (
        _layer2_cache["data"] != ""
        and (time.time() - _layer2_cache["ts"]) < _LAYER2_TTL
    ):
        return _layer2_cache["data"]
    if not kline_data:
        fallback = "【验证结果】信号不足\n【实际走势】K线数据暂不可用\n【分歧说明】\n【验证置信度】低"
        _layer2_cache["data"] = fallback
        _layer2_cache["ts"] = time.time()
        return fallback
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer2 = asyncio.run(mod.generate_cross_validation(layer1, kline_data))
    if not layer2:
        layer2 = "【验证结果】信号不足\n【实际走势】分析生成失败\n【分歧说明】\n【验证置信度】低"
    _layer2_cache["data"] = layer2
    _layer2_cache["ts"] = time.time()
    return layer2


def _get_layer3(layer1: str, layer2: str) -> str:
    """Layer 3 cache with 15-min TTL."""
    if (
        _layer3_cache["data"] != ""
        and (time.time() - _layer3_cache["ts"]) < _LAYER3_TTL
    ):
        return _layer3_cache["data"]
    import importlib
    mod = importlib.import_module("backend.data.sources.briefing")
    layer3 = asyncio.run(mod.generate_price_forecast(layer1, layer2))
    _layer3_cache["data"] = layer3
    _layer3_cache["ts"] = time.time()
    return layer3
```

- [ ] **Step 4: 新增 `_run_three_layers()` 主函数，替换现有的 `_generate_analysis()`**

```python
def _run_three_layers(news: list[dict], days: int) -> dict:
    """Run all three layers sequentially and cache each independently."""
    if not news:
        return {"layer1": "暂无足够新闻数据生成分析。", "layer2": "", "layer3": ""}

    # Step 1: Layer 1 (concurrent with Kline fetch)
    current_price = _fetch_current_price()

    async def _layer1_task() -> tuple[str, list[dict] | None]:
        async def gen() -> str:
            import importlib
            mod = importlib.import_module("backend.data.sources.briefing")
            return await mod.generate_daily_briefing_from_news(news, current_price)

        def fetch_kline():
            from backend.data.sources import binance_kline
            return binance_kline.fetch_xauusd_kline()

        results = await asyncio.gather(
            asyncio.to_thread(fetch_kline),
            gen(),
            return_exceptions=True,
        )
        kline_data = results[0] if not isinstance(results[0], Exception) else None
        layer1 = results[1] if not isinstance(results[1], Exception) else ""
        if not layer1:
            layer1 = f"近{days}日共{len(news)}条新闻，详情见列表。"
        return (layer1, kline_data)

    layer1, kline_data = asyncio.run(_layer1_task())

    # Step 2: Layer 2
    layer2 = _get_layer2(layer1, kline_data)

    # Step 3: Layer 3
    layer3 = _get_layer3(layer1, layer2)

    logger.info(
        f"Three-layer analysis: L1={len(layer1)} chars, "
        f"L2={len(layer2)} chars, L3={len(layer3)} chars"
    )
    return {"layer1": layer1, "layer2": layer2, "layer3": layer3}
```

- [ ] **Step 5: 更新 `get_briefing()` 响应格式**

```python
def get_briefing(days: int = 3) -> dict:
    """Return cached briefing + news. Each layer refreshed independently on its own TTL."""
    news = _get_news(days)
    three_layers = _run_three_layers(news, days)
    return {
        "weekly": {
            "layer3": three_layers["layer3"],
            "layer2": three_layers["layer2"],
            "layer1": three_layers["layer1"],
            "confidence": _extract_confidence(three_layers),
            "time_range": _time_range(days),
            "news_count": len(news),
        },
        "news": news,
        "news_count": len(news),
    }
```

- [ ] **Step 6: 新增 `_extract_confidence()` 辅助函数**

```python
def _extract_confidence(three_layers: dict) -> str:
    """Extract overall confidence: prefer Layer 3, fall back to Layer 2."""
    for layer_key in ("layer3", "layer2"):
        text = three_layers.get(layer_key, "")
        if not text:
            continue
        for line in text.split("\n"):
            if "置信度" in line:
                for kw in ["高", "中", "低"]:
                    if kw in line:
                        return kw
    return "低"
```

- [ ] **Step 7: 同步更新 `refresh_news()` 和 `refresh_briefing_only()` 返回格式**

两者都改为与 `get_briefing()` 一致的 `weekly` 格式（`layer3/layer2/layer1`）。

- [ ] **Step 8: Commit**

```bash
git add backend/services/briefing_service.py
git commit -m "feat: per-layer independent cache and TTL in briefing_service"
```

---

## Task 3: 前端 — 三区块独立骨架屏渲染（`app.js`）

**Files:**
- Modify: `frontend/js/app.js`

**Steps:**

- [ ] **Step 1: 新增置信度和图标常量**

在 `escapeHtml` 函数附近新增：

```javascript
const CONFIDENCE_COLORS = { "高": "#d4af37", "中": "#fb923c", "低": "#9ca3af" };
const CONFIDENCE_ICONS = { "高": "✅", "中": "⚠️", "低": "❌" };
```

- [ ] **Step 2: 新增 `_renderBlock()` 辅助函数**

```javascript
/** Render a single analysis block (L3/L2/L1) with label and text. */
function _renderBlock(icon, title, text, extraHeaderHtml = "") {
  const body = text
    ? renderBriefing(text)
    : `<div class="state-message">正在生成...</div>`;
  return `<div class="analysis-block__body">${body}</div>`;
}
```

- [ ] **Step 3: 重写 `_showBriefing()` 函数**

```javascript
/** Show AI briefing in three independent blocks: L3 → L2 → L1 (L1 collapsible). */
function _showBriefing(data) {
  const weeklyEl = document.getElementById("weekly-content");
  const weeklySkeleton = document.getElementById("briefing-skeleton");
  const weeklyContent = document.getElementById("briefing-content");
  if (weeklySkeleton) weeklySkeleton.style.display = 'none';
  if (weeklyContent) weeklyContent.style.display = 'block';
  if (!weeklyEl) return;

  const weekly = data.weekly || {};
  const layer3 = weekly.layer3 || "";
  const layer2 = weekly.layer2 || "";
  const layer1 = weekly.layer1 || "";
  const confidence = weekly.confidence || "低";
  const confColor = CONFIDENCE_COLORS[confidence] || "#9ca3af";
  const confIcon = CONFIDENCE_ICONS[confidence] || "❌";

  weeklyEl.innerHTML = `
    <div class="analysis-block analysis-block--layer3" id="block-layer3">
      <div class="analysis-block__header">
        <span class="analysis-block__icon">🎯</span>
        <span class="analysis-block__title">金价预期</span>
        <span class="analysis-block__confidence" style="color:${confColor}">${confIcon} ${confidence}</span>
      </div>
      ${layer3
        ? `<div class="analysis-block__body">${renderBriefing(layer3)}</div>`
        : `<div class="analysis-block__body"><div class="state-message">正在生成...</div></div>`}
    </div>

    <div class="analysis-block analysis-block--layer2" id="block-layer2">
      <div class="analysis-block__header">
        <span class="analysis-block__icon">📊</span>
        <span class="analysis-block__title">行情验证</span>
      </div>
      ${layer2
        ? `<div class="analysis-block__body">${renderBriefing(layer2)}</div>`
        : `<div class="analysis-block__body"><div class="state-message">正在生成...</div></div>`}
    </div>

    <div class="analysis-block analysis-block--layer1" id="block-layer1">
      <div class="analysis-block__header analysis-block__header--toggle" id="layer1-toggle">
        <span class="analysis-block__icon">📰</span>
        <span class="analysis-block__title">新闻分析</span>
        <span class="analysis-block__chevron" id="layer1-chevron">▸</span>
      </div>
      <div class="analysis-block__body analysis-block__body--collapsed" id="layer1-body">
        ${layer1
          ? renderBriefing(layer1)
          : `<div class="state-message">暂无分析</div>`}
      </div>
    </div>
  `;

  // Wire up Layer 1 collapsible toggle
  const toggle = document.getElementById("layer1-toggle");
  const body = document.getElementById("layer1-body");
  const chevron = document.getElementById("layer1-chevron");
  if (toggle && body && chevron) {
    toggle.addEventListener("click", () => {
      const isCollapsed = body.classList.contains("analysis-block__body--collapsed");
      body.classList.toggle("analysis-block__body--collapsed");
      chevron.textContent = isCollapsed ? "▾" : "▸";
    });
  }
}
```

- [ ] **Step 4: 更新 `renderBriefing()` 支持 `【】` 格式高亮**

```javascript
/** Render briefing text, converting 【】 sections to styled HTML. */
function renderBriefing(text) {
  const escaped = escapeHtml(text || "");
  return escaped.replace(/^【(.+?)】/gm, '<span class="section-label">【$1】</span>');
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/js/app.js
git commit -m "feat: three-block independent rendering L3→L2→L1 with collapsible Layer 1"
```

---

## Task 4: 前端 — HTML + CSS（`index.html` + `style.css`）

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/css/style.css`

**Steps:**

- [ ] **Step 1: 更新 HTML 标题**

在 `index.html` 的 `.briefing-section` 内，将标题改为：

```html
<span class="briefing__title">🎯 AI 金价分析</span>
```

- [ ] **Step 2: 在 `style.css` 末尾追加三区块样式**

```css
/* ===== Three-Layer Analysis Blocks ===== */

.analysis-block {
  margin-bottom: 12px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--color-border);
}

/* Layer 3: 金价预期 — prominent gold border */
.analysis-block--layer3 {
  border-color: var(--color-gold);
  background: linear-gradient(135deg, rgba(212, 175, 55, 0.07) 0%, transparent 60%);
}

/* Layer 2: 行情验证 — subtle gold accent */
.analysis-block--layer2 {
  border-color: rgba(212, 175, 55, 0.3);
  background: rgba(212, 175, 55, 0.03);
}

/* Layer 1: 新闻分析 — muted, collapsible */
.analysis-block--layer1 {
  border-color: var(--color-border);
  background: transparent;
}
.analysis-block--layer1:hover {
  border-color: rgba(212, 175, 55, 0.3);
}

/* Block header */
.analysis-block__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
}

.analysis-block__header--toggle {
  cursor: pointer;
  user-select: none;
}

.analysis-block__icon { font-size: 14px; }

.analysis-block__title {
  font-size: 12px;
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: 0.5px;
  color: var(--color-text);
  flex: 1;
}

.analysis-block--layer3 .analysis-block__title {
  color: var(--color-gold);
}

.analysis-block__confidence {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
}

.analysis-block__chevron {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* Block body */
.analysis-block__body {
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--color-text);
}

.analysis-block__body--collapsed {
  display: none;
}

/* 【】 section labels */
.section-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-gold);
  font-family: var(--font-mono);
  margin-top: 8px;
  letter-spacing: 0.5px;
}
.section-label:first-child {
  margin-top: 0;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html frontend/css/style.css
git commit -m "feat: three-layer analysis HTML structure and CSS styles"
```

---

## Task 5: 端到端测试

**Steps:**

- [ ] **Step 1: 启动后端**

```bash
./start.sh restart
sleep 3
```

- [ ] **Step 2: 测试 API 响应格式**

```bash
curl -s "http://localhost:18000/api/briefings?days=3" | python3 -c "
import sys, json
d = json.load(sys.stdin)
w = d.get('weekly', {})
print('Keys:', list(w.keys()))
print('layer3 (80):', repr(w.get('layer3','')[:80]))
print('layer2 (80):', repr(w.get('layer2','')[:80]))
print('layer1 (80):', repr(w.get('layer1','')[:80]))
print('confidence:', w.get('confidence'))
"
```

Expected: Keys 包含 `layer3`, `layer2`, `layer1`, `confidence`

- [ ] **Step 3: 浏览器验证**

打开 `http://localhost:18000`，检查：
1. 三区块顺序：🎯 金价预期 → 📊 行情验证 → 📰 新闻分析（收起）
2. 点击 📰 新闻分析可展开/收起
3. 🎯 金价预期区块显示置信度标签（颜色正确）
4. `【】` 分区标题正确高亮为金色

- [ ] **Step 4: 强制刷新测试**

点击"🧠 刷新AI分析"按钮，等待各层逐层出现（不是全部完成才展示）

- [ ] **Step 5: Commit 最终**

```bash
git add -A
git commit -m "feat: three-layer AI analysis — news→validation→forecast with per-layer independent display"
```

---

## 自检清单

- [ ] Spec 覆盖：Layer 1/2/3 prompt、三层独立 cache、前端三区块展示、折叠交互、置信度颜色 — 全部有对应 Step
- [ ] Placeholder 扫描：无 "TBD"、"TODO"、未填写字段
- [ ] 类型一致性：`layer1/layer2/layer3` 字段名贯穿全程一致
- [ ] 错误处理：三层各自失败时有降级方案
- [ ] CSS 变量：`var(--color-gold)` 等均已在现有 `style.css` 中定义
