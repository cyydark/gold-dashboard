/**
 * Technical indicators display with plain explanations.
 */

/** Signal messages in plain Chinese */
const RSI_SIGNALS = {
  overbought: (v) =>
    `⚠️ RSI=${v} 超过70，属于「超买区」—— 涨势过猛，可能随时回调，注意风险`,
  oversold: (v) =>
    `🟢 RSI=${v} 低于30，属于「超卖区」—— 跌势过大，可能出现反弹机会`,
  neutral: (v) =>
    `RSI=${v} 处于中性区间（30~70），多空力量相对均衡`,
};

const MA_SIGNALS = {
  bullish: "📈 短期 > 中期 > 长期均线，形成「多头排列」，上涨趋势健康",
  bearish: "📉 短期 < 中期 < 长期均线，形成「空头排列」，下跌趋势持续",
  neutral: "均线纠缠，暂无明确趋势方向",
};

function rsiSignal(rsi) {
  if (rsi === null || rsi === undefined) return null;
  if (rsi > 70) return RSI_SIGNALS.overbought(rsi);
  if (rsi < 30) return RSI_SIGNALS.oversold(rsi);
  return RSI_SIGNALS.neutral(rsi);
}

function maSignal(ma5, ma20, ma60) {
  if (!ma5 || !ma20 || !ma60) return null;
  if (ma5 > ma20 && ma20 > ma60) return MA_SIGNALS.bullish;
  if (ma5 < ma20 && ma20 < ma60) return MA_SIGNALS.bearish;
  return MA_SIGNALS.neutral;
}

function renderIndicators(data) {
  const container = document.getElementById("indicators-content");
  if (!data || data.error) {
    container.innerHTML = '<p class="hint">暂无数据</p>';
    return;
  }

  const { ma5, ma10, ma20, ma60, rsi, macd, macd_signal, macd_hist, signal } = data;
  const maSig = maSignal(ma5, ma20, ma60);
  const rsiSig = rsiSignal(rsi);

  const rsiClass = rsi > 70 ? "red" : rsi < 30 ? "green" : "";
  const macdClass = (macd_hist > 0) ? "green" : "red";

  container.innerHTML = `
    <div class="ind-grid">
      <div class="ind-item">
        <div class="ind-label">MA5（5日均线）</div>
        <div class="ind-value">${ma5 ?? "--"}</div>
      </div>
      <div class="ind-item">
        <div class="ind-label">MA10（10日均线）</div>
        <div class="ind-value">${ma10 ?? "--"}</div>
      </div>
      <div class="ind-item">
        <div class="ind-label">MA20（20日均线）</div>
        <div class="ind-value">${ma20 ?? "--"}</div>
      </div>
      <div class="ind-item">
        <div class="ind-label">MA60（60日均线）</div>
        <div class="ind-value">${ma60 ?? "--"}</div>
      </div>
      <div class="ind-item">
        <div class="ind-label">RSI（14日）</div>
        <div class="ind-value ${rsiClass}">${rsi ?? "--"}</div>
      </div>
      <div class="ind-item">
        <div class="ind-label">MACD</div>
        <div class="ind-value ${macdClass}">${macd ?? "--"}</div>
      </div>
      <div class="ind-item">
        <div class="ind-label">MACD Signal</div>
        <div class="ind-value">${macd_signal ?? "--"}</div>
      </div>
      <div class="ind-item">
        <div class="ind-label">MACD 柱</div>
        <div class="ind-value ${macdClass}">${macd_hist != null ? (macd_hist > 0 ? "红柱+" + macd_hist : "绿柱" + macd_hist) : "--"}</div>
      </div>
    </div>
    ${signal ? `<div class="ind-signal">${signal}</div>` : ""}
  `;
}

async function loadIndicators(symbol, days) {
  try {
    const res = await fetch(`/api/indicators/${symbol}?days=${days}`);
    const data = await res.json();
    renderIndicators(data);
  } catch (e) {
    console.warn("Indicators load error:", e);
  }
}

window.loadIndicators = loadIndicators;
