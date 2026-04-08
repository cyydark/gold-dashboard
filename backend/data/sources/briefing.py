"""AI 金市简报生成 via claude -p 命令。"""
import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone, timedelta

from backend.data import constants as c

logger = logging.getLogger(__name__)


class BriefingGenerationError(Exception):
    """Raised when Claude CLI fails to generate a briefing."""

    pass

DAILY_PROMPT_TEMPLATE = """用大白话说清楚黄金这两天的走势。不要任何markdown格式（不用加粗、斜体、表格、---分隔线）。

新闻来源（共{news_count}条，当前金价 ${current_price} USD/oz）：
{news_list}

直接回答，不用客气话，分三块：

【现在怎么看】
涨还是跌？什么原因？说人话，别绕。

【最近发生了什么】
挑最重要的2-3条新闻，说清楚它们是怎么影响金价的。

【接下来会怎样】
可能涨还是跌？理由是什么？"""

L12_STREAMING_TEMPLATE = """用大白话分析黄金走势，结合新闻和实际行情数据。不要任何markdown格式。

【新闻来源】（共{news_count}条，当前金价 ${current_price} USD/oz）
{news_list}

【实际行情数据】
{kline_summary}

分两部分输出：

【分析结论】

（金价当前方向、核心驱动、新闻与走势是否吻合，用大白话）

【金价预期】

（简单说接下来涨还是跌、能到多少、什么时候见效、什么情况下变卦）"""

L3_STREAMING_TEMPLATE = """基于以上分析，给出最直接的判断：

【接下来涨还是跌】
说清楚。

【能涨/跌到多少】
给个大概区间。

【什么时候见效】
大概多久？

【什么情况下变卦】
最容易打破预期的一件事是什么？"""


def call_claude_cli(prompt: str) -> str:
    """调用 claude -p 命令，返回简报文本。"""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=c.CLI_TIMEOUT, env={**os.environ},
        )
        if result.returncode != 0:
            logger.warning(f"Claude CLI error: {result.stderr}")
            raise BriefingGenerationError(f"Claude CLI exited with code {result.returncode}: {result.stderr}")
        return result.stdout.strip()
    except FileNotFoundError:
        logger.warning("claude CLI not found")
        raise BriefingGenerationError("claude CLI not found")
    except Exception as e:
        logger.warning(f"Claude CLI call failed: {e}")
        raise BriefingGenerationError(f"Claude CLI call failed: {e}")


async def call_claude_cli_streaming(prompt: str) -> tuple[asyncio.StreamReader, asyncio.subprocess.Process]:
    """启动 claude -p 流式进程，返回 stdout reader 和进程对象。

    Caller must await proc.wait() or call proc.terminate() to clean up the subprocess.
    """
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={**os.environ},
    )
    return proc.stdout, proc


def _build_news_list(news: list[dict]) -> str:
    """从新闻列表构建 prompt 文本。"""
    lines = []
    for n in news:
        title = n.get("title", "").strip()
        if not title:
            continue
        lines.append(title)
    return "\n".join(lines)


async def generate_daily_briefing_from_news(news: list[dict], current_price: str = "N/A") -> str:
    """Generate daily briefing text from news using Claude CLI."""
    if not news:
        return "暂无足够新闻数据生成日报。"
    news_list = _build_news_list(news)
    prompt = DAILY_PROMPT_TEMPLATE.format(
        news_count=len(news),
        news_list=news_list,
        current_price=current_price,
    )
    return call_claude_cli(prompt)


# -------------------------------------------------------------------
# Step 2: 行情交叉验证
# -------------------------------------------------------------------


CROSS_VALIDATION_TEMPLATE = """对比一下新闻说的和实际行情，看看新闻分析准不准。不要任何markdown格式。

【新闻分析】
{layer1_output}

【实际行情数据】
{kline_summary}

直接说：

【新闻说的对不对】
对 / 不太对 / 看不出来

【实际情况是什么样的】
用大白话描述这两天金价实际怎么走的。

【差在哪里】
如果新闻和实际对不上，具体说哪里不一样。"""


PRICE_FORECAST_TEMPLATE = """结合新闻分析和实际行情，给个简单直接的判断。不要任何markdown格式。

【新闻分析】
{layer1_output}

【行情验证】
{layer2_output}

直接说：

【接下来涨还是跌】
说清楚。

【能涨/跌到多少】
给个大概的数字区间。

【什么时候见效】
大概要等多久？

【什么情况下会变卦】
说出最可能打破预期的一件事。"""


async def generate_price_forecast(layer1_output: str, layer2_output: str) -> str:
    """Step 3: Generate price forecast based on Layer 1 + Layer 2 conclusions."""
    prompt = PRICE_FORECAST_TEMPLATE.format(
        layer1_output=layer1_output,
        layer2_output=layer2_output,
    )
    try:
        return call_claude_cli(prompt)
    except BriefingGenerationError:
        return ""


def _shanghai_ts(ts: int) -> datetime:
    """将 Unix 时间戳转换为上海时区的日期。"""
    utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    return utc.astimezone(timezone(timedelta(hours=8)))


def _last_5_close_direction(bars: list[dict]) -> str:
    """判断最近 5 根 5M bar 的收盘方向。"""
    if len(bars) < 5:
        return "数据不足"
    recent = bars[-5:]
    first_close = recent[0]["close"]
    last_close = recent[-1]["close"]
    diff_pct = (last_close - first_close) / first_close * 100 if first_close else 0
    if diff_pct > 0.1:
        return "上涨"
    elif diff_pct < -0.1:
        return "下跌"
    else:
        return "震荡"


def aggregate_kline_for_prompt(klines: list[dict]) -> str:
    """将 Binance 5M K线列表聚合为日线摘要字符串，供 Step 2 prompt 使用。

    Args:
        klines: binance_kline.fetch_xauusd_kline() 返回的列表 oldest-first。

    Returns:
        多行字符串，供 CROSS_VALIDATION_TEMPLATE 渲染使用。
    """
    if not klines:
        return "（暂无 K线数据）"

    # 数据 oldest-first（第一条 = 最早一根），确认一下
    newest_close = klines[-1]["close"]
    oldest_open = klines[0]["open"]

    # 按日期分组（上海时区）
    daily_groups: dict[str, list[dict]] = {}
    for bar in klines:
        dt = _shanghai_ts(bar["time"])
        date_key = dt.strftime("%Y-%m-%d")
        daily_groups.setdefault(date_key, []).append(bar)

    # 按日期升序排列
    sorted_dates = sorted(daily_groups.keys())

    # 构建每日摘要，取最近 3 个交易日
    day_lines: list[str] = []
    max_high_price, max_high_date = -1.0, ""
    min_low_price, min_low_date = float("inf"), ""

    for date_key in sorted_dates[-3:]:
        bars = daily_groups[date_key]          # 该日所有 5M bar，oldest-first
        bars_rev = list(reversed(bars))       # 反转为 newest-first 供计算用
        open_price = bars_rev[-1]["open"]      # 当日第一根（最早）的开盘 = 日开盘
        close_price = bars_rev[0]["close"]     # 当日最后一根（最新）的收盘 = 日收盘
        high_price = max(b["high"] for b in bars_rev)
        low_price = min(b["low"] for b in bars_rev)
        change = round(close_price - open_price, 2)
        pct = round(change / open_price * 100, 2) if open_price else 0.0

        if high_price > max_high_price:
            max_high_price, max_high_date = high_price, date_key
        if low_price < min_low_price:
            min_low_price, min_low_date = low_price, date_key

        if pct > 0.2:
            trend = "上涨"
        elif pct < -0.2:
            trend = "下跌"
        else:
            trend = "震荡"

        close_dir = _last_5_close_direction(list(reversed(bars)))
        sign = "+" if change >= 0 else ""
        day_lines.append(
            f"{date_key}：开{open_price} 收{close_price} "
            f"高{high_price} 低{low_price} "
            f"涨跌{sign}{change} ({sign}{pct}%) 趋势：{trend} "
            f"尾盘（最后25分钟）：{close_dir}"
        )

    # 整体趋势描述
    overall_change = round(newest_close - oldest_open, 2)
    overall_pct = round(overall_change / oldest_open * 100, 2) if oldest_open else 0.0
    sign = "+" if overall_change >= 0 else ""
    key_lines = [
        f"- 整体方向：{oldest_open} → {newest_close}，{sign}{overall_change} ({sign}{overall_pct}%)",
        f"- 近2日最高：{max_high_price}（{max_high_date[5:]}）",
        f"- 近2日最低：{min_low_price}（{min_low_date[5:]}）",
        f"- 波动幅度：{round(max_high_price - min_low_price, 2)} USD/oz",
    ]

    sections = ["日线数据：", *day_lines, "近期关键信息：", *key_lines]
    return "\n".join(sections)


async def generate_cross_validation(layer1_output: str, kline_data: list[dict]) -> str:
    """Step 2: cross-validate news analysis against Kline data."""
    kline_summary = aggregate_kline_for_prompt(kline_data)
    prompt = CROSS_VALIDATION_TEMPLATE.format(
        layer1_output=layer1_output,
        kline_summary=kline_summary,
    )
    try:
        return call_claude_cli(prompt)
    except BriefingGenerationError:
        return ""


# -------------------------------------------------------------------
# Streaming prompt builders (L12 merged + independent L3)
# -------------------------------------------------------------------


def build_l1_prompt(news: list[dict], current_price: str) -> str:
    news_list = _build_news_list(news)
    return DAILY_PROMPT_TEMPLATE.format(
        news_count=len(news),
        news_list=news_list,
        current_price=current_price,
    )


def build_l2_prompt(layer1_output: str, kline_summary: str) -> str:
    return CROSS_VALIDATION_TEMPLATE.format(
        layer1_output=layer1_output,
        kline_summary=kline_summary,
    )


def build_l3_prompt(layer1_output: str, layer2_output: str) -> str:
    return PRICE_FORECAST_TEMPLATE.format(
        layer1_output=layer1_output,
        layer2_output=layer2_output,
    )

