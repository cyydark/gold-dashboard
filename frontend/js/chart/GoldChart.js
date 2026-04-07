/**
 * GoldChart — dual-axis gold price chart.
 *
 * Module structure:
 *   GoldChart.js     — main chart class, emoji/dashed-line plugin (inline)
 *   plugins/hover.js — custom hover crosshair + tooltip
 *   plugins/zoom.js  — scroll-to-zoom, drag-to-pan
 *   utils/time.js    — fmtBJ, fmtUS, findNearest
 */
import { hoverPlugin } from "./plugins/hover.js";
import { zoomPlugin } from "./plugins/zoom.js";
import { fmtBJ, fmtUS } from "./utils/time.js";

Chart.register(hoverPlugin);
Chart.register(zoomPlugin);

/**
 * Insert null y-values at the MIDPOINT of gaps larger than thresholdMs.
 * Chart.js breaks the line at null points, producing a clean visual gap
 * instead of a horizontal connector.
 */
const insertGaps = (pts, thresholdMs = 30 * 60 * 1000) => {
  const result = [];
  for (let i = 0; i < pts.length; i++) {
    if (i > 0) {
      const gap = pts[i].x - pts[i - 1].x;
      if (gap > thresholdMs) {
        result.push({
          x: new Date((pts[i - 1].x.getTime() + pts[i].x.getTime()) / 2),
          y: null,
        });
      }
    }
    result.push(pts[i]);
  }
  return result;
};

/** Y-axis range from points array, null-safe. */
const _yRange = (pts, minPad = 1) => {
  const vals = pts.map(p => p.y).filter(v => v !== null && v !== undefined);
  if (vals.length === 0) return null;
  const dataMin = Math.min(...vals);
  const dataMax = Math.max(...vals);
  const range = dataMax - dataMin;
  const pad = Math.max(range * 0.05, minPad);
  return [dataMin - pad, dataMax + pad];
};

const XAU_SYMBOL_MAP = {
  comex:   "XAUUSD",
  binance: "XAUUSD_BINANCE",
  sina:    "XAUUSD_SINA",
};

const XAU_LEGEND_MAP = {
  comex:   "COMEX GC00Y",
  binance: "XAUTUSDT (Binance)",
  sina:    "Sina 伦敦金 (hf_XAU)",
};

/** Distinct line colors per XAU source — warm gold/amber/violet palette */
const XAU_COLORS = {
  comex:   { normal: "#d4af37", flash: "#f0d060", bg: "rgba(212,175,55,0.10)"  },
  binance: { normal: "#fb923c", flash: "#fdba74", bg: "rgba(251,146,60,0.10)"  },
  sina:    { normal: "#c084fc", flash: "#d8b4fe", bg: "rgba(192,132,252,0.10)" },
};

/** Distinct line colors per AU source — cool cyan/blue/teal palette */
const AU_COLORS = {
  au9999:  { normal: "#22d3ee", flash: "#67e8f9", bg: "rgba(34,211,238,0.10)" },
  sina_au0:{ normal: "#38bdf8", flash: "#7dd3fc", bg: "rgba(56,189,248,0.10)" },
};

/** Random vivid color for source-switch flash */
const _randomFlashColor = () => {
  const palette = [
    "#34d399", "#22d3ee", "#a78bfa", "#f59e0b",
    "#fb7185", "#f97316", "#e879f9", "#4ade80",
    "#facc15", "#38bdf8",
  ];
  return palette[Math.floor(Math.random() * palette.length)];
};

/** Convert hex color to rgba with given alpha */
const _hexToRgba = (hex, alpha) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
};

class GoldChart {
  constructor() {
    this.chart = null;
    this.loading = false;
    this.news = [];
    this.xauSource = "comex";
    this.auSource = "au9999";
  }

  setNews(news) {
    this.news = news || [];
    if (this.chart) {
      this.chart._goldNews = this.news;
      this.chart.update("none");
    }
  }

  /**
   * Switch XAU source: clear chart → show loader → fetch → render with color flash.
   */
  async switchXauSource(source) {
    const wasLoading = this._loadingChart;
    this._loadingChart = true;
    this._xauSwitchPending = true;
    this.xauSource = source;

    // 1. Clear chart immediately
    if (this.chart && this.chart.data.datasets[0]) {
      this.chart.data.datasets[0].data = [];
      this.chart.update("none");
    }

    // 2. Update legend immediately
    const legendXau = document.getElementById("legend-xau");
    if (legendXau) legendXau.textContent = XAU_LEGEND_MAP[source] || source;

    // 3. Flash bright random color on the line
    const flashColor = _randomFlashColor();
    if (this.chart && this.chart.data.datasets[0]) {
      const ds = this.chart.data.datasets[0];
      ds.borderColor = flashColor;
      ds.backgroundColor = _hexToRgba(flashColor, 0.10);
      ds.borderWidth = 2.5;
      this.chart.options.scales.y.title.color = flashColor;
      this.chart.options.scales.y.ticks.color = flashColor;
      this.chart.update("none");
    }

    // 4. Show loader
    const loader = document.getElementById("chart-loader");
    if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "加载中..."; }

    // 5. Fetch new data (no polling interference since _xauSwitchPending = true)
    try {
      const res = await fetch(`/api/chart/xau?source=${source}`);
      const d = await res.json();
      if (!d.bars || d.bars.length === 0) {
        if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "暂无数据"; }
        this._xauSwitchPending = false;
        this._loadingChart = false;
        return;
      }
      const pts = insertGaps(d.bars.map(b => ({ x: new Date(b.time * 1000), y: b.close })));

      // 6. Only render after confirmed data
      const c = XAU_COLORS[source] || XAU_COLORS.comex;
      if (this.chart && this.chart.data.datasets[0]) {
        this.chart.data.datasets[0].data = pts;
        this.chart.data.datasets[0].borderColor = c.normal;
        this.chart.data.datasets[0].backgroundColor = c.bg;
        this.chart.data.datasets[0].borderWidth = 1.5;
        this.chart.options.scales.y.title.text = XAU_LEGEND_MAP[source] + " (USD/oz)";
        this.chart.options.scales.y.title.color = c.normal;
        this.chart.options.scales.y.ticks.color = c.normal;
        this._updateScales(0);
        this.chart.update("none");
        this._updateNowLine();
      }
      if (loader) loader.style.display = "none";
    } catch (e) {
      if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "加载失败"; }
    }

    this._xauSwitchPending = false;
    this._loadingChart = false;
  }

  /**
   * Switch AU source: clear chart → show loader → fetch → render with color flash.
   */
  async switchAuSource(source) {
    this._loadingChart = true;
    this._auSwitchPending = true;
    this.auSource = source;

    // 1. Clear chart
    if (this.chart && this.chart.data.datasets[1]) {
      this.chart.data.datasets[1].data = [];
      this.chart.update("none");
    }

    // 2. Update legend
    const legendAu = document.getElementById("legend-au");
    if (legendAu) legendAu.textContent = source === "sina_au0" ? "沪金 AU0 (Sina)" : "AU9999";

    // 3. Flash bright random color
    const flashColor = _randomFlashColor();
    if (this.chart && this.chart.data.datasets[1]) {
      const ds = this.chart.data.datasets[1];
      ds.borderColor = flashColor;
      ds.backgroundColor = _hexToRgba(flashColor, 0.10);
      ds.borderWidth = 2.5;
      this.chart.options.scales.y2.title.color = flashColor;
      this.chart.options.scales.y2.ticks.color = flashColor;
      this.chart.update("none");
    }

    // 4. Show loader
    const loader = document.getElementById("chart-loader");
    if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "加载中..."; }

    // 5. Fetch new data
    try {
      const res = await fetch(`/api/chart/au?source=${source}`);
      const d = await res.json();
      if (!d.bars || d.bars.length === 0) {
        if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "暂无数据"; }
        this._auSwitchPending = false;
        this._loadingChart = false;
        return;
      }
      const pts = insertGaps(d.bars.map(b => ({ x: new Date(b.time * 1000), y: b.close })));

      // 6. Only render after confirmed data
      const c = AU_COLORS[source] || AU_COLORS.au9999;
      if (this.chart && this.chart.data.datasets[1]) {
        this.chart.data.datasets[1].data = pts;
        this.chart.data.datasets[1].borderColor = c.normal;
        this.chart.data.datasets[1].backgroundColor = c.bg;
        this.chart.data.datasets[1].borderWidth = 1.5;
        this.chart.options.scales.y2.title.color = c.normal;
        this.chart.options.scales.y2.ticks.color = c.normal;
        this._updateScales(1);
        this.chart.update("none");
      }
      if (loader) loader.style.display = "none";
    } catch (e) {
      if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "加载失败"; }
    }

    this._auSwitchPending = false;
    this._loadingChart = false;
  }

  warmup() {
    fetch(`/api/chart/xau?source=${this.xauSource}`).then(r => r.json()).then(d => {
      if (d && d.bars && d.bars.length > 0) {
        this._warmupXau = d;
        this.loadXauFromCache(d);
      }
    }).catch(() => {});
    fetch(`/api/chart/au?source=${this.auSource}`).then(r => r.json()).then(d => {
      if (d && d.bars && d.bars.length > 0) {
        this._warmupAu = d;
        this.loadAuFromCache(d);
      }
    }).catch(() => {});
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

  /** Recompute Y limits for a dataset after live data arrives. */
  _updateScales(datasetIndex) {
    if (!this.chart) return;
    const pts = this.chart.data.datasets[datasetIndex]?.data || [];
    const range = _yRange(pts);
    if (!range) return;
    const axisID = datasetIndex === 0 ? "y" : "y2";
    this.chart.options.scales[axisID].min = range[0];
    this.chart.options.scales[axisID].max = range[1];
  }

  /** Called by PollingManager with fresh chart data */
  loadXauFromCache(data) {
    if (!data || !data.bars || data.bars.length === 0) return;
    const pts = insertGaps(data.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })));
    if (this.chart && this.chart.data.datasets[0]) {
      const c = XAU_COLORS[this.xauSource] || XAU_COLORS.comex;
      this.chart.data.datasets[0].data = pts;
      this.chart.data.datasets[0].borderColor = c.normal;
      this.chart.data.datasets[0].backgroundColor = c.bg;
      this.chart.data.datasets[0].label = XAU_LEGEND_MAP[this.xauSource] || "XAU";
      this.chart.options.scales.y.title.text = XAU_LEGEND_MAP[this.xauSource] + " (USD/oz)";
      this.chart.options.scales.y.title.color = c.normal;
      this.chart.options.scales.y.ticks.color = c.normal;
      this._updateScales(0);
      this.chart.update("none");
      this._updateNowLine();
    } else {
      this._pendingXau = pts;
    }
  }

  loadAuFromCache(data) {
    if (!data || !data.bars || data.bars.length === 0) return;
    const pts = insertGaps(data.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })));
    if (this.chart && this.chart.data.datasets[1]) {
      const c = AU_COLORS[this.auSource] || AU_COLORS.au9999;
      this.chart.data.datasets[1].data = pts;
      this.chart.data.datasets[1].borderColor = c.normal;
      this.chart.data.datasets[1].backgroundColor = c.bg;
      this._updateScales(1);
      this.chart.update("none");
    } else {
      this._pendingAu = pts;
    }
  }

  /**
   * Append a real-time bar to the chart.
   * Inserts a null at the gap midpoint if gap > 30 min, then recomputes Y scale.
   */
  appendPrice(datasetIndex, bar) {
    if (!this.chart) return;
    const dataset = this.chart.data.datasets[datasetIndex];
    if (!dataset) return;
    const pts = dataset.data;
    const tsMs = bar.x.getTime();
    const lastTs = pts.length > 0 ? pts[pts.length - 1].x.getTime() : null;

    if (lastTs !== null && tsMs - lastTs > 30 * 60 * 1000) {
      dataset.data.push({
        x: new Date((lastTs + tsMs) / 2),
        y: null,
      });
    }
    dataset.data.push(bar);
    this._updateScales(datasetIndex);
    this.chart.update("none");
  }

  async load() {
    if (this.loading) return;
    this.loading = true;

    const canvas = document.getElementById("priceChart");
    if (!canvas) { console.error("canvas not found"); return; }

    const loader = document.getElementById("chart-loader");
    if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "加载中..."; }

    try {
      // Clear any warmup-pending data — load() has fresh fetch data, warmup is stale
      this._pendingXau = null;
      this._pendingAu  = null;
      // Prefer warmup cache to avoid duplicate fetch
      const warmupXau = this._warmupXau;
      const warmupAu  = this._warmupAu;
      this._warmupXau = null;
      this._warmupAu  = null;

      let xauResp = warmupXau;
      let auResp  = warmupAu;

      // Fetch each independently — one failure should not block the other
      if (!xauResp || !xauResp.bars || xauResp.bars.length === 0) {
        try {
          const xauRes = await fetch(`/api/chart/xau?source=${this.xauSource}`);
          const d = await xauRes.json();
          if (d.bars && d.bars.length > 0) xauResp = d;
        } catch (e) {
          console.warn("XAU chart fetch failed:", e.message);
        }
      }
      if (!auResp || !auResp.bars || auResp.bars.length === 0) {
        try {
          const auRes = await fetch(`/api/chart/au?source=${this.auSource}`);
          const d = await auRes.json();
          if (d.bars && d.bars.length > 0) auResp = d;
        } catch (e) {
          console.warn("AU chart fetch failed:", e.message);
        }
      }

      const xauPts = xauResp
        ? insertGaps(xauResp.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })))
        : [];
      const auPts = auResp
        ? insertGaps(auResp.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })))
        : [];

      if (xauPts.length === 0 && auPts.length === 0) {
        if (loader) { loader.querySelector('span').textContent = "暂无数据"; }
        this.loading = false;
        if (loader) loader.style.display = "none";
        return;
      }

      const datasets = [];
      if (xauPts.length > 0) {
        const c = XAU_COLORS[this.xauSource] || XAU_COLORS.comex;
        datasets.push({
          label: XAU_LEGEND_MAP[this.xauSource] || "COMEX GC00Y",
          data: xauPts,
          borderColor: c.normal,
          backgroundColor: c.bg,
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 0,
          fill: true,
          tension: 0.15,
          yAxisID: "y",
        });
      }
      if (auPts.length > 0) {
        const c = AU_COLORS[this.auSource] || AU_COLORS.au9999;
        datasets.push({
          label: "AU9999",
          data: auPts,
          borderColor: c.normal,
          backgroundColor: c.bg,
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 0,
          fill: true,
          tension: 0.15,
          yAxisID: "y2",
        });
      }

      const now = new Date();
      const xMax = now;
      const xMin = new Date(now.getTime() - 72 * 60 * 60 * 1000);
      const yau  = _yRange(xauPts, 10);
      const yau2 = _yRange(auPts, 1);

      // Update pending data only after chart is confirmed to exist
      if (this.chart) {
        if (this._pendingXau && this.chart.data.datasets[0]) {
          this.chart.data.datasets[0].data = this._pendingXau;
          this._updateScales(0);
          this._pendingXau = null;
        }
        if (this._pendingAu && this.chart.data.datasets[1]) {
          this.chart.data.datasets[1].data = this._pendingAu;
          this._updateScales(1);
          this._pendingAu = null;
        }
      }

      if (this.chart) {
        this.chart.data.datasets = datasets;
        this.chart.options.scales.x.min = xMin;
        this.chart.options.scales.x.max = xMax;
        this.chart.options.scales.y.min = yau ? yau[0] : undefined;
        this.chart.options.scales.y.max = yau ? yau[1] : undefined;
        this.chart.options.scales.y.title.text = XAU_LEGEND_MAP[this.xauSource] + " (USD/oz)";
        this.chart.options.scales.y2.min = yau2 ? yau2[0] : undefined;
        this.chart.options.scales.y2.max = yau2 ? yau2[1] : undefined;
        this.chart.update("none");
        this.chart._goldNews    = this.news;
        this.chart._goldXauData = xauPts;
        this._updateNowLine();
        this.loading = false;
        if (loader) loader.style.display = "none";
        return;
      }

      canvas._goldXMin = xMin;
      canvas._goldXMax = xMax;

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
                wheel: { enabled: true, speed: 0.1 },
                pinch: { enabled: false },
                drag: { enabled: false },
                mode: "x",
                onZoomComplete: ({ chart }) => {
                  if (chart._updateNowLine) chart._updateNowLine();
                },
              },
              limits: { x: { min: xMin, max: xMax } },
            },
          },
          scales: {
            x: {
              type: "time",
              min: xMin,
              max: xMax,
              time: {
                unit: "minute",
                tooltipUnit: "minute",
                displayFormats: {
                  minute: "HH:mm",
                  hour: "M月d日 HH:mm",
                  day: "M月d日",
                },
              },
              ticks: { color: "#7a7f96", maxTicksLimit: 10, autoSkipPadding: 20, maxRotation: 0 },
              grid: { color: "#2a2d3a" },
              border: { color: "#2a2d3a" },
            },
            y: {
              position: "right",
              title: {
                display: true,
                text: XAU_LEGEND_MAP[this.xauSource] + " (USD/oz)",
                color: "#d4af37",
                font: { size: 11 },
              },
              ticks: { color: "#d4af37", callback: v => v.toFixed(2) },
              grid: { color: "#2a2d3a" },
              border: { color: "#2a2d3a" },
              min: yau ? yau[0] : undefined,
              max: yau ? yau[1] : undefined,
            },
            y2: {
              position: "left",
              title: { display: true, text: "AU9999 (CNY/g)", color: "#22d3ee", font: { size: 11 } },
              ticks: { color: "#22d3ee", callback: v => v.toFixed(2) },
              grid: { drawOnChartArea: false },
              border: { color: "#2a2d3a" },
              min: yau2 ? yau2[0] : undefined,
              max: yau2 ? yau2[1] : undefined,
            },
          },
        },
      });

      this.chart._goldNews    = this.news;
      this.chart._goldXauData = xauPts;

      this.chart.update("none");

      canvas.addEventListener("dblclick", () => {
        if (this.chart?._resetZoom) this.chart._resetZoom();
      });

    } catch (e) {
      console.error("Chart error:", e);
      if (loader) { loader.querySelector('span').textContent = "加载失败"; }
    }

    this.loading = false;
    if (loader) loader.style.display = "none";
  }
}

window.GoldChart = GoldChart;
export { GoldChart };
