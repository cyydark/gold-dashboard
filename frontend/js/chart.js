/**
 * Chart.js dual-axis chart: COMEX:GCW00 (right) + AU9999 (left).
 * News markers: dashed vertical lines (annotation v3) + emoji on price line.
 */

// Emoji plugin: registered globally so annotation plugin is not excluded
Chart.register({
  id: "emojiMarkers",
  afterDatasetsDraw(chart) {
    if (!chart._goldNews || !chart._goldXauData || !chart._goldNews.length) return;
    const { ctx, chartArea, scales } = chart;
    if (!chartArea || !scales.x || !scales.y) return;
    const xScale = scales.x;
    const fontSize = 16;
    ctx.save();
    ctx.font = `${fontSize}px serif`;
    ctx.textBaseline = "bottom";

    chart._emojiHits = []; // store hit boxes for click detection
    for (let i = 0; i < chart._goldNews.length; i++) {
      const item = chart._goldNews[i];
      if (item.direction === "neutral") continue;
      const rawTs = item.published_ts ? item.published_ts * 1000 : null;
      if (!rawTs) continue;

      // Emoji always on the dashed line's x, at the bottom of the dashed line
      const x = xScale.getPixelForValue(rawTs);
      const emojiY = chartArea.bottom;

      if (x < chartArea.left || x > chartArea.right) continue;

      const emoji = item.direction === "up" ? "📈" : "📉";
      ctx.fillText(emoji, x - fontSize / 2, emojiY - 2);
      chart._emojiHits.push({ x: x - 15, x2: x + 15, y: emojiY - fontSize, y2: emojiY + 2, url: item.url });
    }
    ctx.restore();
  },
  afterEvent(chart, args) {
    if (args.event.type !== "click") return;
    if (!chart._emojiHits || !chart._emojiHits.length) return;
    const { x, y } = args.event;
    for (const hit of chart._emojiHits) {
      if (x >= hit.x && x <= hit.x2 && y >= hit.y && y <= hit.y2) {
        window.open(hit.url, "_blank", "noopener");
        return;
      }
    }
  },
});

class GoldChart {
  constructor() {
    this.chart = null;
    this.loading = false;
    this.currentDays = 1;
    this.news = [];
    this._xauData = [];
  }

  setNews(news) {
    this.news = news || [];
    if (this.chart) {
      this.chart._goldNews = this.news;
      this._updateAnnotations();
    }
  }

  /** Fire fetch for all 3 windows in parallel (backend caches each for 5 min). */
  warmup() {
    [1, 5, 30].forEach(days => {
      fetch(`/api/history/XAUUSD?days=${days}`).catch(() => {});
      fetch(`/api/history/AU9999?days=${days}`).catch(() => {});
    });
  }

  _updateAnnotations() {
    if (!this.chart) return;
    const annotations = {};
    for (let i = 0; i < this.news.length; i++) {
      const item = this.news[i];
      if (item.direction === "neutral") continue;
      // published_ts is the canonical UTC publication timestamp
      const ts = item.published_ts ? new Date(item.published_ts * 1000) : null;
      if (!ts || isNaN(ts.getTime())) continue;
      const isUp = item.direction === "up";
      annotations[`n_${i}`] = {
        type: "line",
        xMin: ts,
        xMax: ts,
        borderColor: isUp ? "rgba(34,197,94,0.8)" : "rgba(239,68,68,0.8)",
        borderWidth: 2,
        borderDash: [6, 4],
      };
    }
    // "Now" line — updated each time so it tracks real clock time
    annotations["nowLine"] = {
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
    };
    this.chart.options.plugins.annotation = { annotations };
    this.chart.update("none");
  }

  async load(days) {
    if (this.loading) return;
    this.loading = true;
    this.currentDays = days;

    const canvas = document.getElementById("priceChart");
    if (!canvas) { console.error("canvas not found"); return; }

    const loader = document.getElementById("chart-loader");
    if (loader) { loader.style.display = "block"; loader.textContent = "加载中..."; }

    try {
      const [xauRes, auRes] = await Promise.all([
        fetch(`/api/history/XAUUSD?days=${days}`),
        fetch(`/api/history/AU9999?days=${days}`),
      ]);

      const [xauData, auData] = await Promise.all([
        xauRes.json(),
        auRes.json(),
      ]);

      // Timestamps from backend are UTC seconds — no conversion needed,
      // Chart.js renders them in browser's local timezone (Beijing for this user)
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
          pointRadius: xauPts.length > 200 ? 0 : 3,
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
          pointRadius: auPts.length > 200 ? 0 : 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.15,
          yAxisID: "y2",
        });
      }

      const unit = days <= 1 ? "minute" : days <= 5 ? "hour" : "day";

      if (this.chart) this.chart.destroy();

      // Use the actual data range from Google Finance for xMin (aligned session boundaries).
      // xMax is always "now" so the right edge of the chart tracks real clock time.
      const xMin = xauResp ? toBeijingDate(xauResp.xMin) : new Date(Date.now() - days * 86400 * 1000);
      const xMax = new Date();

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
            tooltip: {
              backgroundColor: "#1e2130",
              titleColor: "#8a8fad",
              bodyColor: "#ddd",
              borderColor: "#2a2d3a",
              borderWidth: 1,
              padding: 10,
              callbacks: {
                title(items) {
                  if (!items.length) return "";
                  const d = items[0].parsed.x;
                  const pad = n => String(n).padStart(2, "0");
                  const toBJ = new Date(d);
                  const toUS = new Date(d - 12 * 3600 * 1000); // approximate US ET = BJ - 12h
                  const bjStr = `${toBJ.getFullYear()}年${toBJ.getMonth()+1}月${toBJ.getDate()}日 ${pad(toBJ.getHours())}:${pad(toBJ.getMinutes())}`;
                  const usStr = `${toUS.getMonth()+1}月${toUS.getDate()}日 ${pad(toUS.getHours())}:${pad(toUS.getMinutes())}`;
                  return `${bjStr} 北京 | ${usStr} 美东`;
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

      this.chart._goldNews = this.news;
      this.chart._goldXauData = xauPts;

      this._updateAnnotations();  // always include session markers

    } catch (e) {
      console.error("Chart error:", e);
      if (loader) { loader.textContent = "加载失败: " + e.message; }
    }

    this.loading = false;
    if (loader) loader.style.display = "none";
  }
}

window.GoldChart = GoldChart;
