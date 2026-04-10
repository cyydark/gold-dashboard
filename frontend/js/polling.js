/**
 * PollingManager — replaces SSEClient.
 * Three independent polling channels: card-prices, chart-bars, news.
 * Each channel polls at its own interval and persists source choices.
 */
const POLL_INTERVAL_PRICES   = 10000;   // 10s
const POLL_INTERVAL_CHART    = 30000;   // 30s
const POLL_INTERVAL_NEWS     = 30 * 60 * 1000;  // 30min — kept for compatibility
const POLL_INTERVAL_BRIEFING = 15 * 60 * 1000;  // 15min — unified briefing poll

export class PollingManager {
  constructor() {
    this._timers = {};
    this._lastPrices = {};
    this._lastChart  = {};
    this._onPriceUpdate    = null;
    this._onChartUpdate    = null;
    this._onNewsUpdate     = null;
    this._onBriefingUpdate = null;
    this._switchingChart = null; // null = idle, "xau"/"au" = switching (set by app.js)
    // Source defaults (权威性排序第一个)
    this._sources = {
      xau:      localStorage.getItem("source_xau")        || "comex",
      au:       localStorage.getItem("source_au")         || "au9999",
      fx:       localStorage.getItem("source_fx")           || "yfinance",
      xauChart: localStorage.getItem("source_xauChart")   || "binance",
      auChart:  localStorage.getItem("source_auChart")    || "sina_au0",
    };
  }

  // ── Event callbacks ────────────────────────────────────────────────

  onPriceUpdate(fn)    { this._onPriceUpdate = fn; }
  onChartUpdate(fn)    { this._onChartUpdate = fn; }
  onNewsUpdate(fn)     { this._onNewsUpdate = fn; }
  onBriefingUpdate(fn) { this._onBriefingUpdate = fn; }

  // ── Source accessors ──────────────────────────────────────────────

  getSource(key) { return this._sources[key]; }

  setSource(key, value) {
    this._sources[key] = value;
    localStorage.setItem("source_" + key, value);
    if (key === "xau" || key === "au" || key === "fx") {
      // 只刷新被切换的那个源，保留其他两个最近缓存
      this._pollPricesOne(key === "xau" ? "XAUUSD" : key === "au" ? "AU9999" : "USDCNY");
    }
    if (key === "xauChart") {
      return this._pollChartOne("xau");
    }
    if (key === "auChart") {
      return this._pollChartOne("au");
    }
  }

  // ── Start / Stop ──────────────────────────────────────────────────

  start(channel) {
    if (this._timers[channel]) return;
    if (channel === "prices") {
      this._pollPrices();
      this._timers.prices = setInterval(() => this._pollPrices(), POLL_INTERVAL_PRICES);
    } else if (channel === "chart") {
      this._pollChart();
      this._timers.chart = setInterval(() => this._pollChart(), POLL_INTERVAL_CHART);
    } else if (channel === "news") {
      this._pollNews();
      this._timers.news = setInterval(() => this._pollNews(), POLL_INTERVAL_NEWS);
    } else if (channel === "briefing") {
      this._pollBriefing();
      this._timers.briefing = setInterval(() => this._pollBriefing(), POLL_INTERVAL_BRIEFING);
    }
  }

  stop(channel) {
    if (this._timers[channel]) {
      clearInterval(this._timers[channel]);
      delete this._timers[channel];
    }
  }

  stopAll() {
    Object.keys(this._timers).forEach(k => this.stop(k));
  }

  // 只抓单个源，合并到最近缓存后回调（用于 source 切换时零刷新）
  async _pollPricesOne(sym) {
    const urlMap = {
      XAUUSD: `/api/realtime/xau/${this._sources.xau}`,
      AU9999: `/api/realtime/au/${this._sources.au}`,
      USDCNY: `/api/realtime/fx/${this._sources.fx}`,
    };
    const lastMap = { XAUUSD: "xau", AU9999: "au", USDCNY: "fx" };
    const cacheKey = lastMap[sym];
    const url = urlMap[sym];
    if (!url) return;

    try {
      const r = await fetch(url);
      const d = await r.json();
      if (d.price != null) {
        this._lastPrices[cacheKey] = d;
        const result = { [sym]: d };
        // 合并其他两个最近缓存（不重新请求）
        if (sym !== "XAUUSD" && this._lastPrices.xau)   result.XAUUSD = this._lastPrices.xau;
        if (sym !== "AU9999" && this._lastPrices.au)    result.AU9999 = this._lastPrices.au;
        if (sym !== "USDCNY" && this._lastPrices.fx)   result.USDCNY = this._lastPrices.fx;
        if (this._onPriceUpdate) this._onPriceUpdate(result);
      }
    } catch (_) {}
  }

  // 只抓单个图表，合并到最近缓存后回调（用于 chart source 切换时零刷新）
  async _pollChartOne(which) {
    const chartGapMs = window.__goldChart?.gapThresholdMs ?? (30 * 60 * 1000);
    const threshold = `&gap_threshold_ms=${chartGapMs}`;
    const urlMap  = { xau: `/api/chart/xau?source=${this._sources.xauChart}${threshold}`, au: `/api/chart/au?source=${this._sources.auChart}${threshold}` };
    const url = urlMap[which];
    if (!url) return;
    // If a switch is in progress, switchXauSource/switchAuSource already fetched + rendered;
    // skip the entire fetch to avoid a duplicate request.
    if (this._switchingChart) return;
    try {
      const r = await fetch(url);
      const d = await r.json();
      this._lastChart[which] = d;
      if (this._onChartUpdate) {
        this._onChartUpdate({
          xau: which === "xau" ? d : (this._lastChart.xau || null),
          au:  which === "au"  ? d : (this._lastChart.au  || null),
        });
      }
    } catch (_) {}
  }

  // ── Private pollers ────────────────────────────────────────────────

  async _pollPrices() {
    const [xau, au, fx] = await Promise.allSettled([
      fetch(`/api/realtime/xau/${this._sources.xau}`).then(r => r.json()),
      fetch(`/api/realtime/au/${this._sources.au}`).then(r => r.json()),
      fetch(`/api/realtime/fx/${this._sources.fx}`).then(r => r.json()),
    ]);

    const result = {};
    if (xau.status === "fulfilled" && xau.value.price != null) {
      result.XAUUSD = xau.value;
      this._lastPrices.xau = xau.value;
    } else if (this._lastPrices.xau) {
      result.XAUUSD = { ...this._lastPrices.xau, error: "获取失败" };
    }
    if (au.status === "fulfilled" && au.value.price != null) {
      result.AU9999 = au.value;
      this._lastPrices.au = au.value;
    } else if (this._lastPrices.au) {
      result.AU9999 = { ...this._lastPrices.au, error: "获取失败" };
    }
    if (fx.status === "fulfilled" && fx.value.price != null) {
      result.USDCNY = fx.value;
      this._lastPrices.fx = fx.value;
    } else if (this._lastPrices.fx) {
      result.USDCNY = { ...this._lastPrices.fx, error: "获取失败" };
    }

    if (Object.keys(result).length > 0 && this._onPriceUpdate) {
      this._onPriceUpdate(result);
    }
  }

  async _pollChart() {
    // Skip first poll right after page load — warmup+load already has fresh data
    if (this._skipNextChartPoll) {
      this._skipNextChartPoll = false;
      return;
    }
    // Skip if a switch is in progress — switchXauSource/switchAuSource handles the fetch
    if (this._switchingChart) return;
    // Use gap threshold from GoldChart if available, otherwise default 30min
    const chartGapMs = window.__goldChart?.gapThresholdMs ?? (30 * 60 * 1000);
    const threshold = `&gap_threshold_ms=${chartGapMs}`;
    const [xau, au] = await Promise.allSettled([
      fetch(`/api/chart/xau?source=${this._sources.xauChart}${threshold}`).then(r => r.json()),
      fetch(`/api/chart/au?source=${this._sources.auChart}${threshold}`).then(r => r.json()),
    ]);

    if (xau.status === "fulfilled") this._lastChart.xau = xau.value;
    if (au.status  === "fulfilled") this._lastChart.au  = au.value;

    if (this._onChartUpdate) {
      this._onChartUpdate({
        xau: xau.status === "fulfilled" ? xau.value : null,
        au:  au.status  === "fulfilled" ? au.value  : null,
      });
    }
  }

  async _pollBriefing() {
    // loadBriefings() handles SWR internally — just call it
    const { loadBriefings } = await import("./modules/briefingUpdate.js");
    loadBriefings();
  }

  async _pollNews() {
    try {
      const r = await fetch("/api/news");
      const d = await r.json();
      if (this._onNewsUpdate) this._onNewsUpdate(d.news || []);
    } catch (_) {}
  }
}

window.PollingManager = PollingManager;
