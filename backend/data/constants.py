"""全局配置常量 — 应用层 magic numbers 集中在此处。

循环间隔 (秒)
    REFRESH_INTERVAL:   新闻/价格后台刷新间隔
    BRIEFING_LOOP_SLEEP: 简报生成后等待时长（1 小时）
    SSE_INTERVAL:        SSE 实时推送间隔
    CLI_TIMEOUT:        Claude CLI subprocess 超时（秒）

其他
    DAILY_BRIEFING_HOUR: 日报生成触发时间（北京时间小时）
"""

from dotenv import load_dotenv
load_dotenv()

import os

# — Loop intervals (seconds) —
REFRESH_INTERVAL = 300      # 5 minutes
BRIEFING_LOOP_SLEEP = 3600  # 1 hour
SSE_INTERVAL = 30          # seconds
CLI_TIMEOUT = 120          # seconds

# — Scheduling —
DAILY_BRIEFING_HOUR = 8    # Beijing time

# — Briefing —
NEWS_LIMIT_BRIEFING = 20  # max news items in briefing prompt

# — API query limits —
HISTORY_BARS_LIMIT = 2000   # /history endpoint
BRIEFINGS_LIMIT = 24        # /briefings default hourly limit
NEWS_LIMIT_BRIEFINGS_ENDPOINT = 20  # /briefings 近1小时新闻上限
