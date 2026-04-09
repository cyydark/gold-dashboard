/**
 * Price card update module.
 * Handles animation, color assignment, and DOM updates for the 3 price cards.
 */
import { emit } from "../utils/eventBus.js";

// Distinct fonts — one per symbol, guaranteed unique
const _CARD_FONTS = [
  "'Cormorant Garamond', serif",
  "'Playfair Display', serif",
  "'DM Sans', sans-serif",
  "'Space Grotesk', sans-serif",
  "'JetBrains Mono', monospace",
  "'IBM Plex Mono', monospace",
];

// Color palette — distinct per symbol
const _CARD_COLORS = [
  "#d4af37", "#fb923c", "#c084fc",
  "#34d399", "#38bdf8", "#fbbf24",
  "#f472b6", "#a78bfa", "#4ade80",
  "#fb7185", "#facc15", "#22d3ee",
];

// Source → price color
const SOURCE_COLORS = {
  comex:     "#d4af37",
  binance:   "#fb923c",
  sina:      "#c084fc",
  au9999:    "#34d399",
  eastmoney: "#38bdf8",
  yfinance:  "#fbbf24",
  sina_au0:  "#fb923c",
};

// Fisher-Yates shuffle
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Assign a distinct value to each of the 3 symbols — shuffle pool on first call
const _fontAssign  = { value: null };
const _colorAssign = { value: null };

function _assign(symbol, pool, stateRef) {
  if (!stateRef.value) {
    const shuffled = shuffle(pool);
    stateRef.value = { XAUUSD: shuffled[0], AU9999: shuffled[1], USDCNY: shuffled[2] };
  }
  return stateRef.value[symbol];
}

/** Animate a price number change with a brief scale effect */
function animatePriceChange(element, newValue) {
  if (!element) return;
  const oldValue = element.textContent;
  if (oldValue !== newValue) {
    element.style.transform = 'scale(1.05)';
    element.style.transition = 'transform 0.15s ease-out';
    setTimeout(() => {
      element.textContent = newValue;
      element.style.transform = 'scale(1)';
    }, 50);
  }
}

/** Apply a price update to DOM */
function applyPrice(symbol, data) {
  const priceEl = document.getElementById(`price-${symbol}`);
  const changeEl = document.getElementById(`change-${symbol}`);
  const card = document.getElementById(`card-${symbol}`);
  const openEl = document.getElementById(`open-${symbol}`);
  const highEl = document.getElementById(`high-${symbol}`);
  const lowEl = document.getElementById(`low-${symbol}`);
  if (!priceEl) return;

  const srcKeyMap = { XAUUSD: "xau", AU9999: "au", USDCNY: "fx" };
  const sel = document.getElementById(`src-${srcKeyMap[symbol]}`);
  const srcVal = sel ? sel.value : "";

  const color = _assign(symbol, _CARD_COLORS, _colorAssign);
  const font  = _assign(symbol, _CARD_FONTS,   _fontAssign);
  priceEl.setAttribute("data-source", srcVal);
  priceEl.style.color = color;
  priceEl.style.fontFamily = font;
  changeEl.setAttribute("data-source", srcVal);
  changeEl.style.fontFamily = font;

  animatePriceChange(priceEl, `${data.price} ${data.unit || ""}`);

  const hasChange = data.change != null && data.pct != null;
  if (hasChange) {
    const sign = data.change >= 0 ? "+" : "";
    const changeText = `${sign}${data.change} (${sign}${data.pct}%)`;
    animatePriceChange(changeEl, changeText);
    changeEl.className = `price-card__change price-card__change--${data.change >= 0 ? "up" : "down"}`;
    if (card) {
      card.classList.remove("price-card--up", "price-card--down");
      const animClass = data.change >= 0 ? "price-card--up" : "price-card--down";
      card.classList.add(animClass);
      setTimeout(() => card.classList.remove(animClass), 600);
    }
  } else {
    changeEl.textContent = "";
    changeEl.className = "price-card__change";
    if (card) card.classList.remove("price-card--up", "price-card--down");
  }

  if (data.open != null && data.high != null && data.low != null) {
    if (openEl) openEl.textContent = data.open;
    if (highEl) highEl.textContent = data.high;
    if (lowEl) lowEl.textContent = data.low;
  }
}

/** Update a price card (reveals card, hides skeleton, applies price) */
export function updatePriceCard(symbol, data) {
  if (!data) return;
  const skeletonEl = document.getElementById(`skeleton-${symbol}`);
  const cardEl = document.getElementById(`card-${symbol}`);
  if (skeletonEl && cardEl) {
    skeletonEl.style.display = 'none';
    cardEl.style.display = 'block';
  }
  applyPrice(symbol, data);
}

/** Flash card when user changes source selector */
export function flashCardSource(symbol) {
  const card = document.getElementById(`card-${symbol}`);
  if (!card) return;

  const selMap  = { XAUUSD: "src-xau", AU9999: "src-au", USDCNY: "src-fx" };
  const sel = document.getElementById(selMap[symbol]);
  const srcVal = sel ? sel.value : "";
  const srcColor = SOURCE_COLORS[srcVal] || "#d4af37";
  const priceEl = document.getElementById(`price-${symbol}`);

  const oldTag = card.querySelector(".price-card__source-tag");
  if (oldTag) oldTag.remove();

  card.classList.remove("price-card--switched");
  void card.offsetWidth;
  card.classList.add("price-card--switched");

  if (priceEl) {
    priceEl.style.color = srcColor;
    priceEl.setAttribute("data-source", srcVal);
  }

  const srcName = sel ? sel.options[sel.selectedIndex].text : "";
  const tag = document.createElement("span");
  tag.className = "price-card__source-tag";
  tag.textContent = srcName;
  card.appendChild(tag);

  setTimeout(() => {
    card.classList.remove("price-card--switched");
    if (tag.parentNode) tag.remove();
  }, 1200);

  emit("source:changed", { symbol, srcKey: { XAUUSD: "xau", AU9999: "au", USDCNY: "fx" }[symbol], srcVal });
}

/** Handle price update events from EventBus */
export function onPriceUpdate(data) {
  if (!data) return;
  const el = document.getElementById("last-update");
  if (el) {
    const ts = data.XAUUSD?.ts || data.AU9999?.ts || data.USDCNY?.ts;
    if (ts) {
      const d = new Date(ts * 1000);
      el.textContent = `更新于 ${d.toLocaleTimeString("zh-CN", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        timeZone: "Asia/Shanghai"
      })} 北京时间`;
    }
  }
  for (const sym of ["XAUUSD", "AU9999", "USDCNY"]) {
    if (data[sym]) updatePriceCard(sym, data[sym]);
  }
}
