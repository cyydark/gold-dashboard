/**
 * Chart.js dual-axis chart: COMEX:GCW00 (right) + AU9999 (left).
 * News markers: dashed vertical lines (annotation v3) + emoji on price line.
 */

function _tsFromTimeAgo(timeAgo) {
  if (!timeAgo) return null;
  const now = Date.now();
  const m = timeAgo.match(/^(\d+)\s*(分钟|min)/i);
  if (m) return now - parseInt(m[1]) * 60 * 1000;
  const h = timeAgo.match(/^(\d+)\s*(小时|hour)/i);
  if (h) return now - parseInt(h[1]) * 60 * 60 * 1000;
  const d = timeAgo.match(/^(\d+)\s*(日|天|day)/i);
  if (d) return now - parseInt(d[1]) * 24 * 60 * 60 * 1000;
  return null;
}

// Emoji plugin: registered globally so annotation plugin is not excluded
Chart.register({
  id: "emojiMarkers",
  afterDatasetsDraw(chart) {
    if (!chart._goldNews || !chart._goldXauData || !chart._goldNews.length) return;
    const { ctx, chartArea, scales } = chart;
    if (!chartArea || !scales.x || !scales.y) return;
    const xScale = scales.x;
    const yScale = scales.y;
    const fontSize = 16;
    ctx.save();
    ctx.font = `${fontSize}px serif`;
    ctx.textBaseline = "bottom";
    chart._emojiHits = []; // store hit boxes for click detection
    for (let i = 0; i < chart._goldNews.length; i++) {
      const item = chart._goldNews[i];
      if (item.direction === "neutral") continue;
      const ts = _tsFromTimeAgo(item.time_ago);
      if (!ts) continue;
      const x = xScale.getPixelForValue(ts);
      if (x < chartArea.left || x > chartArea.right) continue;
      if (!chart._goldXauData.length) continue;
      let closest = chart._goldXauData[0], minDiff = Infinity;
      for (const pt of chart._goldXauData) {
        const d = Math.abs(pt.x - ts);
        if (d < minDiff) { minDiff = d; closest = pt; }
      }
      const y = yScale.getPixelForValue(closest.y);
      if (y < chartArea.top || y > chartArea.bottom) continue;
      const emoji = item.direction === "up" ? "📈" : "📉";
      ctx.fillText(emoji, x - fontSize / 2, y - 2);
      // Store hit box: 30px wide click area around emoji
      chart._emojiHits.push({ x: x - 15, x2: x + 15, y: y - fontSize, y2: y + 2, url: item.url });
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

  _updateAnnotations() {
    if (!this.chart) return;
    const annotations = {};
    for (let i = 0; i < this.news.length; i++) {
      const item = this.news[i];
      if (item.direction === "neutral") continue;
      const ts = _tsFromTimeAgo(item.time_ago);
      if (!ts) continue;
      const isUp = item.direction === "up";
      annotations[`n_${i}`] = {
        type: "line",
        xMin: new Date(ts),
        xMax: new Date(ts),
        borderColor: isUp ? "rgba(34,197,94,0.8)" : "rgba(239,68,68,0.8)",
        borderWidth: 2,
        borderDash: [6, 4],
      };
    }
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

      const xauPts = (xauData && Array.isArray(xauData) && xauData.length > 0)
        ? xauData.map(d => ({ x: toBeijingDate(d.time), y: d.close }))
        : [];
      const auPts = (auData && Array.isArray(auData) && auData.length > 0)
        ? auData.map(d => ({ x: toBeijingDate(d.time), y: d.close }))
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
                  const date = new Date(d);
                  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
                },
              },
            },
            annotation: { annotations: {} },
          },
          scales: {
            x: {
              type: "time",
              time: {
                unit: unit,
                tooltipUnit: unit,
                displayFormats: {
                  minute: "HH:mm",
                  hour: "MM-dd HH:mm",
                  day: "MM-dd",
                  week: "MM-dd",
                  month: "yyyy-MM",
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

      if (this.news.length > 0) this._updateAnnotations();

    } catch (e) {
      console.error("Chart error:", e);
      if (loader) { loader.textContent = "加载失败: " + e.message; }
    }

    this.loading = false;
    if (loader) loader.style.display = "none";
  }
}

window.GoldChart = GoldChart;
