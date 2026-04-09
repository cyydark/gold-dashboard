"""全局配置常量 — 应用层可调参数集中在此。

NEWS_TTL:           新闻源缓存 TTL（秒）
REFRESH_INTERVAL:    新闻/价格后台刷新间隔（秒）
CLI_TIMEOUT:         Claude CLI subprocess 超时（秒）
DAILY_BRIEFING_HOUR: 日报生成触发时间（北京时间小时）
"""

from dotenv import load_dotenv
load_dotenv()

NEWS_TTL = 300             # 5 minutes — shared news source cache TTL
REFRESH_INTERVAL = 360     # 6 minutes — 新闻/价格刷新间隔（> TTL 300s）
CLI_TIMEOUT = 120          # seconds — Claude CLI 超时
DAILY_BRIEFING_HOUR = 8    # 北京时间
