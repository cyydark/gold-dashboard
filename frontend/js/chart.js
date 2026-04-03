/**
 * Chart.js dual-axis chart: COMEX:GCW00 (right) + AU9999 (left).
 * News markers: emoji + dashed vertical lines — rendered together in afterDatasetsDraw.
 * No annotation plugin dependency; all news visuals drawn directly on canvas.
 */

// Emoji + dashed-line plugin: both rendered together so they are always in sync
Chart.register({
  id: "emojiMarkers",
  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea || !scales.x) return;
    const news = chart._goldNews;
    const xauData = chart._goldXauData;
    if (!news || !news.length) return;

    const xScale = scales.x;
    const fontSize = 16;
    ctx.save();
    ctx.font = `${fontSize}px serif`;
    ctx.textBaseline = "bottom";

    chart._emojiHits = []; // hit boxes for click detection

    for (let i = 0; i < news.length; i++) {
      const item = news[i];
      const rawTs = item.published_ts ? item.published_ts * 1000 : null;
      if (!rawTs) continue;

      const x = xScale.getPixelForValue(rawTs);
      if (x < chartArea.left || x > chartArea.right) continue;

      // ── Dashed vertical line + emoji (only for up/down items) ─────────────
      if (item.direction !== "neutral") {
        const isUp = item.direction === "up";
        const lineColor = isUp ? "rgba(34,197,94,0.8)" : "rgba(239,68,68,0.8)";

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x, chartArea.top);
        ctx.lineTo(x, chartArea.bottom);
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.restore();

        let emojiY = chartArea.bottom;
        if (xauData && xauData.length > 0) {
          const firstTs = xauData[0].x;
          const lastTs  = xauData[xauData.length - 1].x;
          if (rawTs >= firstTs && rawTs <= lastTs) {
            let closest = xauData[0], minDiff = Infinity;
            for (const pt of xauData) {
              const d = Math.abs(pt.x - rawTs);
              if (d < minDiff) { minDiff = d; closest = pt; }
            }
            const rawY = scales.y.getPixelForValue(closest.y);
            const clamped = Math.max(chartArea.top, Math.min(chartArea.bottom, rawY));
            if (clamped === rawY) emojiY = rawY;
          }
        }
        const emoji = item.direction === "up" ? "📈" : "📉";
        ctx.fillText(emoji, x - fontSize / 2, emojiY - 2);
        chart._emojiHits.push({ x: x - 15, x2: x + 15, y: emojiY - fontSize, y2: emojiY + 2, url: item.url });
      }
    }

    // ── "Now" dashed line ─────────────────────────────────────────────────
    const nowX = xScale.getPixelForValue(Date.now());
    if (nowX >= chartArea.left && nowX <= chartArea.right) {
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(nowX, chartArea.top);
      ctx.lineTo(nowX, chartArea.bottom);
      ctx.strokeStyle = "rgba(148,163,184,0.7)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.restore();
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
      // afterDatasetsDraw runs every draw — just trigger a silent redraw
      this.chart.update("none");
    }
  }

  /** Fire fetch for all 3 windows in parallel (backend caches each for 5 min). */
  warmup() {
    [1, 5, 30].forEach(days => {
      fetch(`/api/history/XAUUSD?days=${days}`).catch(() => {});
      fetch(`/api/history/AU9999?days=${days}`).catch(() => {});
    });
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
          pointRadius: 0,
          pointHoverRadius: 4,
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
          pointHoverRadius: 4,
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

      // Note: do NOT call _updateAnnotations() here — chart._goldNews was just set
      // from this.news (which may be stale/empty if news hasn't loaded for this range yet).
      // Annotations are updated by setNews() once fresh news arrives.

    } catch (e) {
      console.error("Chart error:", e);
      if (loader) { loader.textContent = "加载失败: " + e.message; }
    }

    this.loading = false;
    if (loader) loader.style.display = "none";
  }
}

window.GoldChart = GoldChart;
