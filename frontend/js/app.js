/**
 * Main app: wires PollingManager, GoldChart, and event-driven modules.
 * All data driven by PollingManager (REST polling, no SSE).
 */
import { GoldChart } from "./chart/GoldChart.js";
import { PollingManager } from "./polling.js";
import { EventBus, on } from "./utils/eventBus.js";
import { onPriceUpdate, flashCardSource, initCardAppearance } from "./modules/priceUpdate.js";
import { loadBriefings } from "./modules/briefingUpdate.js";
import { loadNews } from "./modules/newsUpdate.js";

// Re-export showToast so other modules can use it
export { showToast } from "./modules/briefingUpdate.js";

const polling = new PollingManager();
let chart = null;

// ── Subscribe to EventBus instead of PollingManager callbacks ───────────────

on("prices:update", onPriceUpdate);

on("chart:update", ({ xau, au }) => {
  if (xau && chart) chart.loadXauFromCache(xau);
  if (au  && chart) chart.loadAuFromCache(au);
});

on("source:changed", ({ symbol, srcKey, srcVal }) => {
  if (symbol === "XAUUSD") polling.setSource("xau", srcVal);
  else if (symbol === "AU9999") polling.setSource("au", srcVal);
  else if (symbol === "USDCNY") polling.setSource("fx", srcVal);
});

// ── Source change handlers ──────────────────────────────────────────────────

function handleXauSourceChange(selXau, selAu) {
  if (!selXau) return;
  selXau.value = polling.getSource("xauChart");
  selXau.addEventListener("change", async () => {
    chart._switchingChart = "xau";
    polling._switchingChart = "xau";
    polling.setSource("xauChart", selXau.value);
    await chart.switchXauSource(selXau.value);
    polling._switchingChart = undefined;
    chart._switchingChart = undefined;
  });
}

function handleAuSourceChange(selAu) {
  if (!selAu) return;
  selAu.value = polling.getSource("auChart");
  selAu.addEventListener("change", async () => {
    chart._switchingChart = "au";
    polling._switchingChart = "au";
    polling.setSource("auChart", selAu.value);
    await chart.switchAuSource(selAu.value);
    polling._switchingChart = undefined;
    chart._switchingChart = undefined;
  });
}

function handlePriceSelectors() {
  const srcXau = document.getElementById("src-xau");
  const srcAu  = document.getElementById("src-au");
  const srcFx  = document.getElementById("src-fx");

  if (srcXau) {
    srcXau.value = polling.getSource("xau");
    srcXau.addEventListener("change", () => flashCardSource("XAUUSD"));
  }
  if (srcAu) {
    srcAu.value = polling.getSource("au");
    srcAu.addEventListener("change", () => flashCardSource("AU9999"));
  }
  if (srcFx) {
    srcFx.value = polling.getSource("fx");
    srcFx.addEventListener("change", () => flashCardSource("USDCNY"));
  }
}

// ── Bootstrap ───────────────────────────────────────────────────────────────

window.addEventListener("DOMContentLoaded", async () => {
  handlePriceSelectors();

  // Randomize card colors/fonts ONCE at startup — not on every price update
  initCardAppearance();

  // Fire news + briefing immediately — don't wait for chart load
  loadNews();
  loadBriefings();

  // Chart initialization
  chart = new GoldChart();
  chart.xauSource = polling.getSource("xauChart");
  chart.auSource  = polling.getSource("auChart");
  chart.warmup();   // no await — fetch starts async, load() awaits it internally
  await chart.load();
  window.__goldChart = chart;  // allow other modules to access chart instance
  polling._skipNextChartPoll = true;  // skip the first _pollChart since warmup+load already fetched

  // Chart source selectors
  const selXau = document.getElementById("sel-xau");
  const selAu  = document.getElementById("sel-au");
  handleXauSourceChange(selXau, selAu);
  handleAuSourceChange(selAu);

  // Wire PollingManager → EventBus
  polling.onPriceUpdate((data) => EventBus.emit("prices:update", data));
  polling.onChartUpdate((data) => EventBus.emit("chart:update", data));

  // Start polling
  polling.start("prices");
  polling.start("chart");
  polling.start("briefing");  // 15min — refreshes AI briefing in background
});
