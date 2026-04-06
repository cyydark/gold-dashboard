/**
 * Main app: price cards + dual gold chart + news.
 */
import { GoldChart } from "./chart/GoldChart.js";

let chart = null;
let prices = {};

function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
window.showToast = showToast;

function updatePriceCard(symbol, data) {
  if (!data) return;
  const priceEl  = document.getElementById(`price-${symbol}`);
  const changeEl = document.getElementById(`change-${symbol}`);
  const card     = document.getElementById(`card-${symbol}`);
  const openEl   = document.getElementById(`open-${symbol}`);
  const highEl   = document.getElementById(`high-${symbol}`);
  const lowEl    = document.getElementById(`low-${symbol}`);
  const ohlcEl   = document.getElementById(`ohlc-${symbol}`);
  if (!priceEl) return;

  priceEl.textContent = `${data.price} ${data.unit || ""}`;
  const hasChange = data.change != null && data.pct != null;
  if (hasChange) {
    const sign = data.change >= 0 ? "+" : "";
    changeEl.textContent = `${sign}${data.change} (${sign}${data.pct}%)`;
    changeEl.className = `card-change ${data.change >= 0 ? "up" : "down"}`;
    if (card) {
      card.classList.remove("up", "down");
      card.classList.add(data.change >= 0 ? "up" : "down");
    }
  } else {
    changeEl.textContent = "";
    changeEl.className = "card-change";
    if (card) card.classList.remove("up", "down");
  }

  const hasOHLC = data.open != null && data.high != null && data.low != null;
  if (ohlcEl) ohlcEl.style.display = hasOHLC ? "" : "none";
  if (hasOHLC) {
    if (openEl) openEl.textContent = data.open;
    if (highEl) highEl.textContent = data.high;
    if (lowEl)  lowEl.textContent  = data.low;
  }
}

window.onPriceUpdate = function (data) {
  if (!data) return;
  prices = data;
  const el = document.getElementById("last-update");
  if (el) el.textContent = data.updated_at ? `更新于 ${data.updated_at}` : "";
  for (const sym of ["XAUUSD", "AU9999", "USDCNY"]) {
    if (data[sym]) updatePriceCard(sym, data[sym]);
  }
};

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

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

async function loadNews(days = 1) {
  const list = document.getElementById("news-list");
  const refreshTime = document.getElementById("news-refresh-time");
  if (!list) return;

  try {
    const res = await fetch(`/api/news?days=${days}`);
    const data = await res.json();
    const news = data.news || [];

    if (news.length === 0) {
      list.innerHTML = '<div class="news-loading">暂无资讯</div>';
      return;
    }

    list.innerHTML = news.map(item => {
      const escape = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      const timeAgo = _timeAgo(item.published_ts);
      return `
      <a class="news-item" href="${escape(item.url)}" target="_blank" rel="noopener">
        <div class="news-meta">
          <span class="news-source">${escape(item.source)}</span>
          <span class="news-time">${timeAgo}</span>
        </div>
        <div class="news-content">
          <span class="news-headline">${escape(item.title)}</span>
        </div>
      </a>
    `}).join("");

    if (refreshTime) {
      const now = new Date();
      refreshTime.textContent = `更新于 ${now.toLocaleTimeString("zh-CN", {hour:"2-digit", minute:"2-digit"})}`;
    }

    if (chart) {
      chart.setNews(news);
    }

  } catch (e) {
    list.innerHTML = '<div class="news-loading">加载失败</div>';
  }
}

async function loadBriefings() {
  const weeklyEl = document.getElementById("weekly-content");
  const newsEl = document.getElementById("briefing-news-list");
  const weeklyTimeEl = document.getElementById("weekly-time");
  const newsCountEl = document.getElementById("news-count");
  if (!weeklyEl) return;

  try {
    const res = await fetch("/api/briefings?days=7");
    const data = await res.json();
    const weeklyData = data.weekly;
    const news = data.news || [];

    // 左侧：近7日整体
    if (weeklyData) {
      weeklyTimeEl.textContent = weeklyData.time_range || "";
      weeklyEl.innerHTML = `<span class="briefing-daily-text">${escapeHtml(weeklyData.content || "")}</span>`;
    } else {
      weeklyTimeEl.textContent = "";
      weeklyEl.innerHTML = '<span class="briefing-empty">暂无周报</span>';
    }

    // 右侧：新闻列表
    if (newsEl) {
      if (newsCountEl) {
        newsCountEl.textContent = `${data.news_count || news.length}条`;
      }
      if (news.length === 0) {
        newsEl.innerHTML = '<div class="briefing-empty">暂无资讯</div>';
      } else {
        newsEl.innerHTML = news.map(n => `
          <div class="source-news-item">
            <div class="source-news-meta">
              <span class="source-news-source">${escapeHtml(n.source || "")}</span>
              <span>·</span>
              <span>${escapeHtml(n.published_at ? _timeAgo(n.published_ts) : (n.time_ago || ""))}</span>
            </div>
            <a class="source-news-title" href="${escapeHtml(n.url || "#")}" target="_blank" rel="noopener">
              ${escapeHtml(n.title || n.title_en || "")}
            </a>
          </div>`).join("");
      }
    }

    if (chart) {
      chart.setNews(news);
    }
  } catch (e) {
    weeklyEl.innerHTML = '<div class="briefing-empty">加载失败</div>';
    if (newsEl) newsEl.innerHTML = '<div class="briefing-empty">加载失败</div>';
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  chart = new GoldChart();

  // 绑定图表数据源切换
  const selXau = document.getElementById("sel-xau");
  const selAu  = document.getElementById("sel-au");
  const legendXau = document.getElementById("legend-xau");

  const reloadChart = async () => {
    const xau = selXau ? selXau.value : "comex";
    const au  = selAu  ? selAu.value  : "au9999";
    if (legendXau) {
      legendXau.textContent = xau === "binance" ? "XAUTUSDT (Binance)" : "COMEX GC00Y";
    }
    if (xau === "binance" && chart.xauSource !== "binance") {
      const loader = document.getElementById("chart-loader");
      if (loader) { loader.style.display = "block"; loader.textContent = "切换数据源中..."; }
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
  if (selAu)  selAu.addEventListener("change", reloadChart);

  loadBriefings();
  await chart.load();
  chart.warmup();
});
