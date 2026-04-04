# gold-dashboard 5分钟图表重构设计

## 目标

移除时间范围切换按钮，图表固定显示最近 72 小时的 5 分钟 K 线数据，支持双轴 crosshair 交互。

## 数据源

| 数据集 | 数据源 | 颗粒度 | 最大条数 | 覆盖时长 |
|--------|--------|--------|----------|----------|
| XAU/USD | Binance XAUTUSDT K线 | 5 分钟 | ~1000 条 | ~3.5 天 |
| AU9999 | Sina au0 futures 5m | 5 分钟 | ~1023 条 | ~11 天 |

两者时间范围均覆盖最近 72 小时。

## 前端图表行为

### 时间范围
- `xMin = now - 72h`, `xMax = now`
- 不手动计算重叠，由 Chart.js 自动截取

### Y 轴
- XAU/USD: 右侧轴（USD/oz）
- AU9999: 左侧轴（CNY/g）

### Crosshair 交互
鼠标移动时：
1. 在 X 轴位置画垂直虚线（`rgba(148,163,184,0.5)`, `setLineDash([4,4])`），覆盖整个图表高度
2. 在金价曲线交点处用 Canvas 2D 绘制该点价格数值
3. 显示内容：
   - 时间：北京时间 + 美东时间（如 `04月04日 11:30 北京 | 04月03日 23:30 美东`）
   - XAU/USD：最近数据点价格
   - AU9999：最近数据点价格

### Emoji 新闻标注
代码注释（`/* ... */`），功能暂停，不删除。

### 加载
- 移除时间范围切换按钮
- 页面加载时直接请求 `/api/history/XAUUSD` + `/api/history/AU9999`
- `chart.load()` 无参数

## 数据流

```
页面加载
  └── chart.load() 发起 /api/history/XAUUSD + /api/history/AU9999
        ├── backend: fetch_xauusd_history(days=1) → Binance 5m klines
        └── backend: fetch_au9999_history(days=1) → Sina au0 5m
              └── 前端: Chart.js x轴自动限制到最近72h
                    └── Crosshair插件: 监听mousemove，Canvas绘制交点数值+时间
```

## 文件修改范围

| 文件 | 操作 |
|------|------|
| `frontend/js/chart.js` | 移除 xMin/xMax，新增 Crosshair 插件，注释 Emoji 插件 |
| `frontend/js/app.js` | `chart.load()` 无参数，warmup 清理 |
| `frontend/index.html` | 移除时间范围切换按钮 |

后端 API 保持不变。
