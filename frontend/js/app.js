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

/**
 * Load briefings via SSE stream.
 */
function loadBriefings() {
  const es = new EventSource("/api/briefings/stream?days=3");

  _initBriefingSkeleton(); // renders two blocks with "正在生成..."

  const texts = { l12: "", l3: "" };
  const bodies = {
    l12: document.getElementById("body-l12"),
    l3: document.getElementById("body-l3"),
  };

  es.addEventListener("cached", (e) => {
    const data = JSON.parse(e.data);
    if (bodies.l12) bodies.l12.innerHTML = renderBriefing(data.blocks.l12 || "");
    if (bodies.l3) bodies.l3.innerHTML = renderBriefing(data.blocks.l3 || "");
    es.close();
  });

  es.addEventListener("token", (e) => {
    const { block, chunk } = JSON.parse(e.data);
    if (!bodies[block]) return;
    texts[block] += chunk;
    bodies[block].innerHTML = renderBriefing(texts[block]);
  });

  es.addEventListener("done", (e) => {
    const { news } = JSON.parse(e.data);
    if (news && news.length) _renderNews(news);
    es.close();
  });

  es.onerror = () => {
    es.close();
    const partial = texts.l12 || texts.l3;
    if (partial && bodies.l12) bodies.l12.innerHTML = renderBriefing(partial);
  };
}

/** Render news list in right panel */
function _renderNews(news) {
  const newsEl = document.getElementById("briefing-news-list");
  const newsSkeleton = document.getElementById("news-skeleton");
  if (!newsEl) return;
  if (newsSkeleton) newsSkeleton.style.display = 'none';
  newsEl.style.display = 'block';
  if (news.length === 0) {
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
  }
  if (chart) chart.setNews(news);
}

/** Render initial three blocks with all showing "正在生成..." */
function _initBriefingSkeleton() {
  const weeklyEl = document.getElementById("weekly-content");
  const weeklySkeleton = document.getElementById("briefing-skeleton");
  const weeklyContent = document.getElementById("briefing-content");
  if (weeklySkeleton) weeklySkeleton.style.display = 'none';
  if (weeklyContent) weeklyContent.style.display = 'block';
  if (!weeklyEl) return;

  weeklyEl.innerHTML = `
    <div class="analysis-block analysis-block--l12" id="block-l12">
      <div class="analysis-block__header"><span class="analysis-block__icon">📊</span><span class="analysis-block__title">📊 分析结论</span></div>
      <div class="analysis-block__body" id="body-l12"><div class="state-message">正在生成...</div></div>
    </div>
    <div class="analysis-block analysis-block--l3" id="block-l3">
      <div class="analysis-block__header"><span class="analysis-block__icon">🎯</span><span class="analysis-block__title">🎯 金价预期</span></div>
      <div class="analysis-block__body" id="body-l3"><div class="state-message">正在生成...</div></div>
    </div>
  `;
}

/** Fetch Layer 1 (parallel-safe, returns Promise) */
async function _loadLayer1() {
  const res = await fetch("/api/briefings/layer1?days=3");
  return res.json();
}

/** Process Layer 1 response + auto-expand the block */
function _loadLayer1Done(d) {
  const body = document.getElementById("layer1-body");
  if (!body || !d.content) return;
  body.innerHTML = renderBriefing(d.content);
  body.classList.remove("analysis-block__body--collapsed");
  const chevron = document.getElementById("layer1-chevron");
  if (chevron) chevron.textContent = "▾";
}

/** Update Layer 2 block with response data */
function _showLayer2(d) {
  const body = document.querySelector("#block-layer2 .analysis-block__body");
  if (body && d.content) {
    body.innerHTML = renderBriefing(d.content);
  }
}

/** Update Layer 3 block */
function _showLayer3(d) {
  const body = document.querySelector("#block-layer3 .analysis-block__body");
  if (body && d.content) {
    body.innerHTML = renderBriefing(d.content);
  }
}

/** Show legacy full-briefing response (for backward compat). */
function _showBriefing(data) {
  const weeklyEl = document.getElementById("weekly-content");
  const weeklySkeleton = document.getElementById("briefing-skeleton");
  const weeklyContent = document.getElementById("briefing-content");
  if (weeklySkeleton) weeklySkeleton.style.display = 'none';
  if (weeklyContent) weeklyContent.style.display = 'block';
  if (!weeklyEl) return;

  const weekly = data.weekly || {};
  const layer3 = weekly.layer3 || "";
  const layer2 = weekly.layer2 || "";
  const layer1 = weekly.layer1 || "";

  weeklyEl.innerHTML = `
    <div class="analysis-block analysis-block--layer3" id="block-layer3">
      <div class="analysis-block__header"><span class="analysis-block__icon">🎯</span><span class="analysis-block__title">金价预期</span></div>
      ${layer3
        ? `<div class="analysis-block__body">${renderBriefing(layer3)}</div>`
        : `<div class="analysis-block__body"><div class="state-message">正在生成...</div></div>`}
    </div><div class="analysis-block analysis-block--layer2" id="block-layer2">
      <div class="analysis-block__header"><span class="analysis-block__icon">📊</span><span class="analysis-block__title">行情验证</span></div>
      ${layer2
        ? `<div class="analysis-block__body">${renderBriefing(layer2)}</div>`
        : `<div class="analysis-block__body"><div class="state-message">正在生成...</div></div>`}
    </div><div class="analysis-block analysis-block--layer1" id="block-layer1">
      <div class="analysis-block__header analysis-block__header--toggle" id="layer1-toggle"><span class="analysis-block__icon">📰</span><span class="analysis-block__title">新闻分析</span><span class="analysis-block__chevron" id="layer1-chevron">▸</span></div>
      <div class="analysis-block__body analysis-block__body--collapsed" id="layer1-body">
        ${layer1
          ? renderBriefing(layer1)
          : `<div class="state-message">正在生成...</div>`}
      </div>
    </div>
  `;

  // Wire up Layer 1 collapsible toggle
  const toggle = document.getElementById("layer1-toggle");
  const body = document.getElementById("layer1-body");
  const chevron = document.getElementById("layer1-chevron");
  if (toggle && body && chevron) {
    toggle.addEventListener("click", () => {
      const isCollapsed = body.classList.contains("analysis-block__body--collapsed");
      body.classList.toggle("analysis-block__body--collapsed");
      chevron.textContent = isCollapsed ? "▾" : "▸";
    });
  }
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
  const srcColor = PRICE_SOURCE_COLORS[srcVal] || "#d4af37";
  priceEl.setAttribute("data-source", srcVal);
  priceEl.style.color = srcColor;
  priceEl.style.textShadow = "";

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
  loadBriefings();

});
