/**
 * Alert management: CRUD operations + triggered alert display.
 */

let _alertRules = [];

async function loadAlerts() {
  try {
    const res = await fetch("/api/alerts/");
    _alertRules = await res.json();
    renderAlertList();
  } catch (e) {
    console.warn("Load alerts error:", e);
  }
}

async function addAlert() {
  const symbol = document.getElementById("alert-symbol").value;
  const high = parseFloat(document.getElementById("alert-high").value) || null;
  const low = parseFloat(document.getElementById("alert-low").value) || null;

  if (!high && !low) {
    showToast("请至少填写一个价格阈值", "error");
    return;
  }

  try {
    const res = await fetch("/api/alerts/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, high_price: high, low_price: low, condition: "cross" }),
    });
    const result = await res.json();
    if (result.error) {
      showToast(result.error, "error");
      return;
    }
    showToast("预警已添加！", "success");
    document.getElementById("alert-high").value = "";
    document.getElementById("alert-low").value = "";
    await loadAlerts();
  } catch (e) {
    showToast("添加失败: " + e.message, "error");
  }
}

async function deleteAlert(ruleId) {
  try {
    await fetch(`/api/alerts/${ruleId}`, { method: "DELETE" });
    showToast("预警已删除", "success");
    await loadAlerts();
  } catch (e) {
    showToast("删除失败", "error");
  }
}

function renderAlertList() {
  const list = document.getElementById("alerts-list");
  const hint = document.getElementById("no-alerts-hint");

  if (!_alertRules || _alertRules.length === 0) {
    hint.style.display = "";
    list.querySelectorAll(".alert-item").forEach((el) => el.remove());
    return;
  }

  hint.style.display = "none";

  // Remove existing items (keep hint)
  list.querySelectorAll(".alert-item").forEach((el) => el.remove());

  _alertRules.forEach((rule) => {
    const item = document.createElement("div");
    item.className = "alert-item";
    item.innerHTML = `
      <div class="alert-item-info">
        <span class="alert-tag symbol">${rule.symbol}</span>
        ${rule.high_price ? `<span class="alert-tag high">↑ 高价 ${rule.high_price}</span>` : ""}
        ${rule.low_price ? `<span class="alert-tag low">↓ 低价 ${rule.low_price}</span>` : ""}
      </div>
      <button class="btn-delete" onclick="window._deleteAlert(${rule.id})">删除</button>
    `;
    list.appendChild(item);
  });
}

function renderTriggeredAlerts(alerts) {
  const badge = document.getElementById("alert-badge");
  if (!alerts || alerts.length === 0) {
    badge.style.display = "none";
    return;
  }
  badge.style.display = "block";
  badge.innerHTML = "🚨 " + alerts.map((a) => a.message).join("<br>🚨 ");
  showToast(alerts[0].message, "warning");
}

window._deleteAlert = deleteAlert;
window.loadAlerts = loadAlerts;
window.addAlert = addAlert;
window.renderTriggeredAlerts = renderTriggeredAlerts;

// Wire up button
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-add-alert");
  if (btn) btn.addEventListener("click", addAlert);
  loadAlerts();
});
