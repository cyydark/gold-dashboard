# 黄金分析仪表盘 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 容器化部署黄金分析仪表盘，包含实时金价、AI 新闻分析、RSS + 网页输出

**Architecture:**
- `gold_rss_server.py`：内置 HTTP 服务器，端口 18888，提供网页 + RSS
- `news_ai.py`：APScheduler 定时任务，每 15 分钟抓新闻 + 调用 MiniMax AI 分析
- 两个进程通过共享状态（JSON 文件）通信，不引入额外依赖
- 前端：纯 HTML/CSS/JS，零构建工具

**Tech Stack:** Python 3.14 / httpx / APScheduler / openai (MiniMax 兼容) / PyYAML

---

## Task 1: 项目结构与配置文件

**Files:**
- Create: `gold-ai-news/sources.yaml`
- Create: `gold-ai-news/requirements.txt`
- Create: `gold-ai-news/.env.example`

- [ ] **Step 1: 创建目录和 sources.yaml**

```yaml
# gold-ai-news/sources.yaml
sources:
  - name: 华尔街见闻快讯
    url: http://192.168.2.200:11200/wallstreetcn/live
    enabled: true
    keywords:
      - 黄金
      - 美元
      - 美联储
      - 关税
      - 央行
      - 制裁
      - 战争
      - CPI
      - 非农
      - FOMC
      - 降息
      - 加息

  - name: 金十数据
    url: http://192.168.2.200:11200/jinse/lives
    enabled: false
    keywords:
      - 黄金
      - 美元
      - 美联储
      - 汇率
```

- [ ] **Step 2: 创建 requirements.txt**

```
httpx>=0.28.0
apscheduler>=3.10.0
openai>=1.50.0
pyyaml>=6.0.0
```

- [ ] **Step 3: 创建 .env.example**

```env
# MiniMax API
MINIMAX_API_KEY=your_api_key_here

# RSSHub 地址
RSSHUB_BASE_URL=http://192.168.2.200:11200

# 服务器端口
PORT=18888

# 分析间隔（分钟）
NEWS_CHECK_INTERVAL=15
BRIEFING_INTERVAL=60

# 数据文件路径
DATA_DIR=/app/data
```

- [ ] **Step 4: Commit**

```bash
mkdir -p gold-ai-news && cd gold-ai-news
git init
git add sources.yaml requirements.txt .env.example
git commit -m "feat: init project structure and config"
```

---

## Task 2: 金价 HTTP 服务（gold_rss_server.py）

**Files:**
- Create: `gold-ai-news/gold_rss_server.py`
- Modify: `gold-ai-news/.env`（创建，包含真实 API Key）

**依赖（仅标准库 + httpx）：**
- 端口 18888，监听 `0.0.0.0`
- 缓存金价 30 秒
- 提供三个端点：
  - `GET /` → 网页（HTML）
  - `GET /rss` → RSS XML
  - `GET /api/price` → JSON 当前金价
  - `GET /api/briefing` → JSON 今日简报
  - `GET /api/alerts` → JSON 最新预警
  - `GET /api/news` → JSON 最新新闻列表

- [ ] **Step 1: 写 gold_rss_server.py**

```python
#!/usr/bin/env python3
"""
黄金实时价格 + 分析结果 HTTP 服务
端口: 18888
"""

import time
import json
import ssl
import threading
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = 18888
CNY_TZ = timezone(timedelta(hours=8))
CACHE_TTL = 30  # 金价缓存秒数

cached_price = {"data": None, "ts": 0}
DATA_DIR = Path("/app/data")
STATE_FILE = DATA_DIR / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"briefing": None, "alerts": [], "recent_news": []}


def fetch_json(url: str) -> dict | None:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def get_gold_price() -> dict:
    """获取 OKX XAUT/USDT 价格（24/7，1 XAUT = 1 金衡盎司黄金）"""
    data = fetch_json("https://www.okx.com/api/v5/market/ticker?instId=XAUT-USDT")
    if not data or data.get("code") != "0" or not data.get("data"):
        raise RuntimeError("无法获取 OKX 金价")

    d = data["data"][0]
    last = float(d["last"])
    open_ = float(d["sodUtc8"])
    change_pct = (last - open_) / open_ * 100

    # USD/CNY 汇率
    rate_data = fetch_json("https://open.er-api.com/v6/latest/USD")
    cny_rate = float(rate_data["rates"]["CNY"]) if rate_data else 7.0

    return {
        "price_usd": last,
        "change_pct": change_pct,
        "high_24h": float(d["high24h"]),
        "low_24h": float(d["low24h"]),
        "cny_rate": cny_rate,
        "price_cny_gram": round(last * cny_rate / 31.1035, 2),
    }


def build_html(price: dict, state: dict) -> str:
    now = datetime.now(CNY_TZ)
    gold = price
    state_str = json.dumps(state, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>黄金分析仪表盘</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, sans-serif; background: #0f0f14; color: #e0e0e0; min-height: 100vh; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 24px 16px; }}
  h1 {{ color: #f0c040; font-size: 1.5em; margin-bottom: 16px; text-align: center; }}
  .price-card {{ background: #1a1a24; border: 1px solid #333; border-radius: 12px; padding: 24px; margin-bottom: 16px; text-align: center; }}
  .price-main {{ font-size: 2.5em; font-weight: 700; color: #f0c040; }}
  .price-sub {{ color: #888; margin-top: 4px; }}
  .change {{ font-size: 1.1em; margin-top: 8px; }}
  .up {{ color: #22c55e; }} .down {{ color: #ef4444; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }}
  .box {{ background: #1a1a24; border: 1px solid #333; border-radius: 8px; padding: 16px; }}
  .box h3 {{ color: #888; font-size: 0.85em; margin-bottom: 8px; text-transform: uppercase; }}
  .box p, .box .content {{ font-size: 0.95em; line-height: 1.6; }}
  .news-item {{ padding: 8px 0; border-bottom: 1px solid #222; font-size: 0.9em; }}
  .news-item:last-child {{ border-bottom: none; }}
  .tag {{ display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 0.75em; margin-left: 6px; }}
  .tag-bull {{ background: #1a3a1a; color: #22c55e; }}
  .tag-bear {{ background: #3a1a1a; color: #ef4444; }}
  .tag-neutral {{ background: #2a2a2a; color: #888; }}
  .alert-high {{ border-left: 3px solid #ef4444; padding-left: 8px; }}
  .alert-medium {{ border-left: 3px solid #f59e0b; padding-left: 8px; }}
  .footer {{ text-align: center; color: #555; font-size: 0.8em; margin-top: 24px; }}
  #briefing {{ white-space: pre-wrap; line-height: 1.8; }}
  .refresh {{ color: #666; font-size: 0.8em; text-align: right; }}
</style>
</head>
<body>
<div class="container">
  <h1>黄金分析仪表盘</h1>
  <div class="refresh">更新时间: {now.strftime('%H:%M:%S')}</div>

  <div class="price-card">
    <div class="price-main" id="price-main">--</div>
    <div class="price-sub">元/克 (人民币)</div>
    <div class="change" id="change">--</div>
    <div class="price-sub" style="margin-top:8px" id="price-usd">-- / 盎司</div>
  </div>

  <div class="grid">
    <div class="box">
      <h3>今日简报</h3>
      <div class="content" id="briefing">等待分析...</div>
    </div>
    <div class="box">
      <h3>风险预警</h3>
      <div id="alerts">暂无预警</div>
    </div>
  </div>

  <div class="box">
    <h3>最新新闻</h3>
    <div id="news">加载中...</div>
  </div>

  <div class="footer">
    数据来源: OKX XAUT (24/7) · 华尔街见闻 · MiniMax AI 分析<br>
    <a href="/rss" style="color:#f0c040">📡 订阅 RSS</a>
  </div>
</div>

<script>
const state = {state_str};

function render() {{
  const price = document.getElementById('price-main');
  const change = document.getElementById('change');
  const usd = document.getElementById('price-usd');
  const briefing = document.getElementById('briefing');
  const alerts = document.getElementById('alerts');
  const news = document.getElementById('news');

  if (state.price) {{
    price.textContent = state.price.price_cny_gram + ' 元/克';
    usd.textContent = '$' + state.price.price_usd.toFixed(2) + ' / 盎司';
    const p = state.price.change_pct;
    change.innerHTML = (p >= 0 ? '+' : '') + p.toFixed(2) + '% (24h)';
    change.className = 'change ' + (p >= 0 ? 'up' : 'down');
  }}

  if (state.briefing) {{
    briefing.textContent = state.briefing;
  }}

  if (state.alerts && state.alerts.length) {{
    alerts.innerHTML = state.alerts.slice(0,3).map(a =>
      `<div class="alert-{{a.level}}">{{a.title}}</div><div style="font-size:0.85em;color:#888;margin-top:4px">{{a.summary}}</div>`
    ).join('');
  }}

  if (state.recent_news && state.recent_news.length) {{
    news.innerHTML = state.recent_news.slice(0,10).map(n =>
      `<div class="news-item">
        <span class="tag tag-{{n.sentiment === '利多' ? 'bull' : n.sentiment === '利空' ? 'bear' : 'neutral'}}">{{n.sentiment}}</span>
        {{n.title}}
      </div>`
    ).join('');
  }}
}}

render();
setInterval(() => fetch('/api/state').then(r=>r.json()).then(s => {{ Object.assign(state, s); render(); }}), 30000);
</script>
</body>
</html>"""


def build_rss(price: dict, state: dict) -> str:
    now = datetime.now(CNY_TZ)
    now_str = now.strftime("%a, %d %b %Y %H:%M:%S +0800")
    items = []

    for a in (state.get("alerts", []) or [])[:5]:
        items.append(f"""  <item>
    <title>[预警] {a["title"]}</title>
    <link>http://192.168.2.200:{PORT}/</link>
    <guid isPermaLink="false">alert-{a.get("ts","")}</guid>
    <pubDate>{now_str}</pubDate>
    <description><![CDATA[{a.get("summary","")}]]></description>
  </item>""")

    if state.get("briefing"):
        items.append(f"""  <item>
    <title>今日简报：{state["briefing"][:60]}...</title>
    <link>http://192.168.2.200:{PORT}/</link>
    <guid isPermaLink="false">briefing-{now.strftime("%Y%m%d")}</guid>
    <pubDate>{now_str}</pubDate>
    <description><![CDATA[{state["briefing"]}]]></description>
  </item>""")

    items_xml = "\n".join(items) if items else "  <item><title>等待分析...</title></item>"

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>黄金分析 | {price["price_cny_gram"] if price else "--"} 元/克</title>
    <link>http://192.168.2.200:{PORT}/</link>
    <description>黄金实时价格 + AI 分析</description>
    <language>zh-CN</language>
    <lastBuildDate>{now_str}</lastBuildDate>
    <ttl>5</ttl>
    <atom:link href="http://192.168.2.200:{PORT}/rss" rel="self" type="application/rss+xml"/>
{items_xml}
  </channel>
</rss>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        state = load_state()
        try:
            price = get_gold_price()
        except Exception:
            price = cached_price["data"] or {"price_cny_gram": "--", "price_usd": 0, "change_pct": 0}

        now_ts = time.time()
        if price and now_ts - cached_price.get("ts", 0) < CACHE_TTL:
            price = cached_price["data"]
        elif price:
            cached_price["data"] = price
            cached_price["ts"] = now_ts

        if self.path == "/" or self.path == "/index.html":
            html = build_html(price or {}, state)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/rss":
            rss = build_rss(price or {}, state)
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.wfile.write(rss.encode("utf-8"))

        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            resp = {"price": price, **state}
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/api/price":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.wfile.write(json.dumps(price or {}, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/api/briefing":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.wfile.write(json.dumps({"briefing": state.get("briefing")}, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/api/alerts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.wfile.write(json.dumps(state.get("alerts", []), ensure_ascii=False).encode("utf-8"))

        else:
            self.send_response(404)
            self.wfile.write(b"Not Found")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"黄金分析仪表盘 http://0.0.0.0:{PORT}/")
    print(f"RSS 订阅: http://0.0.0.0:{PORT}/rss")
    server.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add gold_rss_server.py
git commit -m "feat: add gold price HTTP server with web UI and RSS"
```

---

## Task 3: AI 新闻分析（news_ai.py）

**Files:**
- Create: `gold-ai-news/news_ai.py`

**设计要点：**
- 读取 `sources.yaml` 获取 RSS 源列表
- 用 httpx 拉取 RSS，feedparser 解析
- 关键词过滤 + MiniMax AI 判断利多/利空/中性
- 共享状态写入 `/app/data/state.json`，`gold_rss_server.py` 读取
- APScheduler 两个任务：
  - `check_news`：每 15 分钟，检测重大事件
  - `generate_briefing`：每小时，汇总生成简报

- [ ] **Step 1: 写 news_ai.py**

```python
#!/usr/bin/env python3
"""
黄金新闻 AI 分析定时任务
每 15 分钟：检测重大事件 → MiniMax 判断利多/利空
每小时：汇总生成今日简报
状态写入 /app/data/state.json
"""

import os
import json
import ssl
import feedparser
import httpx
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from openai import OpenAI

# ---------- 配置 ----------
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
STATE_FILE = DATA_DIR / "state.json"
SOURCES_FILE = Path(os.getenv("SOURCES_FILE", "/app/sources.yaml"))
PORT = int(os.getenv("PORT", "18888"))
MINIMAX_KEY = os.getenv("MINIMAX_API_KEY", "")
RSSHUB_BASE = os.getenv("RSSHUB_BASE_URL", "http://192.168.2.200:11200")

CNY_TZ = timezone(timedelta(hours=8))

# 全局分析结果
state = {
    "briefing": None,
    "alerts": [],
    "recent_news": [],
    "last_briefing_ts": 0,
}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"briefing": None, "alerts": [], "recent_news": [], "last_briefing_ts": 0}


def save_state(s: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def get_all_news() -> list[dict]:
    """从 sources.yaml 获取所有启用的 RSS 源，返回新闻列表"""
    try:
        with open(SOURCES_FILE) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"[{now()}] 读取 sources.yaml 失败: {e}")
        return []

    all_news = []
    keywords = set()

    for src in config.get("sources", []):
        if not src.get("enabled"):
            continue
        for kw in src.get("keywords", []):
            keywords.add(kw)

        url = src["url"].replace("http://192.168.2.200:11200", RSSHUB_BASE)
        try:
            resp = httpx.get(url, timeout=15, verify=False)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:20]:
                all_news.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": src["name"],
                    "sentiment": None,
                })
        except Exception as e:
            print(f"[{now()}] 获取 {src['name']} 失败: {e}")

    return all_news, keywords


def call_minimax(prompt: str) -> str:
    """调用 MiniMax API，返回文本响应"""
    if not MINIMAX_KEY:
        return "[MiniMax API Key 未配置]"

    try:
        client = OpenAI(
            api_key=MINIMAX_KEY,
            base_url="https://api.minimax.chat/v1",
        )
        resp = client.chat.completions.create(
            model="MiniMax-M2.7",
            messages=[
                {"role": "system", "content": "你是一位专业的贵金属分析师，专注于黄金市场。你的分析简洁、有深度，用中文回答。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[{now()}] MiniMax API 错误: {e}")
        return ""


def analyze_sentiment(news: dict, gold_price: dict) -> dict:
    """用 MiniMax 判断单条新闻对金价的影响"""
    price_info = f"当前金价: ${gold_price.get('price_usd',0):,.2f}/盎司，24h涨跌: {gold_price.get('change_pct',0):+.2f}%，折合 {gold_price.get('price_cny_gram',0):,.2f} 元/克"

    prompt = f"""当前金价信息：{price_info}

新闻标题：{news['title']}
新闻来源：{news['source']}
发布时间：{news.get('published','')}

请判断这条新闻对黄金价格的影响：
1. 方向：利多、利空、还是中性？
2. 程度：轻微、中等、还是重大？
3. 给出1-2句话的简要解释。

请用以下JSON格式回答（只输出JSON，不要其他内容）：
{{"sentiment":"利多|利空|中性","level":"轻微|中等|重大","reason":"简短解释"}}
"""

    result = call_minimax(prompt)
    try:
        # 尝试从结果中提取 JSON
        import re
        m = re.search(r'\{[^}]+\}', result)
        if m:
            obj = json.loads(m.group())
            return obj
    except Exception:
        pass
    return {"sentiment": "中性", "level": "轻微", "reason": "分析失败"}


def generate_briefing(news_list: list[dict], gold_price: dict):
    """每小时生成今日金价简报"""
    if not news_list:
        return

    news_text = "\n".join(
        f"- [{n['source']}] {n['title']} (情绪: {n.get('sentiment','未知')})"
        for n in news_list[:15]
    )
    price_info = f"当前金价: ${gold_price.get('price_usd',0):,.2f}/盎司，{gold_price.get('price_cny_gram',0):,.2f} 元/克，24h涨跌: {gold_price.get('change_pct',0):+.2f}%"

    prompt = f"""你是一位专业的黄金市场分析师。请根据以下今日新闻，生成一份金价简报。

{price_info}

今日相关新闻（按时间倒序）：
{news_text}

请生成简报，要求：
1. 总结今日金价走势和主要驱动因素
2. 指出最值得关注的1-3个事件
3. 给出你对后市的简要判断（偏多/偏空/中性）
4. 提示普通纸黄金投资者应注意什么

用中文回答，简洁有力，不超过300字。"""

    briefing = call_minimax(prompt)
    state["briefing"] = briefing
    state["last_briefing_ts"] = int(datetime.now(CNY_TZ).timestamp())
    print(f"[{now()}] 简报已生成: {briefing[:80]}...")
    save_state(state)


def check_news_job():
    """每15分钟：检测重大事件 + 判断情绪"""
    print(f"[{now()}] 开始新闻检测...")

    s = load_state()
    gold_price = s.get("last_price", {})
    if not gold_price:
        try:
            gold_price = get_gold_price_quick()
        except Exception:
            gold_price = {}

    news_list, keywords = get_all_news()
    if not news_list:
        print(f"[{now()}] 无新闻数据")
        return

    # 关键词过滤：只分析包含关键词的新闻
    significant = []
    for n in news_list:
        title_lower = n["title"].lower()
        for kw in keywords:
            if kw.lower() in title_lower:
                significant.append(n)
                break

    print(f"[{now()}] 获取 {len(news_list)} 条新闻，过滤后 {len(significant)} 条相关")

    alerts = list(s.get("alerts", []) or [])
    recent_news = []

    for n in (significant + news_list)[:20]:
        if n.get("sentiment"):
            continue

        sentiment_data = analyze_sentiment(n, gold_price)
        n["sentiment"] = sentiment_data.get("sentiment", "中性")
        n["level"] = sentiment_data.get("level", "轻微")
        n["reason"] = sentiment_data.get("reason", "")
        recent_news.append(n)

        # 重大预警写入 state
        if sentiment_data.get("level") in ("重大", "中等") and sentiment_data.get("sentiment") != "中性":
            alerts.insert(0, {
                "title": n["title"][:60],
                "source": n["source"],
                "sentiment": sentiment_data["sentiment"],
                "level": sentiment_data["level"],
                "summary": sentiment_data.get("reason", ""),
                "ts": int(datetime.now(CNY_TZ).timestamp()),
                "link": n["link"],
            })
            alerts[:] = alerts[:10]  # 只保留最近10条

    # 按时间排序
    recent_news.sort(key=lambda x: x.get("published", ""), reverse=True)

    state["alerts"] = alerts
    state["recent_news"] = recent_news
    state["last_price"] = gold_price

    # 每小时生成简报
    now_ts = int(datetime.now(CNY_TZ).timestamp())
    last_ts = s.get("last_briefing_ts", 0)
    if now_ts - last_ts >= 3600:
        generate_briefing(recent_news, gold_price)

    save_state(state)
    print(f"[{now()}] 检测完成，预警 {len(alerts)} 条")


def get_gold_price_quick() -> dict:
    """快速获取金价（被 news_ai 调用）"""
    try:
        resp = httpx.get(
            "https://www.okx.com/api/v5/market/ticker?instId=XAUT-USDT",
            timeout=10, verify=False
        )
        data = resp.json()
        if data.get("code") != "0":
            return {}
        d = data["data"][0]
        last = float(d["last"])
        open_ = float(d["sodUtc8"])
        cny_rate = 6.9  # 简化，server 会单独更新

        return {
            "price_usd": last,
            "change_pct": (last - open_) / open_ * 100,
            "price_cny_gram": round(last * cny_rate / 31.1035, 2),
        }
    except Exception:
        return {}


def now() -> str:
    return datetime.now(CNY_TZ).strftime("%Y-%m-%d %H:%M:%S")


def main():
    print("=" * 50)
    print("  黄金新闻 AI 分析任务启动")
    print(f"  信息源: {SOURCES_FILE}")
    print(f"  状态文件: {STATE_FILE}")
    print("=" * 50)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    scheduler = BlockingScheduler()

    # 立即运行一次
    check_news_job()

    # 每15分钟检测新闻
    scheduler.add_job(
        check_news_job,
        IntervalTrigger(minutes=15),
        id="check_news",
        replace_existing=True,
    )

    scheduler.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add news_ai.py
git commit -m "feat: add AI news analysis scheduler with MiniMax integration"
```

---

## Task 4: Dockerfile 和 docker-compose

**Files:**
- Create: `gold-ai-news/Dockerfile`
- Create: `gold-ai-news/docker-compose.yml`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.14-slim

WORKDIR /app

# 安装系统依赖（httpx 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY gold_rss_server.py .
COPY news_ai.py .
COPY sources.yaml .

# 数据目录
RUN mkdir -p /app/data

# HTTP 服务（端口 18888）
EXPOSE 18888

# 启动：先跑 HTTP 服务，后台跑 AI 分析任务
CMD python gold_rss_server.py &
sleep 2 && python news_ai.py
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
version: "3.8"

services:
  gold-ai-news:
    build: .
    container_name: gold-ai-news
    ports:
      - "18888:18888"
    volumes:
      - ./sources.yaml:/app/sources.yaml:ro
      - gold-data:/app/data
    environment:
      - MINIMAX_API_KEY=${MINIMAX_API_KEY}
      - RSSHUB_BASE_URL=${RSSHUB_BASE_URL:-http://192.168.2.200:11200}
      - DATA_DIR=/app/data
      - SOURCES_FILE=/app/sources.yaml
      - PORT=18888
    restart: unless-stopped
    network_mode: host

volumes:
  gold-data:
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: add Dockerfile and docker-compose for deployment"
```

---

## Task 5: 端到端测试

**在本地 Mac 上模拟测试（群晖部署前验证）：**

- [ ] **Step 1: 安装依赖**

```bash
cd gold-ai-news
pip install -r requirements.txt
```

- [ ] **Step 2: 启动服务**

```bash
# 终端1：HTTP 服务
python gold_rss_server.py

# 终端2：AI 任务
MINIMAX_API_KEY=你的key python news_ai.py
```

- [ ] **Step 3: 验证端点**

```bash
# 网页
curl http://localhost:18888/ | head -5

# RSS
curl http://localhost:18888/rss | head -3

# JSON
curl http://localhost:18888/api/state
```

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "test: end-to-end verification complete"
```

---

## Task 6: 部署到群晖

**前提条件：**
- 群晖已安装 Docker（套件中心）
- `sources.yaml` 已填入真实 RSSHub 地址

- [ ] **Step 1: 上传项目到群晖**

```bash
# 在本地 Mac
scp -r gold-ai-news admin@192.168.2.200:/volume1/docker/gold-ai-news/
```

- [ ] **Step 2: 配置环境变量**

```bash
# 在群晖上创建 .env 文件
cd /volume1/docker/gold-ai-news
cat > .env << 'EOF'
MINIMAX_API_KEY=你的MiniMax_API_Key
RSSHUB_BASE_URL=http://192.168.2.200:11200
EOF
```

- [ ] **Step 3: 构建并启动**

```bash
cd /volume1/docker/gold-ai-news
docker-compose build
docker-compose up -d
```

- [ ] **Step 4: 验证**

```bash
curl http://192.168.2.200:18888/
# 应返回 HTML 页面

curl http://192.168.2.200:18888/api/state
# 应返回 JSON 包含 price、briefing、alerts
```

---

## 执行顺序

1. Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6
2. 每个 Task 完成后，告诉我，我会review
3. Task 6 完成后，群晖上验证
