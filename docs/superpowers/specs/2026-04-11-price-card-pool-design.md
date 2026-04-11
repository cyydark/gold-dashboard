# 价格卡片共享池随机化设计

## 背景

三个价格卡片（XAUUSD、AU9999、USDCNY）共享一个颜色池（12色）和字体池（6字体），每次价格更新或用户切换数据源时，从池子抽取新值分配给卡片，旧值退回池子。所有卡片颜色唯一、字体唯一。

## 核心行为

| 触发时机 | 调用函数 | 动画 |
|---|---|---|
| 价格轮询更新 | `_refreshAll()` | ✅ 全部3张卡片闪光 |
| 用户切换数据源 | `_refreshOne(symbol)` | ✅ 该卡片闪光 |

每次触发：
1. 该卡片的旧颜色 + 旧字体 → 退回池子
2. 从当前剩余池子抽取新值分配
3. 触发动画并更新 DOM CSS 变量

## 池子管理

### 常量

```js
const _CARD_COLORS = [
  "#d4af37", "#fb923c", "#c084fc",
  "#34d399", "#38bdf8", "#fbbf24",
  "#f472b6", "#a78bfa", "#4ade80",
  "#fb7185", "#facc15", "#22d3ee",
];

const _CARD_FONTS = [
  "'Cormorant Garamond', serif",
  "'Playfair Display', serif",
  "'DM Sans', sans-serif",
  "'Space Grotesk', sans-serif",
  "'JetBrains Mono', monospace",
  "'IBM Plex Mono', monospace",
];
```

### 状态

```js
const _SYMBOLS = ["XAUUSD", "AU9999", "USDCNY"];

let _colorPool = shuffle([..._CARD_COLORS]);
let _fontPool  = shuffle([..._CARD_FONTS]);

let _cardColor = { XAUUSD: null, AU9999: null, USDCNY: null };
let _cardFont  = { XAUUSD: null, AU9999: null, USDCNY: null };
```

### 工具函数

**`_shuffle(arr)`** — Fisher-Yates 洗牌，返回新数组。

**`_deal(pool)`** — 弹出池子尾部值；池空时用原始 `_CARD_COLORS` / `_CARD_FONTS` 重新 shuffle 补充后再次弹出。

**`_return(pool, value)`** — 如果值非 null 且不在池中，推入池子尾部。

**`_refresh(symbol)`** — 退还旧值 → 抽取新值 → 触发动画 + 更新 DOM：
```js
function _refresh(symbol) {
  _return(_colorPool, _cardColor[symbol]);
  _return(_fontPool,  _cardFont[symbol]);
  _cardColor[symbol] = _deal(_colorPool);
  _cardFont[symbol]  = _deal(_fontPool);
  _apply(symbol);   // 更新 DOM + CSS 变量
}
```

**`_apply(symbol)`** — 更新 DOM 元素 CSS 变量并触发动画：
- 设置 `--card-accent` 和 `--card-font`
- 添加 `.price-card--switched` class 触发闪光
- 1.2s 后移除 class

## 公开函数

### `_refreshAll()`
三个卡片全部刷新，全部触发动画。用于价格轮询更新。

```js
function _refreshAll() {
  for (const sym of _SYMBOLS) {
    _refresh(sym);
  }
}
```

### `_refreshOne(symbol)`
单卡刷新，触发动画。用于用户切换数据源。

```js
function _refreshOne(symbol) {
  _refresh(symbol);
}
```

## 移除内容

- `SOURCE_COLORS` 常量及所有相关引用
- `_switchedAt` 状态变量
- `SWITCH_GRACE_MS` 常量
- `flashCardSource` 中的 `srcColor` 查找逻辑

## 文件变更

- `frontend/js/modules/priceUpdate.js` — 核心逻辑重写
