/**
 * Main app: price cards + dual gold chart + news.
 */

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

/**
 * Compute "X分钟前" / "X小时前" / "X天前" from a UTC Unix timestamp (seconds).
 * Computed live — never stale.
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
      // Escape HTML to prevent XSS
      const escape = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      // time_ago is computed live from published_ts — never stale
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
        <div class="news-dir">${label}</div>
      </a>
    `}).join("");

    const nowForDisplay = new Date();
    if (refreshTime) refreshTime.textContent = `更新于 ${nowForDisplay.toLocaleTimeString("zh-CN", {hour:"2-digit", minute:"2-digit"})}`;

    // Pass news to chart — published_ts is the canonical anchor
    if (chart) {
      chart.setNews(news);
    }

  } catch (e) {
    list.innerHTML = '<div class="news-loading">加载失败</div>';
  }
}

let briefings = [];

async function loadBriefings() {
  const list = document.getElementById("briefing-list-col");
  if (!list) return;
  try {
    const res = await fetch("/api/briefings");
    const data = await res.json();
    briefings = data.briefings || [];
    if (briefings.length === 0) {
      list.innerHTML = '<div class="briefing-empty">暂无简报，将于下一小时生成</div>';
      return;
    }
    list.innerHTML = briefings.map(b => `
      <div class="briefing-item">
        <div class="briefing-time">${b.time_range || b.generated_at}</div>
        <div class="briefing-content">${escapeHtml(b.content)}</div>
      </div>
    `).join("");
  } catch (e) {
    list.innerHTML = '<div class="briefing-empty">加载失败</div>';
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

window.addEventListener("DOMContentLoaded", async () => {
  chart = new GoldChart();
  loadBriefings();
  initControls();
  document.getElementById("refresh-briefing-btn")?.addEventListener("click", loadBriefings);
  await chart.load(currentDays);
  // Warm up all 3 windows in background (backend caches each for 5 min)
  chart.warmup();
  loadNews(currentDays);
  // Refresh news every 5 minutes
  setInterval(() => loadNews(currentDays), 5 * 60 * 1000);
});
