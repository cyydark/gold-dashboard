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

/** Update a price card with new data */
function updatePriceCard(symbol, data) {
  if (!data) return;

  const skeletonEl = document.getElementById(`skeleton-${symbol}`);
  const cardEl = document.getElementById(`card-${symbol}`);
  if (skeletonEl && cardEl) {
    skeletonEl.style.display = 'none';
    cardEl.style.display = 'block';
  }

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

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

async function loadBriefings() {
  const weeklyEl = document.getElementById("weekly-content");
  const newsEl = document.getElementById("briefing-news-list");
  const weeklyTimeEl = document.getElementById("weekly-time");
  const newsCountEl = document.getElementById("news-count");
  const briefingSkeleton = document.getElementById("briefing-skeleton");
  const briefingContent = document.getElementById("briefing-content");
  const newsSkeleton = document.getElementById("news-skeleton");
  if (!weeklyEl) return;

  try {
    const res = await fetch("/api/briefings?days=3");
    const data = await res.json();
    const weeklyData = data.weekly;
    const news = data.news || [];

    if (briefingSkeleton) briefingSkeleton.style.display = 'none';
    if (briefingContent) briefingContent.style.display = 'block';
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    if (newsEl) newsEl.style.display = 'block';

    if (weeklyData) {
      weeklyTimeEl.textContent = weeklyData.time_range || "";
      weeklyEl.innerHTML = `<span class="briefing__daily-text">${escapeHtml(weeklyData.content || "")}</span>`;
    } else {
      weeklyTimeEl.textContent = "";
      weeklyEl.innerHTML = '<div class="state-message">暂无周报</div>';
    }

    if (newsEl) {
      if (newsCountEl) newsCountEl.textContent = `${data.news_count || news.length}条`;
      if (news.length === 0) {
        newsEl.innerHTML = '<div class="state-message">暂无资讯</div>';
      } else {
        newsEl.innerHTML = news.map((n, index) => `
          <a class="news-item" href="${escapeHtml(n.url || "#")}" target="_blank" rel="noopener" style="animation-delay: ${index * 50}ms">
            <div class="news-item__meta">
              <span class="news-item__source">${escapeHtml(n.source || "")}</span>
              <span>·</span>
              <span>${escapeHtml(n.published_at ? _timeAgo(n.published_ts) : (n.time_ago || ""))}</span>
            </div>
            <div class="news-item__title">${escapeHtml(n.title || n.title_en || "")}</div>
          </a>`).join("");
      }
    }

    if (chart) chart.setNews(news);
  } catch (e) {
    if (briefingSkeleton) briefingSkeleton.style.display = 'none';
    if (briefingContent) briefingContent.style.display = 'block';
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    if (newsEl) newsEl.style.display = 'block';
    weeklyEl.innerHTML = '<div class="state-message">加载失败</div>';
    if (newsEl) newsEl.innerHTML = '<div class="state-message">加载失败</div>';
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

  polling.setSource("xauChart", xau);
  polling.setSource("auChart", au);
  chart.xauSource = xau;
  chart.auSource = au;
  await chart.load();
}

window.addEventListener("DOMContentLoaded", async () => {
  // Wire up card source selectors
  const srcXau = document.getElementById("src-xau");
  const srcAu = document.getElementById("src-au");
  if (srcXau) {
    srcXau.value = polling.getSource("xau");
    srcXau.addEventListener("change", () => polling.setSource("xau", srcXau.value));
  }
  if (srcAu) {
    srcAu.value = polling.getSource("au");
    srcAu.addEventListener("change", () => polling.setSource("au", srcAu.value));
  }

  chart = new GoldChart();

  // Chart source selectors
  const selXau = document.getElementById("sel-xau");
  const selAu = document.getElementById("sel-au");
  if (selXau) selXau.addEventListener("change", reloadChart);
  if (selAu) selAu.addEventListener("change", reloadChart);

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
  const btnBriefing = document.getElementById("btn-refresh-briefing");
  const debugStatus = document.getElementById("debug-status");
  if (btnBriefing) {
    btnBriefing.addEventListener("click", async () => {
      btnBriefing.disabled = true;
      btnBriefing.textContent = "⏳ 生成中...";
      if (debugStatus) debugStatus.textContent = "正在生成 AI 分析...";
      try {
        const res = await fetch("/api/briefings/trigger", { method: "POST" });
        const data = await res.json();
        const weekly = data.weekly;
        const weeklyEl = document.getElementById("weekly-content");
        const weeklyTimeEl = document.getElementById("weekly-time");
        if (weeklyEl) weeklyEl.innerHTML = `<span class="briefing__daily-text">${escapeHtml(weekly?.content || "")}</span>`;
        if (weeklyTimeEl) weeklyTimeEl.textContent = weekly?.time_range || "";
        if (debugStatus) debugStatus.textContent = "AI 分析已更新";
        showToast("AI 分析已更新", "info");
      } catch (e) {
        if (debugStatus) debugStatus.textContent = "生成失败";
        showToast("AI 分析生成失败: " + e.message, "error");
      } finally {
        btnBriefing.disabled = false;
        btnBriefing.textContent = "🧠 刷新AI分析";
      }
    });
  }

  await chart.load();
  chart.warmup();
});
