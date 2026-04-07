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

DAILY_PROMPT_TEMPLATE = """你是一位专业黄金市场分析师。基于最新资讯提供的{news_count}条相关新闻，请评估当前金价走势。

评估原则：
1. 时效性：越近期的新闻权重越高
2. 重要性分级：地缘政治/突发风险 ★★★ > 央行政策/宏观经济 ★★ > 市场情绪/技术面 ★
3. 综合判断，给出金价走势预期

{news_list}

请严格按以下4行格式输出，无任何解释、前言或分节符号：
【金价走势】震荡偏强/震荡偏弱/上涨/下跌/区间震荡——20字以内一句话概括核心逻辑
【重点关注】近期最值得关注的2-3条新闻（30字以内）
★★★ 因素一（地缘政治/突发风险）：一句话影响分析
★★ 因素二（央行政策/宏观经济）：一句话影响分析"""


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


async def generate_daily_briefing_from_news(news: list[dict]) -> str:
    """Generate daily briefing text from news using Claude CLI."""
    if not news:
        return "暂无足够新闻数据生成日报。"
    news_list = _build_news_list(news)
    prompt = DAILY_PROMPT_TEMPLATE.format(news_count=len(news), news_list=news_list)
    return call_claude_cli(prompt)


# -------------------------------------------------------------------
# Step 2: 行情交叉验证
# -------------------------------------------------------------------


CROSS_VALIDATION_TEMPLATE = """你是一位专业黄金市场分析师。请将以下 Step 1 新闻分析结论与 Step 2 实际行情数据进行交叉对比，判断新闻判断是否与实际走势吻合。

【Step 1 - 新闻分析结论】
{news_analysis}

【Step 2 - Binance XAUUSD 日线聚合数据（5M K线聚合）】
{kline_summary}

请严格按以下格式输出1-2行结论，无任何额外解释、前言或分节符号：
判断结果 | 理由（20字以内）
判断结果为以下三种之一：
- 一致：✓ 新闻判断与走势吻合，继续维持「{verdict_anchor}」
- 矛盾：⚠ 新闻判断与走势相悖，实际走势为[描述]，建议修正为「[修正结论]」
- 信号不足：当前走势无明确方向，新闻判断暂作参考"""


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


async def generate_cross_validation(news_analysis: str, kline_data: list[dict]) -> str:
    """Step 2: 交叉验证新闻分析与实际 K线走势是否一致。

    Args:
        news_analysis: Step 1 生成的新闻分析 4 行格式文本。
        kline_data: binance_kline.fetch_xauusd_kline() 返回的原始 5M K线列表。

    Returns:
        交叉验证结论字符串；异常时返回空字符串（由调用方负责降级处理）。
    """
    kline_summary = aggregate_kline_for_prompt(kline_data)
    # 从 Step 1 结论中提取走势关键词作为默认锚定
    verdict_anchor = "震荡"
    for kw in ["上涨", "下跌", "偏强", "偏弱", "震荡"]:
        if kw in news_analysis:
            verdict_anchor = kw
            break
    prompt = CROSS_VALIDATION_TEMPLATE.format(
        news_analysis=news_analysis,
        kline_summary=kline_summary,
        verdict_anchor=verdict_anchor,
    )
    try:
        return call_claude_cli(prompt)
    except BriefingGenerationError:
        return ""

