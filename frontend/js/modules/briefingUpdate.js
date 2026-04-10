/**
 * Briefing rendering module — stale-while-revalidate.
 *
 * Strategy:
 * - If content is already visible → show it immediately, refresh in background
 * - If content is NOT visible (first load, cold cache) → show skeleton while fetching
 *
 * Result: users NEVER see a blank page or spinner on repeat visits.
 */
import { escapeHtml } from "../utils/escape.js";

/** True once we have successfully rendered real content at least once. */
let _hasRendered = false;

function renderBriefing(text) {
  return escapeHtml(text || "").replace(
    /【(.+?)】/g,
    '<span class="section-label">【$1】</span>',
  );
}

function hasContent() {
  const bodyL1 = document.getElementById("body-l1");
  const bodyL2 = document.getElementById("body-l2");
  if (!bodyL1 || !bodyL2) return false;
  const l1 = bodyL1.textContent?.trim() || "";
  const l2 = bodyL2.textContent?.trim() || "";
  // "加载中..." is the skeleton placeholder — anything else is real content
  return (l1 && l1 !== "加载中...") || (l2 && l2 !== "加载中...");
}

function hideSkeleton() {
  const skeleton = document.getElementById("briefing-skeleton");
  if (skeleton) skeleton.style.display = "none";
}

function showContent() {
  const content = document.getElementById("briefing-content");
  if (content) content.style.display = "block";
}

function showSkeleton() {
  const skeleton = document.getElementById("briefing-skeleton");
  if (skeleton) skeleton.style.display = "flex";
  const weeklyContent = document.getElementById("briefing-content");
  if (weeklyContent) weeklyContent.style.display = "none";
}

function initSkeleton() {
  const weeklyContent = document.getElementById("briefing-content");
  const weeklySkeleton = document.getElementById("briefing-skeleton");
  if (weeklySkeleton) weeklySkeleton.style.display = "none";
  if (weeklyContent) weeklyContent.style.display = "block";

  const weeklyEl = document.getElementById("weekly-content");
  if (!weeklyEl) return;
  weeklyEl.innerHTML = `
    <div class="analysis-block analysis-block--l2" id="block-l2">
      <div class="analysis-block__body" id="body-l2"><div class="state-message">加载中...</div></div>
    </div>
    <div class="analysis-block analysis-block--l1" id="block-l1">
      <div class="analysis-block__body" id="body-l1"><div class="state-message">加载中...</div></div>
    </div>`;
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
  const firstLoad = !_hasRendered;

  if (firstLoad) {
    // Cold cache or first visit — show skeleton while waiting
    initSkeleton();
    showSkeleton();
  }
  // else: warm cache — existing content stays visible while we fetch fresh data

  fetch("/api/briefings/stream?days=3")
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((data) => {
      const weekly = data.weekly || {};
      const bodyL1 = document.getElementById("body-l1");
      const bodyL2 = document.getElementById("body-l2");
      if (bodyL1 && weekly.layer1) bodyL1.innerHTML = renderBriefing(weekly.layer1);
      if (bodyL2 && weekly.layer2) bodyL2.innerHTML = renderBriefing(weekly.layer2);
      hideSkeleton();
      showContent();
      _hasRendered = true;
    })
    .catch(() => {
      if (firstLoad) {
        hideSkeleton();
        showToast("AI 分析加载失败，请刷新重试", "error");
      }
      // On background refresh failure, silently keep showing stale content — no disruption
    });
}
