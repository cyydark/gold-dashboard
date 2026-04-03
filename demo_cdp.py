#!/usr/bin/env python3
"""CDP-based demo: capture GF auth header once, reuse with requests.

验证思路：
1. 用 Playwright 启动一个 persistent Chromium（只启动一次）
2. 通过 page 监听网络请求，捕获 x-goog-ext-* header 和 URL
3. 后续所有 batchexecute 请求走纯 requests + 捕获的 header
4. 对比：纯 Playwright vs CDP+cached header
"""
import time
import json
import re
import urllib.parse
import requests
from playwright.sync_api import sync_playwright

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE_URL = "https://www.google.com/finance/quote/GCW00:COMEX"


def make_gf_request(url: str, body_template: str, auth_header: tuple, window: int = 1) -> str:
    """用 requests + auth header 发 batchexecute 请求，返回原始响应.

    body_template 必须是原始 URL-encoded 字符串（直接从 Playwright 捕获的 post_data）。
    """
    header_name, header_value = auth_header
    headers = {
        header_name: header_value,
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Referer": "https://www.google.com/finance/quote/GCW00:COMEX",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    # body_template 是原始 URL-encoded 字符串: "f.req=%5B%5B%5B%22AiCwsd..."
    # URL-decode → 替换 window → 直接作为 body bytes 发送（不再 re-encode）
    decoded = urllib.parse.unquote(body_template)

    # 替换 window 参数: ]],1, → ]],{window},
    # 但 f.req 里的数字是 JSON 里的 `,1,` (代表1天窗口)
    if window == 1:
        new_body = decoded
    else:
        new_body = re.sub(r'\],\d+,', '],' + str(window) + ',', decoded, count=1)

    resp = requests.post(url, data=new_body.encode("utf-8"), headers=headers, timeout=15)
    return resp.text


def parse_gf_response(raw: str) -> list[dict]:
    """解析 Google Finance batchexecute 原始响应为 bar list."""
    try:
        header_end = raw.index("[[")
    except ValueError:
        raise ValueError("No JSON array found")

    json_str = raw[header_end:]
    depth = 0
    arr_start = arr_end = -1
    for i, c in enumerate(json_str):
        if c == "[":
            if depth == 0:
                arr_start = i
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                arr_end = i + 1
                break

    if arr_start < 0 or arr_end < 0:
        raise ValueError(f"Bracket mismatch: start={arr_start}, end={arr_end}")

    outer = json.loads(json_str[arr_start:arr_end])
    inner_str = outer[0][2].replace('\\"', '"')
    parsed = json.loads(inner_str)
    session_groups = parsed[0]

    records = []
    for seg in session_groups:
        if not isinstance(seg, list) or len(seg) < 4:
            continue
        bars_info = seg[3][0][1] if (isinstance(seg[3], list) and len(seg[3]) > 0 and isinstance(seg[3][0], list) and len(seg[3][0]) > 1) else []
        if not bars_info:
            continue
        for bar in bars_info:
            if not isinstance(bar, list) or len(bar) < 2:
                continue
            ts_arr = bar[0]
            ohlcv = bar[1]
            if not isinstance(ts_arr, list) or not isinstance(ohlcv, list) or len(ohlcv) < 2:
                continue

            # parse timestamp
            try:
                year, month, day = ts_arr[0], ts_arr[1], ts_arr[2]
                hour = ts_arr[3] or 0
                minute = ts_arr[4] or 0
                tz_arr = ts_arr[-1] if isinstance(ts_arr[-1], list) else []
                tz_seconds = tz_arr[0] if tz_arr else -14400
                from datetime import datetime, timezone, timedelta
                et_tz = timezone(timedelta(seconds=tz_seconds))
                et_dt = datetime(year, month, day, hour, minute, tzinfo=et_tz)
                ts = int(et_dt.timestamp())
            except Exception:
                continue

            close_px = float(ohlcv[0])
            spread = float(ohlcv[1]) if ohlcv[1] else 0.0
            records.append({
                "time": ts,
                "open": round(close_px - spread / 2, 2),
                "high": round(close_px + spread / 2, 2),
                "low": round(close_px - spread / 2, 2),
                "close": round(close_px, 2),
                "volume": 0,
            })
    records.sort(key=lambda x: x["time"])
    return records


def demo_cdp_cached():
    """主流程：CDP cached header 方案.

    捕获 auth header 后，在浏览器关闭前立刻用 requests 重放。
    """
    captured = {}

    print("=" * 60)
    print("STEP 1: 启动 Chromium 并捕获 auth header (Playwright)")
    t0 = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        try:
            with page.expect_request(lambda r: "AiCwsd" in r.url, timeout=25000) as req_info:
                page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=20000)
            req = req_info.value
            captured["url"] = req.url
            captured["body"] = req.post_data or ""
            for name, val in req.headers.items():
                if name.startswith("x-goog-ext"):
                    captured["auth_header"] = (name, val)
                    break
        except Exception as e:
            print(f"  [!] 捕获失败: {e}")
            browser.close()
            return

        t1 = time.time()
        print(f"  捕获耗时: {t1 - t0:.1f}s")
        print(f"  URL: {captured.get('url', '')[:80]}")
        print(f"  Auth header: {captured.get('auth_header', ('',''))[0]}")
        print(f"  Body (first 80): {captured.get('body', '')[:80]}")

        if not captured.get("auth_header"):
            print("  [!] 未捕获到 auth header")
            browser.close()
            return

        # STEP 2-4: 立刻用 requests + 缓存的 header 发请求（浏览器仍然活着）
        results = {}
        for window, label in [(1, "1D"), (2, "5D"), (3, "30D")]:
            t_w = time.time()
            try:
                raw = make_gf_request(
                    captured["url"], captured["body"], captured["auth_header"], window=window
                )
                bars = parse_gf_response(raw)
                results[label] = (time.time() - t_w, len(bars), bars[0] if bars else None, bars[-1] if bars else None)
            except Exception as e:
                results[label] = (time.time() - t_w, 0, None, str(e))

        for label, (dt, count, first, last) in results.items():
            print(f"\n  {label} K线: {count}根, 耗时{dt:.3f}s, 首根={first}, 末根={last}")

        browser.close()


if __name__ == "__main__":
    demo_cdp_cached()
