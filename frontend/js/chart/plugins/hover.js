/**
 * Hover crosshair plugin for GoldChart.
 *
 * Responsibilities:
 * - Track mouse X position via afterEvent
 * - Binary-search nearest data point in each dataset (null-safe)
 * - Draw dashed vertical line + floating tooltip box in afterDatasetsDraw
 * - Only show a dataset's value when cursor is within THRESHOLD_PX of that point
 */
import { fmtBJ, fmtUS, findNearest } from "../utils/time.js";

const THRESHOLD_PX = 5;

export const hoverPlugin = {
  id: "goldHover",

  _mouseX: null,
  _nearest: null,
  _lastDraw: 0,

  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea || !scales.x || !scales.y) return;
    if (this._mouseX === null) return;

    const xPx = this._mouseX;
    if (xPx < chartArea.left || xPx > chartArea.right) return;

    const rawTs = scales.x.getValueForPixel(xPx);
    const nearest = this._nearest;
    const xauRaw = nearest?.xau || null;
    const auRaw  = nearest?.au  || null;

    // Only show if cursor is within THRESHOLD_PX of that dataset's nearest point
    const xauPt = xauRaw && Math.abs(xPx - scales.x.getPixelForValue(xauRaw.x)) <= THRESHOLD_PX ? xauRaw : null;
    const auPt  = auRaw  && Math.abs(xPx - scales.x.getPixelForValue(auRaw.x))  <= THRESHOLD_PX ? auRaw  : null;

    if (!xauPt && !auPt) return;

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

    // Floating label box
    const lineH = 18, pad2 = 8;
    ctx.font = "12px Inter, sans-serif";
    const maxW = Math.max(...lines.map(l => ctx.measureText(l.t).width));
    const boxW = maxW + pad2 * 2;
    const boxH = lines.length * lineH + pad2;

    let boxX = xPx + 8;
    if (boxX + boxW > chartArea.right - 4) boxX = xPx - boxW - 8;

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
          xau: findNearest(xauData, rawTs),
          au:  findNearest(auData,  rawTs),
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
