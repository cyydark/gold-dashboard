# gold-dashboard 5分钟图表重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除时间切换按钮，图表固定显示最近72小时5分钟K线数据，新增双轴 crosshair 交互（垂直虚线 + Canvas 绘制交点价格/时间）。

**Architecture:** Crosshair 通过 Chart.js `afterDatasetsDraw` + `afterEvent` 插件实现，监听 `mousemove` 在 Canvas 上直接绘制垂直虚线和交点数据。xMin/xMax 固定为 `now - 72h / now`，不做重叠计算。

**Tech Stack:** Chart.js 4.4, chartjs-adapter-date-fns 3.0, chartjs-plugin-annotation 3.0

---

## 文件修改范围

| 文件 | 操作 |
|------|------|
| `frontend/js/chart.js` | 移除 xMin/xMax 重叠计算，新增 Crosshair 插件，注释 Emoji 插件 |
| `frontend/js/app.js` | 确认 `chart.load()` 无参数，warmup 清理 |
| `frontend/index.html` | 已确认无时间切换按钮（上一轮已移除） |

---

## Task 1: 注释 Emoji 新闻标注插件

**Files:**
- Modify: `frontend/js/chart.js:11-106`

- [ ] **Step 1: 用 `/* */` 注释掉整个 emojiMarkers Chart.register 块**

打开 `frontend/js/chart.js`，找到第 11-106 行的 `Chart.register({ id: "emojiMarkers", ... })` 块，用 `/*` 和 `*/` 包裹整块代码。

验证：文件语法仍正确（JS 多行注释嵌套单行注释无问题）。

---

## Task 2: 移除 xMin/xMax 重叠计算

**Files:**
- Modify: `frontend/js/chart.js:239-244`

- [ ] **Step 1: 读取 chart.js 第 239-250 行当前代码**

确认 `xMin` 和 `xMax` 当前计算逻辑（重叠计算版本）。

- [ ] **Step 2: 将 xMin/xMax 改为固定 72 小时**

将：
```javascript
const xMin = xauResp ? toBeijingDate(xauResp.xMin) : new Date(Date.now() - days * 86400 * 1000);
const xMax = new Date();
```

改为：
```javascript
const now = new Date();
const xMax = now;
const xMin = new Date(now.getTime() - 72 * 60 * 60 * 1000);
```

同时删除第 239 行的 `const unit = days <= 1 ? "minute" : days <= 5 ? "hour" : "day";`（5分钟数据始终用 `"minute"`）。

---

## Task 3: 新增 Crosshair 插件

**Files:**
- Modify: `frontend/js/chart.js`（在 emojiMarkers 被注释的插件块之后插入）

- [ ] **Step 1: 在文件顶部（`class GoldChart` 定义之前）新增 Crosshair 插件**

在 `Chart.register({ id: "emojiMarkers", ... })` 被注释块之后，`class GoldChart` 之前，插入：

```javascript
/**
 * Crosshair: vertical dashed line + floating label with time + both prices.
 * Drawn in afterDatasetsDraw so it's always on top of data.
 * Interaction handled in afterEvent (mousemove).
 */
const _crosshairPlugin = {
  id: "crosshair",

  // Shared mouse position (reset each draw cycle)
  _mouseX: null,

  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea || !scales.x || !scales.y) return;
    if (this._mouseX === null) return;

    const xPx = this._mouseX;
    if (xPx < chartArea.left || xPx > chartArea.right) return;

    // ── Vertical dashed line ──────────────────────────────────────────────
    ctx.save();
    ctx.beginPath();
    ctx.strokeStyle = "rgba(148,163,184,0.5)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.moveTo(xPx, chartArea.top);
    ctx.lineTo(xPx, chartArea.bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    // ── Find nearest data point for each dataset ───────────────────────
    const xScale = scales.x;
    const rawTs = xScale.getValueForPixel(xPx); // timestamp
    const datasets = chart.data.datasets;

    const findNearest = (data) => {
      if (!data || !data.length) return null;
      let closest = data[0], minDiff = Infinity;
      for (const pt of data) {
        const d = Math.abs(pt.x - rawTs);
        if (d < minDiff) { minDiff = d; closest = pt; }
      }
      return closest;
    };

    const xauPt = findNearest(chart._goldXauData || []);
    const auPt  = findNearest(chart._goldAuData  || []);

    // ── Build label lines ──────────────────────────────────────────────
    const pad = n => String(n).padStart(2, "0");
    const toBJ = (d) => {
      const bj = new Date(d);
      return `${pad(bj.getMonth()+1)}月${pad(bj.getDate())}日 ${pad(bj.getHours())}:${pad(bj.getMinutes())}`;
    };
    const toUS = (d) => {
      const us = new Date(d - 12 * 3600 * 1000);
      return `${pad(us.getMonth()+1)}月${pad(us.getDate())}日 ${pad(us.getHours())}:${pad(us.getMinutes())}`;
    };

    const labelX = xPx + 8;
    const labelY = chartArea.top + 12;
    const lineH = 18;
    const padding = 8;

    const lines = [];
    if (rawTs) {
      lines.push(`⏰ ${toBJ(rawTs)} 北京`);
      lines.push(`    ${toUS(rawTs)} 美东`);
    }
    if (xauPt) {
      lines.push(`🟢 XAU/USD: ${xauPt.y.toFixed(2)}`);
    }
    if (auPt) {
      lines.push(`🟡 AU9999: ${auPt.y.toFixed(2)}`);
    }

    if (!lines.length) { ctx.restore(); return; }

    // ── Draw background box ────────────────────────────────────────────
    ctx.font = "12px Inter, sans-serif";
    const maxW = Math.max(...lines.map(l => ctx.measureText(l).width));
    const boxW = maxW + padding * 2;
    const boxH = lines.length * lineH + padding;
    let boxX = labelX;
    if (boxX + boxW > chartArea.right - 4) boxX = xPx - boxW - 8;

    ctx.fillStyle = "rgba(30,33,48,0.92)";
    ctx.beginPath();
    ctx.roundRect(boxX, labelY, boxW, boxH, 4);
    ctx.fill();

    // ── Draw text lines ────────────────────────────────────────────────
    ctx.fillStyle = "#94a3b8";
    ctx.textBaseline = "top";
    lines.forEach((line, i) => {
      const isFirst = i < 2; // time lines
      ctx.fillStyle = isFirst ? "#94a3b8" : (i === 2 ? "#22c55e" : "#f59e0b");
      ctx.fillText(line, boxX + padding, labelY + padding + i * lineH);
    });

    // ── Draw small dots at intersection with data lines ────────────────
    if (xauPt) {
      const yPx = scales.y.getPixelForValue(xauPt.y);
      if (yPx >= chartArea.top && yPx <= chartArea.bottom) {
        ctx.fillStyle = "#22c55e";
        ctx.beginPath();
        ctx.arc(xPx, yPx, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (auPt) {
      const yPx = scales.y2.getPixelForValue(auPt.y);
      if (yPx >= chartArea.top && yPx <= chartArea.bottom) {
        ctx.fillStyle = "#f59e0b";
        ctx.beginPath();
        ctx.arc(xPx, yPx, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    ctx.restore();
  },

  afterEvent(chart, args) {
    const { inChartArea } = args;
    if (args.event.type === "mousemove") {
      this._mouseX = inChartArea ? args.event.x : null;
      chart.draw(); // trigger afterDatasetsDraw
    } else if (args.event.type === "mouseout" || args.event.type === "mouseleave") {
      this._mouseX = null;
      chart.draw();
    }
  },
};

Chart.register(_crosshairPlugin);
```

- [ ] **Step 2: 在 GoldChart.load() 中设置 _goldAuData**

在 `load()` 方法中，`this._xauData = xauPts;` 之后添加：

```javascript
this._auData = auPts;
```

在 `this.chart._goldXauData = xauPts;` 之后添加：

```javascript
this.chart._goldAuData = auPts;
```

---

## Task 4: 确认 app.js 干净无按钮代码

**Files:**
- Modify: `frontend/js/app.js`

- [ ] **Step 1: 检查 app.js 是否还有 initControls 或 .range-btn 相关代码**

搜索 `initControls`、`range-btn`、`.range-btn` 关键字。如有，删除。

- [ ] **Step 2: 确认 DOMContentLoaded 为：**

```javascript
window.addEventListener("DOMContentLoaded", async () => {
  chart = new GoldChart();
  loadBriefings();
  await chart.load();
  chart.warmup();
  loadNews(1);
  setInterval(() => loadNews(1), 5 * 60 * 1000);
});
```

如果缺少 `loadNews` 和 `setInterval`，补全。

- [ ] **Step 3: warmup() 简化为直接调用（无 days 参数）：**

```javascript
warmup() {
  [1, 5, 30].forEach(() => {
    fetch(`/api/history/XAUUSD`).catch(() => {});
    fetch(`/api/history/AU9999`).catch(() => {});
  });
}
```

（或简化为只 warmup 一次，去掉 forEach 循环。）

---

## Task 5: 重启服务并验证

**Files:**
- 无文件修改

- [ ] **Step 1: 重启后端服务**

```bash
# 找到并杀掉旧进程
lsof -i :18000 | grep Python | awk '{print $2}' | xargs kill
# 重启
cd /Users/chenyanyu/DoSomeThing/gold-dashboard && python -m uvicorn backend.main:app --host 0.0.0.0 --port 18000 &
```

- [ ] **Step 2: 打开浏览器验证**

访问 `http://localhost:18000`，验证：
- 图表加载（不再显示"暂无数据"）
- 鼠标移动显示垂直虚线和价格/时间数据
- 无时间切换按钮

---

## 验证清单

- [ ] 图表渲染出两条曲线（绿色 XAU/USD，橙色 AU9999）
- [ ] 鼠标移到图表上出现垂直虚线
- [ ] 虚线旁显示北京时间 + 美东时间 + 两个价格
- [ ] 交点处有小圆点标注（绿色/橙色）
- [ ] 页面无 1天/5天/月 按钮
- [ ] Emoji 插件无报错（已注释）
