/**
 * Main app: price cards + dual gold chart + news.
 * Enhanced with skeleton loading, animations, and glass effects.
 */
import { GoldChart } from "./chart/GoldChart.js";

let chart = null;
let prices = {};
let hasInitialData = false;

/**
 * Animate a number change with a flash effect
 */
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

/**
 * Show toast notification
 */
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

/**
 * Update a price card with new data
 */
function updatePriceCard(symbol, data) {
  if (!data) return;

  // Hide skeleton, show real card
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

  // Animate price change
  animatePriceChange(priceEl, `${data.price} ${data.unit || ""}`);

  const hasChange = data.change != null && data.pct != null;
  if (hasChange) {
    const sign = data.change >= 0 ? "+" : "";
    const changeText = `${sign}${data.change} (${sign}${data.pct}%)`;
    animatePriceChange(changeEl, changeText);
    changeEl.className = `price-card__change price-card__change--${data.change >= 0 ? "up" : "down"}`;

    if (card) {
      card.classList.remove("price-card--up", "price-card--down");
      // Add animation class
      const animClass = data.change >= 0 ? "price-card--up" : "price-card--down";
      card.classList.add(animClass);
      // Remove animation class after animation completes
      setTimeout(() => {
        card.classList.remove(animClass);
      }, 600);
    }
  } else {
    changeEl.textContent = "";
    changeEl.className = "price-card__change";
    if (card) card.classList.remove("price-card--up", "price-card--down");
  }

  const hasOHLC = data.open != null && data.high != null && data.low != null;
  if (hasOHLC) {
    if (openEl) openEl.textContent = data.open;
    if (highEl) highEl.textContent = data.high;
    if (lowEl) lowEl.textContent = data.low;
  }

  hasInitialData = true;
}

/**
 * Handle price update from SSE or polling
 */
window.onPriceUpdate = function (data) {
  if (!data) return;
  prices = data;
  const el = document.getElementById("last-update");
  if (el) el.textContent = data.updated_at ? `更新于 ${data.updated_at}` : "";

  for (const sym of ["XAUUSD", "AU9999", "USDCNY"]) {
    if (data[sym]) updatePriceCard(sym, data[sym]);
  }
};

/**
 * Format timestamp to relative time
 */
function _timeAgo(tsSec) {
  if (!tsSec) return "未知";
  const diffMs = Date.now() - tsSec * 1000;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}小时前`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}天前`;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Load and display news list
 */
async function loadNews(days = 1) {
  const list = document.getElementById("briefing-news-list");
  const newsSkeleton = document.getElementById("news-skeleton");
  const refreshTime = document.getElementById("news-refresh-time");
  if (!list) return;

  try {
    const res = await fetch(`/api/news?days=${days}`);
    const data = await res.json();
    const news = data.news || [];

    // Hide skeleton, show list
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    list.style.display = 'block';

    if (news.length === 0) {
      list.innerHTML = '<div class="state-message">暂无资讯</div>';
      return;
    }

    list.innerHTML = news.map((item, index) => {
      const timeAgo = _timeAgo(item.published_ts);
      return `
      <a class="news-item" href="${escapeHtml(item.url)}" target="_blank" rel="noopener" style="animation-delay: ${index * 50}ms">
        <div class="news-item__meta">
          <span class="news-item__source">${escapeHtml(item.source)}</span>
          <span>·</span>
          <span>${timeAgo}</span>
        </div>
        <div class="news-item__title">${escapeHtml(item.title)}</div>
      </a>
    `}).join("");

    if (chart) {
      chart.setNews(news);
    }

  } catch (e) {
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    list.style.display = 'block';
    list.innerHTML = '<div class="state-message">加载失败</div>';
  }
}

/**
 * Load and display briefings
 */
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
    const res = await fetch("/api/briefings?days=7");
    const data = await res.json();
    const weeklyData = data.weekly;
    const news = data.news || [];

    // Hide skeletons, show content
    if (briefingSkeleton) briefingSkeleton.style.display = 'none';
    if (briefingContent) briefingContent.style.display = 'block';
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    if (newsEl) newsEl.style.display = 'block';

    // 左侧：近7日整体
    if (weeklyData) {
      weeklyTimeEl.textContent = weeklyData.time_range || "";
      weeklyEl.innerHTML = `<span class="briefing-daily-text">${escapeHtml(weeklyData.content || "")}</span>`;
    } else {
      weeklyTimeEl.textContent = "";
      weeklyEl.innerHTML = '<div class="state-message">暂无周报</div>';
    }

    // 右侧：新闻列表
    if (newsEl) {
      if (newsCountEl) {
        newsCountEl.textContent = `${data.news_count || news.length}条`;
      }
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

    if (chart) {
      chart.setNews(news);
    }

  } catch (e) {
    if (briefingSkeleton) briefingSkeleton.style.display = 'none';
    if (briefingContent) briefingContent.style.display = 'block';
    if (newsSkeleton) newsSkeleton.style.display = 'none';
    if (newsEl) newsEl.style.display = 'block';
    weeklyEl.innerHTML = '<div class="state-message">加载失败</div>';
    if (newsEl) newsEl.innerHTML = '<div class="state-message">加载失败</div>';
  }
}

/**
 * Initialize app on DOM ready
 */
window.addEventListener("DOMContentLoaded", async () => {
  chart = new GoldChart();

  // Bind chart data source switching
  const selXau = document.getElementById("sel-xau");
  const selAu = document.getElementById("sel-au");
  const legendXau = document.getElementById("legend-xau");

  const reloadChart = async () => {
    const xau = selXau ? selXau.value : "comex";
    const au = selAu ? selAu.value : "au9999";
    if (legendXau) {
      legendXau.textContent = xau === "binance" ? "XAUTUSDT (Binance)" : "COMEX GC00Y";
    }
    if (xau === "binance" && chart.xauSource !== "binance") {
      const loader = document.getElementById("chart-loader");
      if (loader) { loader.style.display = "flex"; loader.querySelector('span').textContent = "切换数据源中..."; }
      const r = await fetch(`/api/xau-source?source=${xau}`, { method: "POST" });
      const json = await r.json();
      console.log("[reloadChart] import result:", json);
      if (loader) loader.style.display = "none";
    }
    chart.xauSource = xau;
    chart.auSource = au;
    chart.loading = false;
    console.log("[reloadChart] calling load(), xauSource=" + chart.xauSource);
    await chart.load();
  };

  if (selXau) selXau.addEventListener("change", reloadChart);
  if (selAu) selAu.addEventListener("change", reloadChart);

  loadBriefings();
  await chart.load();
  chart.warmup();
});
