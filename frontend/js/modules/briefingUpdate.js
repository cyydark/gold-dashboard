/**
 * Briefing rendering module.
 * Pattern: fetch → render → done. PollingManager calls this every 15min.
 */
import { escapeHtml } from "../utils/escape.js";

function renderBriefing(text) {
  return escapeHtml(text || "").replace(
    /【(.+?)】/g,
    '<span class="section-label">【$1】</span>',
  );
}

export function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

export function loadBriefings() {
  fetch("/api/briefings/stream?days=3")
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((data) => {
      const weekly = data.weekly || {};

      const skeleton = document.getElementById("briefing__skeleton");
      const content = document.getElementById("briefing-content");
      const weeklyEl = document.getElementById("briefing-content-body");
      if (!weeklyEl) return;

      // Render L2 (金价预期) then L1 (分析结论)
      weeklyEl.innerHTML = `
        <div class="briefing-block briefing-block--l2" id="briefing-block-l2">
          <div class="briefing-block__body" id="briefing-body-l2">${
            weekly.layer2 ? renderBriefing(weekly.layer2) : ""
          }</div>
        </div>
        <div class="briefing-block briefing-block--l1" id="briefing-block-l1">
          <div class="briefing-block__body" id="briefing-body-l1">${
            weekly.layer1 ? renderBriefing(weekly.layer1) : ""
          }</div>
        </div>`;

      // Switch: hide skeleton, show content
      if (skeleton) skeleton.style.display = "none";
      if (content) content.style.display = "block";

      // Update analysis time
      const periodEl = document.getElementById("briefing__period");
      if (periodEl && weekly.generatedAt) {
        periodEl.textContent = weekly.generatedAt;
      }
    })
    .catch(() => {
      showToast("AI 分析加载失败，请刷新重试", "error");
    });
}
