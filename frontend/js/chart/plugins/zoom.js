/**
 * Scroll-to-zoom + drag-to-pan plugin for GoldChart.
 */
export const zoomPlugin = {
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

/**
 * Apply wheel zoom by adjusting chart.options.scales.x min/max.
 * Call this from the canvas wheel event listener.
 */
export function applyScrollZoom(chart, deltaY, mouseX) {
  const { chartArea, scales } = chart;
  if (!chartArea || !scales.x) return;
  const factor = deltaY > 0 ? 1.1 : 0.9;
  const center = scales.x.getValueForPixel(mouseX);
  const range  = (scales.x.max - scales.x.min) * factor;
  chart.options.scales.x.min = center - range / 2;
  chart.options.scales.x.max = center + range / 2;
  chart.update("none");
}
