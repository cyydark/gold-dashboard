/**
 * Main app: price cards + dual gold chart + news.
 */

let chart = null;
let currentDays = 1;
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
  if (!priceEl) return;

  priceEl.textContent = `${data.price} ${data.unit || ""}`;
  const sign = data.change >= 0 ? "+" : "";
  changeEl.textContent = `${sign}${data.change} (${sign}${data.pct}%)`;
  changeEl.className = `card-change ${data.change >= 0 ? "up" : "down"}`;
  if (openEl) openEl.textContent = data.open;
  if (highEl) highEl.textContent = data.high;
  if (lowEl)  lowEl.textContent  = data.low;
  if (card) {
    card.classList.remove("up", "down");
    card.classList.add(data.change >= 0 ? "up" : "down");
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

function initControls() {
  document.querySelectorAll(".range-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("active")) return;
      document.querySelectorAll(".range-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentDays = parseInt(btn.dataset.days);
      if (chart) chart.load(currentDays);
      loadNews(currentDays);
    });
  });
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
      const dir = item.direction;
      const label = dir === "up" ? '<span class="news-tag up">📈 金价升</span>'
                   : dir === "down" ? '<span class="news-tag down">📉 金价降</span>'
                   : '<span class="news-tag neutral">📊 中性</span>';
      return `
      <a class="news-item" href="${item.url}" target="_blank" rel="noopener">
        <div class="news-meta">
          <span class="news-source">${item.source}</span>
          <span class="news-time">${item.time_ago}</span>
        </div>
        <div class="news-content">
          <span class="news-headline">${item.title}</span>
        </div>
        <div class="news-dir">${label}</div>
      </a>
    `}).join("");

    const now = new Date();
    if (refreshTime) refreshTime.textContent = `更新于 ${now.toLocaleTimeString("zh-CN", {hour:"2-digit", minute:"2-digit"})}`;

    // Pass news to chart if chart exists
    if (chart) {
      chart.setNews(news);
    }

  } catch (e) {
    list.innerHTML = '<div class="news-loading">加载失败</div>';
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  chart = new GoldChart();
  initControls();
  await chart.load(currentDays);
  loadNews(currentDays);
  // Refresh news every 5 minutes
  setInterval(() => loadNews(currentDays), 5 * 60 * 1000);
});
