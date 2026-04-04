# 近1小时新闻 — 实现记录

## 实现结果

**最终实现：后端过滤 + 前端展示**

### API 接口

`GET /api/briefings` 返回：

```json
{
  "briefings": [...],
  "news": [...],           // 近1小时新闻（后端按 published_at 过滤）
  "time_window": "15:23~16:23"
}
```

`POST /api/news/refresh` — 手动抓取新闻并入库

### 关键代码

**backend/data/db.py** — `get_news_last_hours()`：

```python
async def get_news_last_hours(hours: int = 1, limit: int = 20) -> list[dict]:
    """Fetch news published within the last N hours (Beijing time)."""
    from backend.data.sources.international import BEIJING_TZ
    now = datetime.now(BEIJING_TZ)
    cutoff = (now - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT title, title_en, source, url, direction, time_ago, published_at, fetched_at "
            "FROM news_items WHERE published_at >= ? ORDER BY published_at DESC LIMIT ?",
            (cutoff, limit),
        )
        return [dict(r) for r in await rows.fetchall()]
```

**backend/routers/price.py** — `/api/briefings`：

```python
@router.get("/briefings")
async def get_briefings(limit: int = 24):
    from backend.data.db import get_recent_briefings, get_news_last_hours
    from backend.data.sources.international import BEIJING_TZ
    from datetime import datetime
    briefings = await get_recent_briefings(limit)
    news = await get_news_last_hours(hours=1, limit=20)
    now = datetime.now(BEIJING_TZ)
    one_hour_ago = now - timedelta(hours=1)
    time_window = f"{one_hour_ago.strftime('%H:%M')}~{now.strftime('%H:%M')}"
    return {"briefings": briefings, "news": news, "time_window": time_window}
```

### 页面展示

- 标题：**📰 近1小时新闻**
- 时间标签：`time_window`（例：15:23~16:23）
- 最多显示 8 条，可点击跳转原文
- 无数据时显示：暂无近1小时新闻

### 文件变更

| 文件 | 变更 |
|------|------|
| `backend/data/db.py` | 新增 `get_news_last_hours()` |
| `backend/routers/price.py` | `/api/briefings` 改用 `get_news_last_hours`，返回 `time_window`；新增 `POST /api/news/refresh` |
| `frontend/js/app.js` | 直接渲染后端返回的 news 和 time_window |
| `frontend/index.html` | 标题改为「📰 近1小时新闻」 |
