"""AI 金市简报生成 via claude -p 命令。"""
import logging
import os
import subprocess
from datetime import datetime, timezone, timedelta

from backend.data import constants as c

logger = logging.getLogger(__name__)


class BriefingGenerationError(Exception):
    """Raised when Claude CLI fails to generate a briefing."""

    pass

DAILY_PROMPT_TEMPLATE = """你是一位专业黄金市场分析师。基于近3日{news_count}条新闻（当前金价 ${current_price} USD/oz），请评估当前金价走势。

{news_list}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【走势判断】
上涨/震荡/下跌——逻辑一句话

【核心驱动】
★★★ 地缘/风险：（一行）
★★ 央行/宏观：（一行）
★ 市场/技术：（一行）

【时效性】
近24h重点新闻对走势的影响权重说明

【置信度】
高/中/低，理由一句话"""


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


CROSS_VALIDATION_TEMPLATE = """你是一位专业黄金市场分析师。请将以下 Layer 1 新闻分析结论与 Layer 2 实际行情数据进行交叉对比，判断新闻判断是否与实际走势吻合。

【Layer 1 - 新闻分析结论】
{layer1_output}

【Layer 2 - Binance XAUUSD 日线聚合数据（5M K线）】
{kline_summary}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【验证结果】
一致 / 矛盾 / 信号不足

【实际走势】
从 Kline 数据提取的趋势描述（一句话）

【分歧说明】
如验证结果为"矛盾"，说明新闻预判与实际走势的差异；否则留空或写"无明显分歧"

【验证置信度】
高/中/低，理由一句话"""


PRICE_FORECAST_TEMPLATE = """你是一位专业黄金市场分析师。基于以下 Layer 1 新闻分析与 Layer 2 行情验证的结论，给出短期金价走势预期。

【Layer 1 - 新闻分析结论】
{layer1_output}

【Layer 2 - 行情验证结论】
{layer2_output}

请严格按以下分区结构输出，无任何前言、解释或分节符号：

【方向预期】
短期（1-3日）方向：上涨/震荡/下跌，理由一句话

【价格目标】
支撑位：XXX USD/oz
压力位：XXX USD/oz

【时间框架】
预期生效窗口：X-X日

【风险提示】
可能推翻预期的关键事件（1-2条）

【综合置信度】
高/中/低
理由：基于 Layer 2 验证一致性说明"""


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
        klines: binance_kline.fetch_xauusd_kline() 返回的列表，最新在前。

    Returns:
        多行字符串，供 CROSS_VALIDATION_TEMPLATE 渲染使用。
    """
    if not klines:
        return "（暂无 K线数据）"

    # 按日期分组（上海时区）
    daily_groups: dict[str, list[dict]] = {}
    for bar in klines:
        dt = _shanghai_ts(bar["time"])
        date_key = dt.strftime("%Y-%m-%d")
        daily_groups.setdefault(date_key, []).append(bar)

    # 按日期升序排列（旧的在前，供尾盘分析使用）
    sorted_dates = sorted(daily_groups.keys())

    # 构建每日摘要，取最多 3 个交易日
    day_lines: list[str] = []
    key_lines: list[str] = []

    max_high_price, max_high_date = -1.0, ""
    min_low_price, min_low_date = float("inf"), ""

    for date_key in sorted_dates[-3:]:
        bars = daily_groups[date_key]          # 该日所有 5M bar，最新在前
        open_price = bars[-1]["open"]           # 当地时间 00:00 的开盘
        close_price = bars[0]["close"]          # 当日最后一根 5M bar 的收盘
        high_price = max(b["high"] for b in bars)
        low_price = min(b["low"] for b in bars)
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

        close_dir = _last_5_close_direction(bars)
        sign = "+" if change >= 0 else ""
        day_lines.append(
            f"{date_key}：开{open_price} 收{close_price} "
            f"高{high_price} 低{low_price} "
            f"涨跌{sign}{change} ({sign}{pct}%) 趋势：{trend} "
            f"尾盘（最后25分钟）：{close_dir}"
        )

    # 近2日关键信息
    if len(sorted_dates) >= 2:
        amplitude = round(max_high_price - min_low_price, 2)
        key_lines.append(f"- 近2日最高：{max_high_price}（{max_high_date[5:]}）")
        key_lines.append(f"- 近2日最低：{min_low_price}（{min_low_date[5:]}）")
        key_lines.append(f"- 波动幅度：{amplitude} USD/oz")

    sections = ["日线数据：", *day_lines]
    if key_lines:
        sections.append("近期关键信息：")
        sections.extend(key_lines)

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

