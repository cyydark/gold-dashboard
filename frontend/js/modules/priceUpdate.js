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

// Symbols whose source was just switched — color/font deferred until new data arrives
let _pendingSwitch = new Set();

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

/** Draw one value from pool, excluding current (ensures fresh value each time) */
function _deal(pool, current) {
  // Filter out the current value so we always get something different
  const candidates = pool.filter(v => v !== current);
  const source = candidates.length > 0 ? candidates : pool;
  const picked = source[Math.floor(Math.random() * source.length)];
  // Remove picked from pool so it can't be dealt to another card this round
  const idx = pool.indexOf(picked);
  if (idx !== -1) pool.splice(idx, 1);
  return picked;
}

/** Restore a value to the pool if it is not already present */
function _returnTo(pool, value) {
  if (value !== null && !pool.includes(value)) pool.push(value);
}

// ── Public entry points ─────────────────────────────────────────────────────────

/**
 * Randomize and apply color/font for one card — WITH animation.
 * Called on user source switch.
 */
export function _refreshOne(symbol) {
  const oldColor = _cardColor[symbol];
  const oldFont  = _cardFont[symbol];

  _cardColor[symbol] = _deal(_colorPool, oldColor);
  _cardFont[symbol]  = _deal(_fontPool,  oldFont);

  _returnTo(_colorPool, oldColor);
  _returnTo(_fontPool,  oldFont);

  _apply(symbol);
}

/**
 * Randomize and assign color/font for ALL cards ONCE — used at init.
 * NO animation, no price data.
 */
export function initCardAppearance() {
  for (const sym of _SYMBOLS) {
    const oldColor = _cardColor[sym];
    const oldFont  = _cardFont[sym];

    _cardColor[sym] = _deal(_colorPool, oldColor);
    _cardFont[sym]  = _deal(_fontPool,  oldFont);

    _returnTo(_colorPool, oldColor);
    _returnTo(_fontPool,  oldFont);

    const card = document.getElementById(`card-${sym}`);
    if (card) {
      card.style.setProperty("--card-accent", _cardColor[sym]);
      card.style.setProperty("--card-font",   _cardFont[sym]);
    }
  }
}

// ── DOM update ──────────────────────────────────────────────────────────────────

/**
 * Apply current card color/font to DOM.
 */
function _apply(symbol) {
  const card = document.getElementById(`card-${symbol}`);
  if (!card) return;

  card.style.setProperty("--card-accent", _cardColor[symbol]);
  card.style.setProperty("--card-font",   _cardFont[symbol]);
}

// ── Legacy export compatibility ─────────────────────────────────────────────────

/** Pending timeout IDs per element — used to cancel in-flight animations */
const _pendingTimeouts = new WeakMap();

/** Animate a price number change with a brief scale effect */
function animatePriceChange(element, newValue) {
  if (!element) return;
  const oldValue = element.textContent;
  if (oldValue !== newValue) {
    // Cancel any in-flight animation so a later timeout can't overwrite with stale text
    const existing = _pendingTimeouts.get(element);
    if (existing != null) clearTimeout(existing);

    element.style.transform = "scale(1.05)";
    element.style.transition = "transform 0.15s ease-out";
    const tid = setTimeout(() => {
      element.textContent = newValue;
      element.style.transform = "scale(1)";
      _pendingTimeouts.delete(element);
    }, 50);
    _pendingTimeouts.set(element, tid);
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
  } else {
    if (changeEl) {
      changeEl.textContent = "";
      changeEl.className = "price-card__change";
    }
  }

  if (card) {
    card.classList.remove("price-card--up", "price-card--down");
    const animClass = data.change != null ? (data.change >= 0 ? "price-card--up" : "price-card--down") : null;
    if (animClass) {
      card.classList.add(animClass);
      setTimeout(() => card.classList.remove(animClass), 600);
    }
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

  // Mark as pending — color/font change deferred until new data arrives
  _pendingSwitch.add(symbol);

  // Remove tag after animation (CSS source-label-pop runs 1.5s)
  setTimeout(() => {
    if (tag.parentNode) tag.remove();
  }, 1500);

  emit("source:changed", {
    symbol,
    srcKey:  { XAUUSD: "xau", AU9999: "au", USDCNY: "fx" }[symbol],
    srcVal:  sel ? sel.value : "",
  });
}

/** Update the "last-update" timestamp label */
function _updateTimestamp(data) {
  const el = document.getElementById("last-update");
  if (!el) return;
  const ts = data.XAUUSD?.ts || data.AU9999?.ts || data.USDCNY?.ts;
  if (ts) {
    const d = new Date(ts * 1000);
    el.textContent = `更新于 ${d.toLocaleTimeString("zh-CN", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      timeZone: "Asia/Shanghai",
    })} 北京时间`;
  }
}

/** Handle price update events from EventBus */
export function onPriceUpdate(data) {
  if (!data) return;
  _updateTimestamp(data);

  // Symbols with fresh data this poll
  const pending = _SYMBOLS.filter(sym => data[sym]);

  // For symbols whose source was just switched: apply new color/font BEFORE price data
  const toRefresh = pending.filter(sym => _pendingSwitch.has(sym));
  for (const sym of toRefresh) {
    _refreshOne(sym);
    _pendingSwitch.delete(sym);
  }

  // Flush price updates in a single frame for synchronized flash
  const remaining = pending.filter(sym => !toRefresh.includes(sym));
  if (remaining.length > 0 || toRefresh.length > 0) {
    requestAnimationFrame(() => {
      for (const sym of toRefresh) updatePriceCard(sym, data[sym]);
      for (const sym of remaining)  updatePriceCard(sym, data[sym]);
    });
  }
}
