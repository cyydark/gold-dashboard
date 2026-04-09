/**
 * News rendering module.
 */
import { on } from "../utils/eventBus.js";

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function timeAgo(tsSec) {
  if (!tsSec) return "未知";
  const diffMs = Date.now() - tsSec * 1000;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}小时前`;
  return `${Math.floor(diffHr / 24)}天前`;
}

function bjTime(tsSec) {
  if (!tsSec) return "";
  const d = new Date(tsSec * 1000);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day} ${h}:${min} 北京`;
}

export function renderNews(news) {
  const newsEl = document.getElementById("briefing-news-list");
  const newsSkeleton = document.getElementById("news-skeleton");
  if (!newsEl) return;
  if (newsSkeleton) newsSkeleton.style.display = 'none';
  newsEl.style.display = 'block';

  if (!news || news.length === 0) {
    newsEl.innerHTML = '<div class="state-message">暂无资讯</div>';
    return;
  }

  newsEl.innerHTML = news.map((n, index) => `
    <a class="news-item" href="${escapeHtml(n.url || "#")}" target="_blank" rel="noopener"
       style="animation-delay: ${index * 50}ms">
      <div class="news-item__meta">
        <span class="news-item__source">${escapeHtml(n.source || "")}</span>
        <span>·</span>
        <span title="${escapeHtml(bjTime(n.published_ts))}">${escapeHtml(timeAgo(n.published_ts))}</span>
      </div>
      <div class="news-item__title">${escapeHtml(n.title || n.title_en || "")}</div>
    </a>`).join("");

  // Notify chart of news update
  if (window.__goldChart) window.__goldChart.setNews(news);
}

export async function loadNews(days = 3) {
  try {
    const res = await fetch(`/api/news?days=${days}`);
    if (!res.ok) throw new Error(`news API ${res.status}`);
    const data = await res.json();
    renderNews(data.news || data.data || []);
  } catch (err) {
    console.error("loadNews failed:", err);
  }
}
