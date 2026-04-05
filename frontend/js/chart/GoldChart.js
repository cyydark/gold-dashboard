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
        // null at MIDPOINT of gap — avoids timestamp collision
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

/**
  constructor() {
    this.chart = null;
    this.loading = false;
    this.currentDays = 1;
    this.news = [];
  }

  setNews(news) {
    this.news = news || [];
    if (this.chart) {
      this.chart._goldNews = this.news;
      this.chart.update("none");
    }
  }

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

      const xauResp = (xauData && xauData.bars && xauData.bars.length > 0) ? xauData : null;
      const auResp  = (auData  && auData.bars  && auData.bars.length  > 0) ? auData  : null;

      // Map bars and insert gap nulls at midpoints
      const xauPts = xauResp
        ? insertGaps(xauResp.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })))
        : [];
      const auPts = auResp
        ? insertGaps(auResp.bars.map(d => ({ x: new Date(d.time * 1000), y: d.close })))
        : [];

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
          pointHoverRadius: 0,
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
          pointHoverRadius: 0,
          fill: true,
          tension: 0.15,
          yAxisID: "y2",
        });
      }

      const now = new Date();
      const xMax = now;
      const xMin = new Date(now.getTime() - 72 * 60 * 60 * 1000);
      canvas._goldXMin = xMin;
      canvas._goldXMax = xMax;

      const yau  = _yRange(xauPts, 10);
      const yau2 = _yRange(auPts, 1);

      if (this.chart) this.chart.destroy();

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
              title: { display: true, text: "COMEX GC00Y (USD/oz)", color: "#22c55e", font: { size: 11 } },
              ticks: { color: "#22c55e", callback: v => v.toFixed(2) },
              grid: { color: "#2a2d3a" },
              border: { color: "#2a2d3a" },
              min: yau ? yau[0] : undefined,
              max: yau ? yau[1] : undefined,
            },
            y2: {
              position: "left",
              title: { display: true, text: "AU9999 (CNY/g)", color: "#f59e0b", font: { size: 11 } },
              ticks: { color: "#f59e0b", callback: v => v.toFixed(2) },
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

      this._updateNowLine();

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
}

window.GoldChart = GoldChart;
export { GoldChart };
