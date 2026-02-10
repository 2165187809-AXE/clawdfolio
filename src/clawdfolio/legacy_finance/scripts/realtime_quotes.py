#!/usr/bin/env python3
"""实时行情获取 - broker-first 行情

数据源优先级：
1. 长桥 Quote API（如有行情权限）
2. moomoo OpenD 行情（如 OpenD 正在运行）
3. yfinance 兜底（延迟约1-2分钟）

输出：持仓股票的实时报价、涨跌幅、成交量等
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.brokers import fetch_holdings
from lib.fmt import fmt_time
from lib.market_data import fetch_best_quotes


def format_number(n: Optional[float], decimals: int = 2) -> str:
    if n is None:
        return "-"
    if abs(n) >= 1e9:
        return f"{n / 1e9:.1f}B"
    if abs(n) >= 1e6:
        return f"{n / 1e6:.1f}M"
    if abs(n) >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:.{decimals}f}"


def format_change(change: Optional[float], change_pct: Optional[float]) -> str:
    if change is None or change_pct is None:
        return "-"
    sign = "+" if change >= 0 else ""
    arrow = "▲" if change >= 0 else "▼"
    return f"{arrow} {sign}{change:.2f} ({sign}{change_pct:.2f}%)"


def main():
    now = datetime.now()
    print(f"📈 实时行情 ({fmt_time(now, '%Y-%m-%d %H:%M')})")
    print("数据源优先级: 长桥 → moomoo → Yahoo(兜底, 延迟1-2分钟)\n")

    holdings = fetch_holdings()
    if not holdings:
        print("未找到持仓。请确保长桥或moomoo OpenD正在运行。")
        return

    tickers = list(holdings.keys())
    print(f"正在获取 {len(tickers)} 只股票的实时行情...\n")

    # Broker-first quotes (with Yahoo fallback)
    quotes = fetch_best_quotes(tickers)

    if not quotes:
        print("无法获取行情数据。")
        return

    sorted_tickers = sorted(
        quotes.keys(),
        key=lambda t: (holdings[t].qty * (quotes[t].get("price") or 0)),
        reverse=True,
    )

    total_value = 0
    total_day_change = 0

    print("━━━ 持仓行情 ━━━\n")
    print(f"{'股票':<6} {'现价':>8} {'涨跌':>18} {'持仓数':>8} {'市值':>10}  来源")
    print("-" * 64)

    for t in sorted_tickers:
        q = quotes[t]
        qty = holdings[t].qty
        price = float(q.get("price") or 0)
        mv = qty * price
        total_value += mv

        prev_close = q.get("prev_close")
        change = None
        change_pct = None
        if prev_close is not None and float(prev_close) != 0:
            prev_close = float(prev_close)
            change = price - prev_close
            change_pct = (price / prev_close - 1) * 100
            total_day_change += qty * change

        change_str = format_change(change, change_pct)
        src = q.get("source") or "-"
        print(f"{t:<6} ${price:>7.2f} {change_str:>18} {int(qty):>8} ${format_number(mv):>8}  [{src}]")

    print("-" * 64)

    prev_value = total_value - total_day_change
    day_change_pct = (total_day_change / prev_value * 100) if prev_value > 0 else 0
    print(f"\n{'总计':<6} {'':<8} {format_change(total_day_change, day_change_pct):>18} {'':<8} ${format_number(total_value):>8}")

    # Top movers
    print("\n━━━ 今日涨跌榜 ━━━")

    by_change = sorted(
        [(t, q.get("change_pct", 0)) for t, q in quotes.items()],
        key=lambda x: x[1] if x[1] is not None else 0,
        reverse=True,
    )

    gainers = [(t, c) for t, c in by_change if c and c > 0][:3]
    losers = [(t, c) for t, c in by_change if c and c < 0][-3:][::-1]

    if gainers:
        print("\n▲ 领涨:")
        for t, c in gainers:
            print(f"   {t}: +{c:.2f}%")

    if losers:
        print("\n▼ 领跌:")
        for t, c in losers:
            print(f"   {t}: {c:.2f}%")

    # Volume alerts
    print("\n━━━ 成交量异常 ━━━")
    volume_alerts = []
    for t, q in quotes.items():
        vol = q.get("volume")
        avg_vol = q.get("avg_volume")
        if vol and avg_vol and avg_vol > 0:
            ratio = vol / avg_vol
            if ratio > 2:
                volume_alerts.append((t, ratio, vol))

    if volume_alerts:
        volume_alerts.sort(key=lambda x: x[1], reverse=True)
        for t, ratio, vol in volume_alerts[:5]:
            print(f"   {t}: {ratio:.1f}x 平均成交量 ({format_number(vol)})")
    else:
        print("   ✓ 无异常")

    print(f"\n⏱️ 数据时间: {fmt_time(now, '%H:%M')}")


if __name__ == "__main__":
    main()
