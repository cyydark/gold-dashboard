/**
 * Chart.js dual-axis chart: XAU/USD (right) + AU9999 (left).
 * Shows 5-minute K-lines for the last 72 hours.
 * The annotation plugin draws the "当前" now-line.
 */

/**
 * Hover crosshair plugin:
 * - afterEvent: pixel→timestamp + binary search in each dataset, throttle redraw
 * - afterDatasetsDraw: draw dashed vertical line + floating label
 */
const _hoverPlugin = {
  id: "goldHover",

  _mouseX: null,
  _nearest: null,   // { xau, au }
  _lastDraw: 0,

  // Binary search: nearest bar to targetTs in O(log n)
  _findNearest(data, targetTs) {
    if (!data || !data.length) return null;
    let lo = 0, hi = data.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (data[mid].x < targetTs) lo = mid + 1;
      else hi = mid;
    }
    let best = data[lo];
    let bestDiff = Math.abs(best.x - targetTs);
    if (lo > 0) {
      const diff = Math.abs(data[lo - 1].x - targetTs);
      if (diff < bestDiff) { bestDiff = diff; best = data[lo - 1]; }
    }
    if (lo < data.length - 1) {
      const diff = Math.abs(data[lo + 1].x - targetTs);
      if (diff < bestDiff) best = data[lo + 1];
    }
    return best;
  },

  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea || !scales.x || !scales.y) return;
    if (this._mouseX === null) return;

    const xPx = this._mouseX;
    if (xPx < chartArea.left || xPx > chartArea.right) return;

    const xScale = scales.x;
    const rawTs = xScale.getValueForPixel(xPx);

    const nearest = this._nearest;
    const xauPt = nearest?.xau || null;
    const auPt  = nearest?.au  || null;

    // Don't show tooltip if cursor is too far from any real data point (>20px)
    const GAP_THRESHOLD_PX = 20;
    const nearestXau = nearest?.xau;
    const nearestAu  = nearest?.au;
    const xauPx = nearestXau ? scales.x.getPixelForValue(nearestXau.x) : null;
    const auPx  = nearestAu  ? scales.x.getPixelForValue(nearestAu.x)  : null;
    if ((xauPx === null || Math.abs(xPx - xauPx) > GAP_THRESHOLD_PX) &&
        (auPx  === null || Math.abs(xPx - auPx)  > GAP_THRESHOLD_PX)) {
      return;
    }

    const pad = n => String(n).padStart(2, "0");
    const fmtBJ = (ts) => {
      const d = new Date(ts);
      return `${pad(d.getMonth()+1)}月${pad(d.getDate())}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };
    const fmtUS = (ts) => {
      const d = new Date(ts - 12 * 3600 * 1000);
      return `${pad(d.getMonth()+1)}月${pad(d.getDate())}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    const lines = [];
    if (rawTs) {
      lines.push({ t: `北京 ${fmtBJ(rawTs)}`, c: "#94a3b8" });
      lines.push({ t: `美东 ${fmtUS(rawTs)}`, c: "#94a3b8" });
    }
    if (xauPt) lines.push({ t: `XAU/USD ${xauPt.y.toFixed(2)}`, c: "#22c55e" });
    if (auPt)  lines.push({ t: `AU9999 ${auPt.y.toFixed(2)}`,  c: "#f59e0b" });

    if (!lines.length) return;

    // Y positions for intersection dots
    const yPxXau = (xauPt && scales.y)
      ? scales.y.getPixelForValue(xauPt.y)
      : null;
    const yPxAu = (auPt && scales.y2)
      ? scales.y2.getPixelForValue(auPt.y)
      : null;

    const validYPx = [yPxXau, yPxAu].filter(y => y !== null && y >= chartArea.top && y <= chartArea.bottom);
    const boxCenterY = validYPx.length > 0
      ? validYPx.reduce((s, y) => s + y, 0) / validYPx.length
      : (chartArea.top + chartArea.bottom) / 2;

    ctx.save();

    // Dashed vertical line
    ctx.beginPath();
    ctx.strokeStyle = "rgba(148,163,184,0.5)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.moveTo(xPx, chartArea.top);
    ctx.lineTo(xPx, chartArea.bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    // Floating label box — positioned near intersection points
    const lineH = 18, pad2 = 8;
    ctx.font = "12px Inter, sans-serif";
    const maxW = Math.max(...lines.map(l => ctx.measureText(l.t).width));
    const boxW = maxW + pad2 * 2;
    const boxH = lines.length * lineH + pad2;

    // Horizontal: prefer right of X line, flip left if overflow
    let boxX = xPx + 8;
    if (boxX + boxW > chartArea.right - 4) boxX = xPx - boxW - 8;

    // Vertical: center box on intersection points, clamp to chart
    const boxHalfH = boxH / 2;
    let boxY = boxCenterY - boxHalfH;
    if (boxY < chartArea.top) boxY = chartArea.top;
    if (boxY + boxH > chartArea.bottom) boxY = chartArea.bottom - boxH;

    ctx.fillStyle = "rgba(30,33,48,0.95)";
    ctx.beginPath();
    ctx.roundRect(boxX, boxY, boxW, boxH, 4);
    ctx.fill();

    ctx.textBaseline = "top";
    lines.forEach((l, i) => {
      ctx.fillStyle = l.c;
      ctx.fillText(l.t, boxX + pad2, boxY + pad2 + i * lineH);
    });

    // Intersection dots
    if (yPxXau !== null) {
      ctx.fillStyle = "#22c55e";
      ctx.beginPath(); ctx.arc(xPx, yPxXau, 4, 0, Math.PI * 2); ctx.fill();
    }
    if (yPxAu !== null) {
      ctx.fillStyle = "#f59e0b";
      ctx.beginPath(); ctx.arc(xPx, yPxAu, 4, 0, Math.PI * 2); ctx.fill();
    }

    ctx.restore();
  },

  afterEvent(chart, args) {
    if (args.event.type === "mousemove") {
      this._mouseX = args.inChartArea ? args.event.x : null;
      if (args.inChartArea) {
        const xScale = chart.scales.x;
        const rawTs = xScale.getValueForPixel(args.event.x);
        const xauData = chart.data.datasets[0]?.data || [];
        const auData  = chart.data.datasets[1]?.data || [];
        this._nearest = {
          xau: this._findNearest(xauData, rawTs),
          au:  this._findNearest(auData,  rawTs),
        };
      }
      const now = Date.now();
      if (now - this._lastDraw >= 16) {
        chart.draw(false);
        this._lastDraw = now;
      }
    } else if (args.event.type === "mouseout" || args.event.type === "mouseleave") {
      this._mouseX = null;
      this._nearest = null;
      chart.draw(false);
      this._lastDraw = 0;
    }
  },
};

Chart.register(_hoverPlugin);

// Zoom plugin — wheel zoom via chartjs-plugin-zoom, drag-pan done natively in afterInit
const _zoomPlugin = {
  id: "goldZoom",

  afterInit(chart) {
    chart._resetZoom = () => chart.resetZoom();

    const canvas = chart.canvas;
    const xMin = canvas._goldXMin;
    const xMax = canvas._goldXMax;

    let dragging = false;
    let startX = 0;
    let origMin = null;
    let origMax = null;

    const onDown = (e) => {
      dragging = true;
      startX = e.clientX;
      origMin = chart.scales.x.min;
      origMax = chart.scales.x.max;
      e.preventDefault();
    };
    const onMove = (e) => {
      if (!dragging || !chart.scales.x) return;
      const chartArea = chart.chartArea;
      if (!chartArea) return;
      const dx = e.clientX - startX;
      if (dx === 0) return;
      const totalPx = chartArea.right - chartArea.left;
      const range = origMax - origMin;
      const shift = (-dx / totalPx) * range;
      const newMin = origMin + shift;
      const newMax = origMax + shift;
      const clampedMin = Math.max(newMin, xMin);
      const clampedMax = Math.min(newMax, xMax);
      chart.zoomScale("x", { min: clampedMin, max: clampedMax });
      if (chart._updateNowLine) chart._updateNowLine();
    };
    const onUp = () => { dragging = false; };

    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  },
};

Chart.register(_zoomPlugin);

class GoldChart {
  constructor() {
    this.chart = null;
    this.loading = false;
    this.currentDays = 1;
    this.news = [];
  }

  setNews(news) {
    this.news = news || [];
    if (this.chart) {
      this.chart.update("none");
    }
  }

  /** Fire fetch for both symbols in parallel (backend caches each for 5 min). */
  warmup() {
    fetch(`/api/history/XAUUSD`).catch(() => {});
    fetch(`/api/history/AU9999`).catch(() => {});
  }

  _updateNowLine() {
    if (!this.chart) return;
    this.chart.options.plugins.annotation = {
      annotations: {
        nowLine: {
          type: "line",
          xMin: new Date(),
          xMax: new Date(),
          borderColor: "rgba(148,163,184,0.7)",
          borderWidth: 1,
          borderDash: [4, 4],
          label: {
            display: true,
            content: "当前",
            position: "center",
            yAdjust: -50,
            color: "#94a3b8",
            font: { size: 10 },
            backgroundColor: "transparent",
          },
        },
      },
    };
    this.chart.update("none");
  }

  async load() {
    if (this.loading) return;
    this.loading = true;

    const canvas = document.getElementById("priceChart");
    if (!canvas) { console.error("canvas not found"); return; }

    const loader = document.getElementById("chart-loader");
    if (loader) { loader.style.display = "block"; loader.textContent = "加载中..."; }

    try {
      const [xauRes, auRes] = await Promise.all([
        fetch(`/api/history/XAUUSD`),
        fetch(`/api/history/AU9999`),
      ]);

      const [xauData, auData] = await Promise.all([
        xauRes.json(),
        auRes.json(),
      ]);

      const toBeijingDate = (unixSec) => new Date(unixSec * 1000);

      const xauResp = (xauData && xauData.bars && xauData.bars.length > 0) ? xauData : null;
      const auResp  = (auData  && auData.bars  && auData.bars.length  > 0) ? auData  : null;

      const xauPts = xauResp
        ? xauResp.bars.map(d => ({ x: toBeijingDate(d.time), y: d.close }))
        : [];
      const auPts = auResp
        ? auResp.bars.map(d => ({ x: toBeijingDate(d.time), y: d.close }))
        : [];

      this._xauData = xauPts;
      this._auData = auPts;

      if (xauPts.length === 0 && auPts.length === 0) {
        if (loader) { loader.textContent = "暂无数据"; }
        this.loading = false;
        return;
      }

      const datasets = [];

      if (xauPts.length > 0) {
        datasets.push({
          label: "COMEX GC00Y",
          data: xauPts,
          borderColor: "#22c55e",
          backgroundColor: "rgba(34,197,94,0.08)",
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.15,
          yAxisID: "y",
        });
      }

      if (auPts.length > 0) {
        datasets.push({
          label: "AU9999",
          data: auPts,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245,158,11,0.08)",
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.15,
          yAxisID: "y2",
        });
      }

      const unit = "minute";

      if (this.chart) this.chart.destroy();

      const now = new Date();
      const xMax = now;
      const xMin = new Date(now.getTime() - 72 * 60 * 60 * 1000);

      // Store bounds on canvas before chart creation (read in beforeInit plugin)
      canvas._goldXMin = xMin;
      canvas._goldXMax = now;

      // Dynamic Y range: ensure minimum ±1 padding so chart is always readable
      const _yRange = (pts, minPad = 1) => {
        if (!pts || pts.length === 0) return null;
        const vals = pts.map(p => p.y);
        const dataMin = Math.min(...vals);
        const dataMax = Math.max(...vals);
        const range = dataMax - dataMin;
        // Use at least minPad padding, or 5% of range if that's larger
        const pad = Math.max(range * 0.05, minPad);
        return { min: dataMin - pad, max: dataMax + pad };
      };
      const yau  = _yRange(xauPts, 10);   // ±10 for XAUUSD (~4700)
      const yau2 = _yRange(auPts, 1);     // ±1 for AU9999 (~1034)

      this.chart = new Chart(canvas, {
        type: "line",
        data: { datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 300 },
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false },
            zoom: {
              zoom: {
                wheel: {
                  enabled: true,
                  speed: 0.1,
                },
                pinch: { enabled: false },
                drag: { enabled: false },
                mode: "x",
                onZoomComplete: ({ chart }) => {
                  if (chart._updateNowLine) chart._updateNowLine();
                },
              },
              limits: {
                x: {
                  min: xMin,
                  max: now,
                },
              },
            },
            annotation: {
              annotations: {
                nowLine: {
                  type: "line",
                  xMin: new Date(),
                  xMax: new Date(),
                  borderColor: "rgba(148,163,184,0.7)",
                  borderWidth: 1,
                  borderDash: [4, 4],
                  label: {
                    display: true,
                    content: "当前",
                    position: "start",
                    color: "#94a3b8",
                    font: { size: 10 },
                    backgroundColor: "transparent",
                  },
                },
              },
            },
          },
          scales: {
            x: {
              type: "time",
              min: xMin,
              max: xMax,
              time: {
                unit: unit,
                tooltipUnit: unit,
                displayFormats: {
                  minute: "HH:mm",
                  hour: "M月d日 HH:mm",
                  day: "M月d日",
                  week: "M月d日",
                  month: "yyyy年M月",
                },
              },
              ticks: { color: "#7a7f96", maxTicksLimit: 10, autoSkipPadding: 20, maxRotation: 0 },
              grid: { color: "#2a2d3a" },
              border: { color: "#2a2d3a" },
            },
            y: {
              position: "right",
              title: { display: true, text: "COMEX GC00Y (USD/oz)", color: "#22c55e", font: { size: 11 } },
              ticks: { color: "#22c55e", callback: v => v.toFixed(2) },
              grid: { color: "#2a2d3a" },
              border: { color: "#2a2d3a" },
              suggestedMin: yau?.min,
              suggestedMax: yau?.max,
            },
            y2: {
              position: "left",
              title: { display: true, text: "AU9999 (CNY/g)", color: "#f59e0b", font: { size: 11 } },
              ticks: { color: "#f59e0b", callback: v => v.toFixed(2) },
              grid: { drawOnChartArea: false },
              border: { color: "#2a2d3a" },
              suggestedMin: yau2?.min,
              suggestedMax: yau2?.max,
            },
          },
        },
      });

      // Draw "当前" now-line via annotation plugin
      this._updateNowLine();

      // Double-click to reset zoom
      canvas.addEventListener("dblclick", () => {
        if (this.chart?._resetZoom) this.chart._resetZoom();
      });

    } catch (e) {
      console.error("Chart error:", e);
      if (loader) { loader.textContent = "加载失败: " + e.message; }
    }

    this.loading = false;
    if (loader) loader.style.display = "none";
  }

  /**
   * Update chart with real-time SSE price.
   * Uses wall-clock minute-aligned timestamp so the point always appears at "now".
   * - Same minute as last point → update its price
   * - New minute → append new point
   * @param {string} symbol - "XAUUSD" or "AU9999"
   * @param {number} nowTsSec - current wall-clock Unix timestamp in seconds
   * @param {number} price - current price
   */
  appendPrice(symbol, nowTsSec, price) {
    if (!this.chart) return;
    const axisID = symbol === "XAUUSD" ? "y" : "y2";
    const dataset = this.chart.data.datasets.find(d => d.yAxisID === axisID);
    if (!dataset || !dataset.data.length) return;

    const tsMs = Math.floor(nowTsSec / 60) * 60 * 1000;
    const last = dataset.data[dataset.data.length - 1];
    const lastTs = last ? Math.floor(last.x.getTime() / 60000) * 60000 : null;

    if (last && lastTs === tsMs) {
      last.y = price;
    } else {
      dataset.data.push({ x: new Date(tsMs), y: price });
    }
    this.chart.update("none");
  }
}

window.GoldChart = GoldChart;
