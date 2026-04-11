/**
 * Price card update module.
 * Handles animation, color assignment, and DOM updates for the 3 price cards.
 * All cards share a single color pool (12 colors) and font pool (6 fonts).
 * On every refresh, old values are returned to the pool and fresh values are dealt.
 */
import { emit } from "../utils/eventBus.js";

const _CARD_FONTS = [
  "'Cormorant Garamond', serif",
  "'Playfair Display', serif",
  "'DM Sans', sans-serif",
  "'Space Grotesk', sans-serif",
  "'JetBrains Mono', monospace",
  "'IBM Plex Mono', monospace",
];

const _CARD_COLORS = [
  "#d4af37", "#fb923c", "#c084fc",
  "#34d399", "#38bdf8", "#fbbf24",
  "#f472b6", "#a78bfa", "#4ade80",
  "#fb7185", "#facc15", "#22d3ee",
];

const _SYMBOLS = ["XAUUSD", "AU9999", "USDCNY"];

// ── Pool state ─────────────────────────────────────────────────────────────────
// Available pool: starts full, values returned here when retired, drawn when dealt
let _colorPool = _shuffle([..._CARD_COLORS]);
let _fontPool  = _shuffle([..._CARD_FONTS]);

// Current assigned color/font per card
let _cardColor = { XAUUSD: null, AU9999: null, USDCNY: null };
let _cardFont  = { XAUUSD: null, AU9999: null, USDCNY: null };

// ── Pool operations ─────────────────────────────────────────────────────────────

/** Fisher-Yates shuffle, returns a new array */
function _shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** Return a value to the pool if it is not already there */
function _return(pool, value) {
  if (value !== null && !pool.includes(value)) pool.push(value);
}

/** Draw one value from pool (refills when empty) */
function _deal(pool) {
  if (pool.length === 0) {
    const fresh = pool === _colorPool
      ? _shuffle([..._CARD_COLORS])
      : _shuffle([..._CARD_FONTS]);
    pool.push(...fresh);
  }
  return pool.pop();
}

// ── Core refresh ────────────────────────────────────────────────────────────────

/**
 * Retire one card's old values, deal fresh assignments, and update DOM.
 */
function _refresh(symbol) {
  _return(_colorPool, _cardColor[symbol]);
  _return(_fontPool,  _cardFont[symbol]);
  _cardColor[symbol] = _deal(_colorPool);
  _cardFont[symbol]  = _deal(_fontPool);
  _apply(symbol);
}

// ── Public entry points ─────────────────────────────────────────────────────────

/** Refresh all 3 cards (called on every price poll update) */
export function _refreshAll() {
  for (const sym of _SYMBOLS) {
    _refresh(sym);
  }
}

/** Refresh one card (called on user source switch) */
export function _refreshOne(symbol) {
  _refresh(symbol);
}

// ── DOM update ──────────────────────────────────────────────────────────────────

/** Apply current card color/font to DOM and trigger flash animation */
function _apply(symbol) {
  const priceEl  = document.getElementById(`price-${symbol}`);
  const card     = document.getElementById(`card-${symbol}`);
  const openEl   = document.getElementById(`open-${symbol}`);
  const highEl   = document.getElementById(`high-${symbol}`);
  const lowEl    = document.getElementById(`low-${symbol}`);

  if (!priceEl) return;

  if (card) {
    card.style.setProperty("--card-accent", _cardColor[symbol]);
    card.style.setProperty("--card-font",   _cardFont[symbol]);
  }

  // Flash animation
  if (card) {
    card.classList.remove("price-card--switched");
    void card.offsetWidth; // force reflow
    card.classList.add("price-card--switched");
    setTimeout(() => card.classList.remove("price-card--switched"), 1200);
  }
}

// ── Legacy export compatibility ─────────────────────────────────────────────────

/** Animate a price number change with a brief scale effect */
function animatePriceChange(element, newValue) {
  if (!element) return;
  const oldValue = element.textContent;
  if (oldValue !== newValue) {
    element.style.transform = "scale(1.05)";
    element.style.transition = "transform 0.15s ease-out";
    setTimeout(() => {
      element.textContent = newValue;
      element.style.transform = "scale(1)";
    }, 50);
  }
}

/** Apply price data to DOM (no color/font changes) */
function applyPrice(symbol, data) {
  const priceEl  = document.getElementById(`price-${symbol}`);
  const changeEl  = document.getElementById(`change-${symbol}`);
  const card     = document.getElementById(`card-${symbol}`);
  const openEl   = document.getElementById(`open-${symbol}`);
  const highEl   = document.getElementById(`high-${symbol}`);
  const lowEl    = document.getElementById(`low-${symbol}`);
  if (!priceEl) return;

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
    if (lowEl)  lowEl.textContent  = data.low;
  }
}

/** Update a price card (reveals card, hides skeleton, applies price) */
export function updatePriceCard(symbol, data) {
  if (!data) return;
  const skeletonEl = document.getElementById(`skeleton-${symbol}`);
  const cardEl     = document.getElementById(`card-${symbol}`);
  if (skeletonEl && cardEl) {
    skeletonEl.style.display = "none";
    cardEl.style.display     = "block";
  }
  applyPrice(symbol, data);
}

/** Flash card when user changes source selector */
export function flashCardSource(symbol) {
  const card   = document.getElementById(`card-${symbol}`);
  const selMap = { XAUUSD: "src-xau", AU9999: "src-au", USDCNY: "src-fx" };
  const sel    = document.getElementById(selMap[symbol]);
  if (!card) return;

  // Source tag
  const oldTag = card.querySelector(".price-card__source-tag");
  if (oldTag) oldTag.remove();
  const srcName = sel ? sel.options[sel.selectedIndex].text : "";
  const tag = document.createElement("span");
  tag.className  = "price-card__source-tag";
  tag.textContent = srcName;
  card.appendChild(tag);

  // Retire old → deal fresh
  _refreshOne(symbol);

  // Remove tag after animation
  setTimeout(() => {
    if (tag.parentNode) tag.remove();
  }, 1200);

  emit("source:changed", {
    symbol,
    srcKey:  { XAUUSD: "xau", AU9999: "au", USDCNY: "fx" }[symbol],
    srcVal:  sel ? sel.value : "",
  });
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
        timeZone: "Asia/Shanghai",
      })} 北京时间`;
    }
  }

  _refreshAll();

  for (const sym of _SYMBOLS) {
    if (data[sym]) updatePriceCard(sym, data[sym]);
  }
}
