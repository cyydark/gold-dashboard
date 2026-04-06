/**
 * PollingManager — replaces SSEClient.
 * Three independent polling channels: card-prices, chart-bars, news.
 * Each channel polls at its own interval and persists source choices.
 */
export class PollingManager {
  constructor() {
    this._timers = {};
    this._lastPrices = {};
    this._onPriceUpdate = null;
    this._onChartUpdate = null;
    this._onNewsUpdate = null;

    // Source defaults (权威性排序第一个)
    this._sources = {
      xau:      localStorage.getItem("source_xau")       || "comex",
      au:       localStorage.getItem("source_au")        || "au9999",
      fx:       localStorage.getItem("source_fx")        || "yfinance",
      xauChart: localStorage.getItem("source_xau_chart") || "comex",
      auChart:  localStorage.getItem("source_au_chart")  || "au9999",
    };
  }

  // ── Event callbacks ────────────────────────────────────────────────

  onPriceUpdate(fn)    { this._onPriceUpdate = fn; }
  onChartUpdate(fn)    { this._onChartUpdate = fn; }
  onNewsUpdate(fn)     { this._onNewsUpdate = fn; }

  // ── Source accessors ──────────────────────────────────────────────

  getSource(key) { return this._sources[key]; }

  setSource(key, value) {
    this._sources[key] = value;
    localStorage.setItem("source_" + key, value);
    if (key === "xau" || key === "au" || key === "fx") {
      this._pollPrices();
    }
    if (key === "xauChart" || key === "auChart") {
      this._pollChart();
    }
  }

  // ── Start / Stop ──────────────────────────────────────────────────

  start(channel) {
    if (this._timers[channel]) return;
    if (channel === "prices") {
      this._pollPrices();
      this._timers.prices = setInterval(() => this._pollPrices(), 10000);
    } else if (channel === "chart") {
      this._pollChart();
      this._timers.chart = setInterval(() => this._pollChart(), 30000);
    } else if (channel === "news") {
      this._pollNews();
      this._timers.news = setInterval(() => this._pollNews(), 30 * 60 * 1000);
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
    const [xau, au] = await Promise.allSettled([
      fetch(`/api/chart/xau?source=${this._sources.xauChart}`).then(r => r.json()),
      fetch(`/api/chart/au?source=${this._sources.auChart}`).then(r => r.json()),
    ]);

    if (this._onChartUpdate) {
      this._onChartUpdate({
        xau: xau.status === "fulfilled" ? xau.value : null,
        au:  au.status  === "fulfilled" ? au.value  : null,
      });
    }
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
