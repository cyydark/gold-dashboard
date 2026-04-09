/**
 * Briefing rendering module.
 */
import { emit } from "../utils/eventBus.js";

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderBriefing(text) {
  return escapeHtml(text || "").replace(/【(.+?)】/g, '<span class="section-label">【$1】</span>');
}

function hideSkeleton() {
  const skeleton = document.getElementById("briefing-skeleton");
  if (skeleton) skeleton.style.display = 'none';
}

function initSkeleton() {
  const weeklyContent = document.getElementById("briefing-content");
  const weeklySkeleton = document.getElementById("briefing-skeleton");
  if (weeklySkeleton) weeklySkeleton.style.display = 'none';
  if (weeklyContent) weeklyContent.style.display = 'block';

  const weeklyEl = document.getElementById("weekly-content");
  if (!weeklyEl) return;
  weeklyEl.innerHTML = `
    <div class="analysis-block analysis-block--l3" id="block-l3">
      <div class="analysis-block__header"><span class="analysis-block__icon">🎯</span><span class="analysis-block__title">金价预期</span></div>
      <div class="analysis-block__body" id="body-l3"><div class="state-message">加载中...</div></div>
    </div>
    <div class="analysis-block analysis-block--l12" id="block-l12">
      <div class="analysis-block__header"><span class="analysis-block__icon">📊</span><span class="analysis-block__title">分析结论</span></div>
      <div class="analysis-block__body" id="body-l12"><div class="state-message">加载中...</div></div>
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
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

export function loadBriefings() {
  const es = new EventSource("/api/briefings/stream?days=3");
  initSkeleton();

  let reconnectCount = 0;
  const MAX_RECONNECT = 3;
  const texts = { l12: "", l3: "" };
  const bodies = {
    l12: document.getElementById("body-l12"),
    l3: document.getElementById("body-l3"),
  };

  es.addEventListener("cached", (e) => {
    const data = JSON.parse(e.data);
    if (data.blocks) {
      if (bodies.l12 && data.blocks.l12) bodies.l12.innerHTML = renderBriefing(data.blocks.l12);
      if (bodies.l3 && data.blocks.l3) bodies.l3.innerHTML = renderBriefing(data.blocks.l3);
    }
    hideSkeleton();
    es.close();
  });

  es.addEventListener("token", (e) => {
    const { block, chunk } = JSON.parse(e.data);
    if (!bodies[block]) return;
    texts[block] += chunk;
    bodies[block].innerHTML = renderBriefing(texts[block]);
    hideSkeleton();
  });

  es.addEventListener("done", () => {
    hideSkeleton();
    es.close();
  });

  es.onerror = () => {
    reconnectCount++;
    if (reconnectCount >= MAX_RECONNECT) {
      es.close();
      hideSkeleton();
      if (texts.l12 && bodies.l12) bodies.l12.innerHTML = renderBriefing(texts.l12);
      if (texts.l3 && bodies.l3) bodies.l3.innerHTML = renderBriefing(texts.l3);
      if (!texts.l12 && !texts.l3) showToast("AI 分析加载失败，请刷新重试", "error");
    }
  };
}
