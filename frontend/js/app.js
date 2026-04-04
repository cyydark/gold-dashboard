/**
 * Main app: price cards + gold chart + AI briefing.
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
      if (chart) chart.load(parseInt(btn.dataset.days));
    });
  });
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

async function loadBriefings() {
  const list = document.getElementById("briefing-list");
  if (!list) return;
  try {
    const res = await fetch("/api/briefings");
    const data = await res.json();
    const briefings = data.briefings || [];
    if (briefings.length === 0) {
      list.innerHTML = '<div class="briefing-empty">暂无简报，将于下一小时生成</div>';
      return;
    }
    list.innerHTML = briefings.map(b => `
      <div class="briefing-item">
        <div class="briefing-time">${escapeHtml(b.time_range || b.generated_at)}</div>
        <div class="briefing-content">${escapeHtml(b.content)}</div>
      </div>
    `).join("");
  } catch (e) {
    list.innerHTML = '<div class="briefing-empty">加载失败</div>';
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  chart = new GoldChart();
  initControls();
  loadBriefings().catch(() => {});
  await chart.load(1);
  chart.warmup();
});
