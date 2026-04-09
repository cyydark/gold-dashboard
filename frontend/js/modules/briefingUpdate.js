/**
 * Briefing rendering module.
 */

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
    <div class="analysis-block analysis-block--l2" id="block-l2">
      <div class="analysis-block__header"><span class="analysis-block__icon">🎯</span><span class="analysis-block__title">金价预期</span></div>
      <div class="analysis-block__body" id="body-l2"><div class="state-message">加载中...</div></div>
    </div>
    <div class="analysis-block analysis-block--l1" id="block-l1">
      <div class="analysis-block__header"><span class="analysis-block__icon">📊</span><span class="analysis-block__title">分析结论</span></div>
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
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

export function loadBriefings() {
  initSkeleton();

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
    })
    .catch(() => {
      hideSkeleton();
      showToast("AI 分析加载失败，请刷新重试", "error");
    });
}
