/**
 * Chart.js dual-axis chart: XAU/USD (Binance, right) + AU9999 (SGE, left).
 * Shows 5-minute K-lines for the last 72 hours.
 * The annotation plugin draws the "当前" now-line.
 */

/**
 * Hover crosshair plugin:
 * - afterEvent: track mouse X, trigger redraw
 * - afterDatasetsDraw: draw dashed vertical line + floating label
 */
const _hoverPlugin = {
  id: "goldHover",

  _mouseX: null,

  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea || !scales.x || !scales.y) return;
    if (this._mouseX === null) return;

    const xPx = this._mouseX;
    if (xPx < chartArea.left || xPx > chartArea.right) return;

    const xScale = scales.x;
    const rawTs = xScale.getValueForPixel(xPx);
    const ms5 = 5 * 60 * 1000; // 5-minute bar width in ms

    // Find exact intersection: bar whose time is within [rawTs - ms5/2, rawTs + ms5/2]
    const findAtX = (data) => {
      if (!data || !data.length) return null;
      for (const pt of data) {
        if (Math.abs(pt.x - rawTs) <= ms5 / 2) return pt;
      }
      return null;
    };

    const xauPt = findAtX(chart.data.datasets[0]?.data || []);
    const auPt  = findAtX(chart.data.datasets[1]?.data || []);

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
      chart.draw(false); // no animation
    } else if (args.event.type === "mouseout" || args.event.type === "mouseleave") {
      this._mouseX = null;
      chart.draw(false);
    }
  },
};

Chart.register(_hoverPlugin);

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
          label: "COMEX: GCW00",
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
              title: { display: true, text: "COMEX: GCW00 (USD/oz)", color: "#22c55e", font: { size: 11 } },
              ticks: { color: "#22c55e", callback: v => v.toFixed(1) },
              grid: { color: "#2a2d3a" },
              border: { color: "#2a2d3a" },
            },
            y2: {
              position: "left",
              title: { display: true, text: "AU9999 (CNY/g)", color: "#f59e0b", font: { size: 11 } },
              ticks: { color: "#f59e0b", callback: v => v.toFixed(1) },
              grid: { drawOnChartArea: false },
              border: { color: "#2a2d3a" },
            },
          },
        },
      });

      // Draw "当前" now-line via annotation plugin
      this._updateNowLine();

    } catch (e) {
      console.error("Chart error:", e);
      if (loader) { loader.textContent = "加载失败: " + e.message; }
    }

    this.loading = false;
    if (loader) loader.style.display = "none";
  }
}

window.GoldChart = GoldChart;
