"""全局配置常量 — 应用层可调参数集中在此。

REFRESH_INTERVAL:      新闻/价格后台刷新间隔（秒）
BRIEFING_LOOP_SLEEP:    简报生成后等待时长（秒）
CLI_TIMEOUT:            Claude CLI subprocess 超时（秒）
DAILY_BRIEFING_HOUR:    日报生成触发时间（北京时间小时）
"""

from dotenv import load_dotenv
load_dotenv()

import os

REFRESH_INTERVAL = 360     # 6 minutes — 新闻/价格刷新间隔（> TTL 300s，避免 cache miss）
BRIEFING_LOOP_SLEEP = 3600 # 1 hour — 简报生成后等待
CLI_TIMEOUT = 120          # seconds — Claude CLI 超时
DAILY_BRIEFING_HOUR = 8    # 北京时间
