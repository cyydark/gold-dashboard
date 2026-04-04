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
      const dir = item.direction;
      const label = dir === "up" ? '<span class="news-tag up">📈 金价升</span>'
                   : dir === "down" ? '<span class="news-tag down">📉 金价降</span>'
                   : '<span class="news-tag neutral">📊 中性</span>';
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
        <div class="news-dir">${label}</div>
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
  const dailyEl = document.getElementById("daily-content");
  const hourlyEl = document.getElementById("hourly-list");
  const newsEl = document.getElementById("briefing-news-list");
  const dailyTimeEl = document.getElementById("daily-time");
  const sourceTimeEl = document.getElementById("source-time");
  if (!dailyEl || !hourlyEl) return;

  try {
    const res = await fetch("/api/briefings?limit=24");
    const data = await res.json();
    const briefings = data.briefings || [];

    if (briefings.length === 0) {
      dailyEl.innerHTML = '<div class="briefing-empty">暂无简报</div>';
      hourlyEl.innerHTML = '';
      return;
    }

    // 上一日整体：取最旧的那条（代表较早时段的分析，或当昨日看）
    const daily = briefings[briefings.length - 1];
    dailyTimeEl.textContent = daily.time_range || daily.generated_at || "";
    dailyEl.innerHTML = `<span class="briefing-daily-text">${escapeHtml(daily.content || "")}</span>`;

    // 最近12小时：最新往前数12条（跳过最旧的那条，避免与"上一日"重复）
    const hourly = briefings.slice(0, 12);
    hourlyEl.innerHTML = hourly.map(b => {
      const timeLabel = b.time_range
        ? b.time_range.split("~")[0] + "时"
        : (b.generated_at ? new Date(b.generated_at).toTimeString().slice(0,5) : "");
      return `
        <div class="hourly-item">
          <span class="hourly-time">${escapeHtml(timeLabel)}</span>
          <span class="hourly-text">${escapeHtml(b.content || "")}</span>
        </div>`;
    }).join("");

    // 右侧：直接展示 API 按最新简报时段过滤好的新闻
    if (newsEl) {
      const news = data.news || [];
      const latestBriefing = briefings[0];
      if (sourceTimeEl) {
        sourceTimeEl.textContent = latestBriefing && latestBriefing.time_range
          ? latestBriefing.time_range
          : "";
      }
      if (news.length === 0) {
        newsEl.innerHTML = '<div class="briefing-empty">暂无来源新闻</div>';
      } else {
        newsEl.innerHTML = news.slice(0, 8).map(n => `
          <div class="source-news-item">
            <div class="source-news-meta">
              <span class="source-news-source">${escapeHtml(n.source || "")}</span>
              <span>·</span>
              <span>${escapeHtml(n.published_at ? n.published_at.slice(11, 16) : (n.time_ago || ""))}</span>
            </div>
            <a class="source-news-title" href="${escapeHtml(n.url || "#")}" target="_blank" rel="noopener">
              ${escapeHtml(n.title || n.title_en || "")}
            </a>
          </div>`).join("");
      }
    }
  } catch (e) {
    dailyEl.innerHTML = '<div class="briefing-empty">加载失败</div>';
    hourlyEl.innerHTML = '';
    if (newsEl) newsEl.innerHTML = '<div class="briefing-empty">加载失败</div>';
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  chart = new GoldChart();
  loadBriefings();
  await chart.load();
  chart.warmup();
});
