/**
 * Main app: price cards + dual gold chart + news.
 * All data driven by PollingManager (REST polling, no SSE).
 */
import { GoldChart } from "./chart/GoldChart.js";
import { PollingManager } from "./polling.js";

const polling = new PollingManager();
let chart = null;

/** Animate a number change with a flash effect */
function animatePriceChange(element, newValue) {
  if (!element) return;
  const oldValue = element.textContent;
  if (oldValue !== newValue) {
    element.style.transform = 'scale(1.05)';
    element.style.transition = 'transform 0.15s ease-out';
    setTimeout(() => {
      element.textContent = newValue;
      element.style.transform = 'scale(1)';
    }, 50);
  }
}

/** Show toast notification */
function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
window.showToast = showToast;

function onPriceUpdate(data) {
  if (!data) return;
  const el = document.getElementById("last-update");
  if (el) {
    const ts = data.XAUUSD?.ts || data.AU9999?.ts || data.USDCNY?.ts;
    if (ts) {
      const d = new Date(ts * 1000);
      el.textContent = `更新于 ${d.toLocaleTimeString("zh-CN", {hour:"2-digit",minute:"2-digit",second:"2-digit",timeZone:"Asia/Shanghai"})} 北京时间`;
    }
  }
  for (const sym of ["XAUUSD", "AU9999", "USDCNY"]) {
    if (data[sym]) updatePriceCard(sym, data[sym]);
  }
}
window.onPriceUpdate = onPriceUpdate;

function _timeAgo(tsSec) {
  if (!tsSec) return "未知";
  const diffMs = Date.now() - tsSec * 1000;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}小时前`;
  return `${Math.floor(diffHr / 24)}天前`;
}

function _bjTime(tsSec) {
  if (!tsSec) return "";
  const d = new Date(tsSec * 1000);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day} ${h}:${min} 北京`;
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Render briefing text, converting 【】 sections to styled HTML. */
function renderBriefing(text) {
  const escaped = escapeHtml(text || "");
  return escaped.replace(/【(.+?)】/g, '<span class="section-label">【$1】</span>');
}

/** Load news via REST API (runs independently of briefing SSE). */
async function loadNews(days = 3) {
  try {
    const res = await fetch(`/api/news?days=${days}`);
    if (!res.ok) throw new Error(`news API ${res.status}`);
    const data = await res.json();
    const items = data.news || data.data || [];
    _renderNews(items);
  } catch (err) {
    console.error("loadNews failed:", err);
  }
}

/** Load briefings via SSE stream (AI content only, news is loaded separately). */
function loadBriefings() {
  const es = new EventSource("/api/briefings/stream?days=3");

  _initBriefingSkeleton();

  let reconnectCount = 0;
  const MAX_RECONNECT = 3;

  const texts = { l12: "", l3: "" };
  const bodies = {
    l12: document.getElementById("body-l12"),
    l3: document.getElementById("body-l3"),
  };

  es.addEventListener("cached", (e) => {
    const data = JSON.parse(e.data);
    if (data.blocks) {
      if (bodies.l12 && data.blocks.l12) bodies.l12.innerHTML = renderBriefing(data.blocks.l12);
      if (bodies.l3 && data.blocks.l3) bodies.l3.innerHTML = renderBriefing(data.blocks.l3);
    }
    _hideBriefingSkeleton();
    es.close();
  });

  es.addEventListener("token", (e) => {
    const { block, chunk } = JSON.parse(e.data);
    if (!bodies[block]) return;
    texts[block] += chunk;
    bodies[block].innerHTML = renderBriefing(texts[block]);
    _hideBriefingSkeleton();
  });

  es.addEventListener("block-done", () => {});

  es.addEventListener("done", () => {
    es.close();
  });

  es.onerror = () => {
    reconnectCount++;
    if (reconnectCount >= MAX_RECONNECT) {
      es.close();
      _hideBriefingSkeleton();
      console.error("SSE reconnected too many times, giving up");
      if (texts.l12 && bodies.l12) bodies.l12.innerHTML = renderBriefing(texts.l12);
      if (texts.l3 && bodies.l3) bodies.l3.innerHTML = renderBriefing(texts.l3);
      const hadContent = texts.l12 || texts.l3;
      if (!hadContent) showToast("AI 分析加载失败，请刷新重试", "error");
    }
  };
}

/** Render news list in right panel */
function _renderNews(news) {
  try {
    const newsEl = document.getElementById("briefing-news-list");
    const newsSkeleton = document.getElementById("news-skeleton");
    if (!newsEl) return;
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    newsEl.style.display = 'block';
    if (!news || news.length === 0) {
      newsEl.innerHTML = '<div class="state-message">暂无资讯</div>';
    } else {
      newsEl.innerHTML = news.map((n, index) => `
        <a class="news-item" href="${escapeHtml(n.url || "#")}" target="_blank" rel="noopener" style="animation-delay: ${index * 50}ms">
          <div class="news-item__meta">
            <span class="news-item__source">${escapeHtml(n.source || "")}</span>
            <span>·</span>
            <span title="${escapeHtml(_bjTime(n.published_ts))}">${escapeHtml(_timeAgo(n.published_ts))}</span>
          </div>
          <div class="news-item__title">${escapeHtml(n.title || n.title_en || "")}</div>
        </a>`).join("");
      if (chart) chart.setNews(news);
    }
  } catch (err) {
    console.error("_renderNews error:", err);
  }
}

/** Hide briefing skeleton once real content arrives */
function _hideBriefingSkeleton() {
  const skeleton = document.getElementById("briefing-skeleton");
  if (skeleton) skeleton.style.display = 'none';
}

/** Render initial two blocks — "加载中" until SSE cached event fills them in. */
function _initBriefingSkeleton() {
  const weeklyEl = document.getElementById("weekly-content");
  const weeklySkeleton = document.getElementById("briefing-skeleton");
  const weeklyContent = document.getElementById("briefing-content");
  if (weeklySkeleton) weeklySkeleton.style.display = 'none';
  if (weeklyContent) weeklyContent.style.display = 'block';
  if (!weeklyEl) return;

  weeklyEl.innerHTML = `
    <div class="analysis-block analysis-block--l3" id="block-l3">
      <div class="analysis-block__header"><span class="analysis-block__icon">🎯</span><span class="analysis-block__title">金价预期</span></div>
      <div class="analysis-block__body" id="body-l3"><div class="state-message">加载中...</div></div>
    </div>
    <div class="analysis-block analysis-block--l12" id="block-l12">
      <div class="analysis-block__header"><span class="analysis-block__icon">📊</span><span class="analysis-block__title">分析结论</span></div>
      <div class="analysis-block__body" id="body-l12"><div class="state-message">加载中...</div></div>
    </div>
  `;
}

const XAU_LEGEND = {
  comex:   "COMEX GC00Y",
  binance: "XAUTUSDT (Binance)",
  sina:    "Sina 伦敦金 (hf_XAU)",
};

async function reloadChart() {
  const selXau = document.getElementById("sel-xau");
  const selAu = document.getElementById("sel-au");
  const legendXau = document.getElementById("legend-xau");

  const xau = selXau ? selXau.value : "comex";
  const au  = selAu ? selAu.value  : "au9999";

  if (legendXau) {
    legendXau.textContent = XAU_LEGEND[xau] || "COMEX GC00Y";
  }

  chart.xauSource = xau;
  chart.auSource = au;
  await polling.setSource("xauChart", xau);
  await polling.setSource("auChart", au);
}

/** Source → price number color map */
const PRICE_SOURCE_COLORS = {
  // XAU sources
  comex:     "#d4af37",   // gold
  binance:   "#fb923c",   // orange
  sina:      "#c084fc",   // violet
  // AU sources
  au9999:    "#34d399",   // emerald green
  eastmoney: "#38bdf8",   // sky blue
  // FX sources
  yfinance:  "#fbbf24",   // amber
  sina_au0:  "#fb923c",   // orange
};

/** Random font pool for price numbers (6 fonts, varied aesthetics) */
const FONT_POOL = [
  "'Cormorant Garamond', serif",
  "'DM Sans', sans-serif",
  "'JetBrains Mono', monospace",
  "'Playfair Display', serif",
  "'Space Grotesk', sans-serif",
  "'IBM Plex Mono', monospace",
];

/** Rich color pool for price numbers */
const COLOR_POOL = [
  "#d4af37",  // gold
  "#fb923c",  // orange
  "#c084fc",  // violet
  "#34d399",  // emerald
  "#38bdf8",  // sky blue
  "#fbbf24",  // amber
  "#f472b6",  // pink
  "#a78bfa",  // purple
  "#4ade80",  // green
  "#fb7185",  // rose
  "#facc15",  // yellow
  "#22d3ee",  // cyan
];

/** Random color/font state per symbol — changes every update with no repeats */
const _symbolStyle = {};
function _rand(pool, prev) {
  let item;
  do {
    item = pool[Math.floor(Math.random() * pool.length)];
  } while (item === prev && pool.length > 1);
  return item;
}
function _styleFor(symbol, pool, key) {
  if (!_symbolStyle[symbol]) _symbolStyle[symbol] = {};
  const prev = _symbolStyle[symbol][key];
  const next = _rand(pool, prev);
  _symbolStyle[symbol][key] = next;
  return next;
}

/** Apply a price update to DOM */
function _applyPrice(symbol, data) {
  const priceEl = document.getElementById(`price-${symbol}`);
  const changeEl = document.getElementById(`change-${symbol}`);
  const card = document.getElementById(`card-${symbol}`);
  const openEl = document.getElementById(`open-${symbol}`);
  const highEl = document.getElementById(`high-${symbol}`);
  const lowEl = document.getElementById(`low-${symbol}`);
  if (!priceEl) return;

  if (data.error) {
    showToast(`${symbol}：${data.error}`, "error");
    return;
  }

  const srcKeyMap = { XAUUSD: "xau", AU9999: "au", USDCNY: "fx" };
  const sel = document.getElementById(`src-${srcKeyMap[symbol]}`);
  const srcVal = sel ? sel.value : "";
  // Randomize color and font on every update for visual variety
  const color = _styleFor(symbol, COLOR_POOL, "color");
  const font = _styleFor(symbol, FONT_POOL, "font");
  priceEl.setAttribute("data-source", srcVal);
  priceEl.style.color = color;
  priceEl.style.fontFamily = font;
  priceEl.style.textShadow = "";
  changeEl.setAttribute("data-source", srcVal);
  changeEl.style.fontFamily = font;

  animatePriceChange(priceEl, `${data.price} ${data.unit || ""}`);

  const hasChange = data.change != null && data.pct != null;
  if (hasChange) {
    const sign = data.change >= 0 ? "+" : "";
    const changeText = `${sign}${data.change} (${sign}${data.pct}%)`;
    animatePriceChange(changeEl, changeText);
    changeEl.className = `price-card__change price-card__change--${data.change >= 0 ? "up" : "down"}`;
    if (card) {
      card.classList.remove("price-card--up", "price-card--down");
      const animClass = data.change >= 0 ? "price-card--up" : "price-card--down";
      card.classList.add(animClass);
      setTimeout(() => card.classList.remove(animClass), 600);
    }
  } else {
    changeEl.textContent = "";
    changeEl.className = "price-card__change";
    if (card) card.classList.remove("price-card--up", "price-card--down");
  }

  if (data.open != null && data.high != null && data.low != null) {
    if (openEl) openEl.textContent = data.open;
    if (highEl) highEl.textContent = data.high;
    if (lowEl) lowEl.textContent = data.low;
  }
}

/** Update a price card */
function updatePriceCard(symbol, data) {
  if (!data) return;

  const skeletonEl = document.getElementById(`skeleton-${symbol}`);
  const cardEl = document.getElementById(`card-${symbol}`);
  if (skeletonEl && cardEl) {
    skeletonEl.style.display = 'none';
    cardEl.style.display = 'block';
  }

  _applyPrice(symbol, data);
}

/** Flash card and defer source change: color + tag immediately, source + fetch after 1.2s */
function flashCardSource(symbol) {
  const card = document.getElementById(`card-${symbol}`);
  if (!card) return;

  const selMap  = { XAUUSD: "src-xau", AU9999: "src-au", USDCNY: "src-fx" };
  const sel = document.getElementById(selMap[symbol]);
  const srcVal = sel ? sel.value : "";
  const srcColor = PRICE_SOURCE_COLORS[srcVal] || "#d4af37";
  const priceEl = document.getElementById(`price-${symbol}`);

  // Remove stale tag
  const oldTag = card.querySelector(".price-card__source-tag");
  if (oldTag) oldTag.remove();

  // Card ring flash
  card.classList.remove("price-card--switched");
  void card.offsetWidth;
  card.classList.add("price-card--switched");

  // Immediately apply source-specific color to price number
  if (priceEl) {
    priceEl.style.color = srcColor;
    priceEl.style.textShadow = "";
    priceEl.setAttribute("data-source", srcVal);
  }

  // Source tag badge
  const srcName = sel ? sel.options[sel.selectedIndex].text : "";
  const tag = document.createElement("span");
  tag.className = "price-card__source-tag";
  tag.textContent = srcName;
  card.appendChild(tag);

  // Immediately update source + fetch new data; keep tag visible for 1.2s as animation
  const srcKey = { XAUUSD: "xau", AU9999: "au", USDCNY: "fx" }[symbol];
  if (srcKey) polling.setSource(srcKey, srcVal);

  setTimeout(() => {
    card.classList.remove("price-card--switched");
    if (tag.parentNode) tag.remove();
  }, 1200);
}

window.addEventListener("DOMContentLoaded", async () => {
  // Wire up card source selectors — flashCardSource handles
  // the color immediately and triggers fetch after 1.2s animation
  const srcXau = document.getElementById("src-xau");
  const srcAu = document.getElementById("src-au");
  const srcFx = document.getElementById("src-fx");
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

  // Fire news + briefing immediately — don't wait for chart load
  loadNews();
  loadBriefings();

  // Chart initialization (takes ~2s, independent of news/AI)
  chart = new GoldChart();
  chart.xauSource = polling.getSource("xauChart");
  chart.auSource  = polling.getSource("auChart");
  chart.warmup();
  await chart.load();

  // Chart source selectors
  const selXau = document.getElementById("sel-xau");
  const selAu = document.getElementById("sel-au");
  if (selXau) {
    selXau.value = polling.getSource("xauChart");
    selXau.addEventListener("change", async () => {
      // Block polling from interfering while switch is in progress
      chart._switchingChart = "xau";
      polling._switchingChart = "xau";
      polling.setSource("xauChart", selXau.value);
      await chart.switchXauSource(selXau.value);
      polling._switchingChart = undefined;
      chart._switchingChart = undefined;
    });
  }
  if (selAu) {
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

  // Plug PollingManager into app
  polling.onPriceUpdate(onPriceUpdate);
  polling.onChartUpdate(({ xau, au }) => {
    if (xau) chart.loadXauFromCache(xau);
    if (au)  chart.loadAuFromCache(au);
  });

  // Start polling
  polling.start("prices");
  polling.start("chart");

});
