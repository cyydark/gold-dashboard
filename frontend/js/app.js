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

/** Render briefing text with basic HTML escaping. */
function renderBriefing(text) {
  return escapeHtml(text || "");
}

/**
 * Load news immediately (fast) + AI briefing in background (slow).
 * News shows right away; AI skeleton disappears when ready.
 */
async function loadBriefings() {
  const newsEl = document.getElementById("briefing-news-list");
  const newsCountEl = document.getElementById("news-count");
  const newsSkeleton = document.getElementById("news-skeleton");
  if (!newsEl) return;

  // Step 1: Load news immediately (no AI involved, 3 days)
  fetch("/api/news?days=3")
    .then(r => r.json())
    .then(data => {
      const news = data.news || [];
      if (newsSkeleton) newsSkeleton.style.display = 'none';
      if (newsEl) newsEl.style.display = 'block';
      if (newsCountEl) newsCountEl.textContent = `${news.length}条`;
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
    })
    .catch(() => {
      if (newsSkeleton) newsSkeleton.style.display = 'none';
      if (newsEl) newsEl.style.display = 'block';
      newsEl.innerHTML = '<div class="state-message">资讯加载失败</div>';
    });

  // Step 2: Load AI briefing in background (uses TTL cache, ~1h)
  try {
    const res = await fetch("/api/briefings?days=3");
    const data = await res.json();
    _showBriefing(data);
  } catch (e) {
    const weeklyEl = document.getElementById("weekly-content");
    const weeklySkeleton = document.getElementById("briefing-skeleton");
    const weeklyContent = document.getElementById("briefing-content");
    if (weeklySkeleton) weeklySkeleton.style.display = 'none';
    if (weeklyContent) weeklyContent.style.display = 'block';
    if (weeklyEl) weeklyEl.innerHTML = '<div class="state-message">AI 分析加载失败</div>';
  }
}

/** Show AI briefing content, hide skeleton. */
function _showBriefing(data) {
  const weeklyEl = document.getElementById("weekly-content");
  const weeklySkeleton = document.getElementById("briefing-skeleton");
  const weeklyContent = document.getElementById("briefing-content");
  if (weeklySkeleton) weeklySkeleton.style.display = 'none';
  if (weeklyContent) weeklyContent.style.display = 'block';
  if (!weeklyEl) return;

  const weekly = data.weekly || {};
  const crossValidation = weekly.cross_validation || "";
  const newsAnalysis = weekly.news_analysis || "";

  const parts = [];

  // cross_validation is primary; news_analysis is fallback
  if (crossValidation) {
    parts.push(
      `<div class="briefing__analysis-block">` +
        `<div class="briefing__label">📊 行情验证</div>` +
        `<div class="briefing__text">${renderBriefing(crossValidation)}</div>` +
      `</div>`
    );
  }

  if (newsAnalysis) {
    parts.push(
      `<div class="briefing__analysis-block">` +
        `<div class="briefing__label">📰 新闻分析</div>` +
        `<div class="briefing__text">${renderBriefing(newsAnalysis)}</div>` +
      `</div>`
    );
  }

  if (parts.length === 0) {
    parts.push(
      `<div class="briefing__analysis-block">` +
        `<div class="briefing__label">📰 新闻分析</div>` +
        `<div class="briefing__text">暂无分析</div>` +
      `</div>`
    );
  }

  weeklyEl.innerHTML = parts.join("");
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
  comex:     "#d4af37",
  binance:   "#fb923c",
  sina:      "#c084fc",
  au9999:    "#d4af37",
  eastmoney: "#d4af37",
  yfinance:  "#d4af37",
  sina_au0:  "#fb923c",
};

/** Per-symbol blocking state: while non-null, price updates are deferred */
const _blocked = {};

/** Apply a deferred price update now */
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
  const srcSel = document.getElementById(`src-${srcKeyMap[symbol]}`);
  const srcVal = srcSel ? srcSel.value : "";
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

/** Update a price card — deferred while source-switch animation is playing */
function updatePriceCard(symbol, data) {
  if (!data) return;

  const skeletonEl = document.getElementById(`skeleton-${symbol}`);
  const cardEl = document.getElementById(`card-${symbol}`);
  if (skeletonEl && cardEl) {
    skeletonEl.style.display = 'none';
    cardEl.style.display = 'block';
  }

  // If blocked (source switch in progress), buffer the data
  if (_blocked[symbol]) {
    _blocked[symbol] = data;
    return;
  }

  _applyPrice(symbol, data);
}

/** Flash a card on source switch: gold ring + source tag + block price updates 1.2s */
function flashCardSource(symbol) {
  const card = document.getElementById(`card-${symbol}`);
  if (!card) return;

  const selMap    = { XAUUSD: "src-xau", AU9999: "src-au", USDCNY: "src-fx" };
  const sel = document.getElementById(selMap[symbol]);
  const srcVal = sel ? sel.value : "";
  const srcColor = PRICE_SOURCE_COLORS[srcVal] || "#d4af37";
  const priceEl = document.getElementById(`price-${symbol}`);

  // Remove stale tag
  const oldTag = card.querySelector(".price-card__source-tag");
  if (oldTag) oldTag.remove();

  // Restart card ring flash animation
  card.classList.remove("price-card--switched");
  void card.offsetWidth;
  card.classList.add("price-card--switched");

  // Immediately apply source color to price number (no data change yet)
  if (priceEl) {
    priceEl.style.color = srcColor;
    priceEl.style.textShadow = "";
  }

  // Show source tag badge
  const srcName = sel ? sel.options[sel.selectedIndex].text : "";
  const tag = document.createElement("span");
  tag.className = "price-card__source-tag";
  tag.textContent = srcName;
  card.appendChild(tag);

  // Block price updates for 1.2s (match CSS animation duration)
  _blocked[symbol] = null;
  setTimeout(() => {
    card.classList.remove("price-card--switched");
    if (tag.parentNode) tag.remove();
    // Unblock and apply any pending data that arrived during animation
    const pending = _blocked[symbol];
    _blocked[symbol] = null;
    if (pending && priceEl) {
      _applyPrice(symbol, pending);
    }
  }, 1200);
}

window.addEventListener("DOMContentLoaded", async () => {
  // Wire up card source selectors — only trigger visual flash,
  // polling will naturally use the new source on next tick
  const srcXau = document.getElementById("src-xau");
  const srcAu = document.getElementById("src-au");
  const srcFx = document.getElementById("src-fx");
  if (srcXau) {
    srcXau.value = polling.getSource("xau");
    srcXau.addEventListener("change", () => {
      polling.setSource("xau", srcXau.value); // update source + save to localStorage
      flashCardSource("XAUUSD");              // block price update 1.2s
    });
  }
  if (srcAu) {
    srcAu.value = polling.getSource("au");
    srcAu.addEventListener("change", () => {
      polling.setSource("au", srcAu.value);
      flashCardSource("AU9999");
    });
  }
  if (srcFx) {
    srcFx.value = polling.getSource("fx");
    srcFx.addEventListener("change", () => {
      polling.setSource("fx", srcFx.value);
      flashCardSource("USDCNY");
    });
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
      await chart.switchXauSource(selXau.value);
      polling.setSource("xauChart", selXau.value);
    });
  }
  if (selAu) {
    selAu.value = polling.getSource("auChart");
    selAu.addEventListener("change", async () => {
      await chart.switchAuSource(selAu.value);
      polling.setSource("auChart", selAu.value);
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
  polling.start("news");

  // DEBUG: refresh buttons
  const btnNews = document.getElementById("btn-refresh-news");
  const btnBriefing = document.getElementById("btn-refresh-briefing");
  const debugStatus = document.getElementById("debug-status");

  if (btnNews) {
    btnNews.addEventListener("click", async () => {
      btnNews.disabled = true;
      btnNews.textContent = "⏳...";
      if (debugStatus) debugStatus.textContent = "刷新资讯...";
      try {
        const res = await fetch("/api/news?days=3");
        const data = await res.json();
        const news = data.news || [];
        const newsEl = document.getElementById("briefing-news-list");
        const newsCountEl = document.getElementById("news-count");
        if (newsCountEl) newsCountEl.textContent = `${news.length}条`;
        if (newsEl) {
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
        }
        if (chart) chart.setNews(news);
        if (debugStatus) debugStatus.textContent = "";
        showToast(`资讯已更新，共 ${news.length} 条`, "info");
      } catch (e) {
        if (debugStatus) debugStatus.textContent = "";
        showToast("刷新失败: " + e.message, "error");
      } finally {
        btnNews.disabled = false;
        btnNews.textContent = "🔄 刷新资讯";
      }
    });
  }

  if (btnBriefing) {
    btnBriefing.addEventListener("click", async () => {
      const weeklySkeleton = document.getElementById("briefing-skeleton");
      const weeklyContent = document.getElementById("briefing-content");
      const weeklyEl = document.getElementById("weekly-content");
      btnBriefing.disabled = true;
      btnBriefing.textContent = "⏳...";
      if (debugStatus) debugStatus.textContent = "生成中...";
      if (weeklyContent) weeklyContent.style.display = 'none';
      if (weeklySkeleton) weeklySkeleton.style.display = 'block';
      if (weeklyEl) weeklyEl.innerHTML = '';
      try {
        const res = await fetch("/api/briefings/briefing/refresh?days=3", { method: "POST" });
        const data = await res.json();
        _showBriefing(data);
        if (debugStatus) debugStatus.textContent = "";
        showToast("AI 分析已更新", "info");
      } catch (e) {
        if (weeklySkeleton) weeklySkeleton.style.display = 'none';
        if (weeklyContent) weeklyContent.style.display = 'block';
        if (weeklyEl) weeklyEl.innerHTML = '<div class="state-message">生成失败</div>';
        if (debugStatus) debugStatus.textContent = "";
        showToast("AI 分析生成失败: " + e.message, "error");
      } finally {
        btnBriefing.disabled = false;
        btnBriefing.textContent = "🧠 刷新AI分析";
      }
    });
  }

});
