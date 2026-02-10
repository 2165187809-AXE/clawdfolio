#!/usr/bin/env python3
"""Earnings Calendar - 获取持仓股票的财报日历

获取未来30天内持仓股票的财报发布日期，帮助用户提前准备。

数据源: yfinance (via lib/market)
输出: 按日期排序的财报日历，自适应列宽
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.brokers import fetch_holdings
from lib.fmt import fmt_time
from lib.market import get_earnings_date, get_stock_info


def format_market_cap(mc: float) -> str:
    if mc >= 1e12:
        return f"${mc / 1e12:.1f}T"
    elif mc >= 1e9:
        return f"${mc / 1e9:.1f}B"
    elif mc >= 1e6:
        return f"${mc / 1e6:.0f}M"
    else:
        return ""


def main():
    now = datetime.now()
    today = now.date()
    end_date = today + timedelta(days=30)

    holdings = fetch_holdings()
    if not holdings:
        print("📅 财报日历\n\n未找到持仓股票。请确保长桥或moomoo OpenD正在运行。")
        return

    tickers = list(holdings.keys())

    print(f"📅 持仓财报日历 (未来30天)\n生成时间: {fmt_time(now)}\n")

    # Collect earnings dates
    earnings: List[Tuple[datetime, str, str, Dict[str, Any]]] = []

    print(f"正在查询 {len(tickers)} 只股票的财报日期...")

    for t in tickers:
        result = get_earnings_date(t)
        if result:
            dt, timing = result
            if today <= dt <= end_date:
                info = get_stock_info(t)
                earnings.append((datetime.combine(dt, datetime.min.time()), timing, t, info))

    if not earnings:
        print("\n✓ 未来30天内没有持仓股票发布财报\n")
        print("已查询股票:", ", ".join(sorted(tickers)))
        return

    # Sort by date
    earnings.sort(key=lambda x: x[0])

    print(f"\n━━━ 即将发布财报 ({len(earnings)}只) ━━━\n")

    # Group by week (using ISO week number + year for correct grouping)
    current_week_key = None
    for dt, timing, ticker, info in earnings:
        iso_year, iso_week, _ = dt.isocalendar()
        week_key = (iso_year, iso_week)
        if week_key != current_week_key:
            current_week_key = week_key
            week_start = dt - timedelta(days=dt.weekday())
            week_end = week_start + timedelta(days=4)
            print(f"📆 {week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}")

        days_until = (dt.date() - today).days
        if days_until == 0:
            day_hint = "今天"
        elif days_until == 1:
            day_hint = "明天"
        elif days_until <= 7:
            day_hint = f"{days_until}天后"
        else:
            day_hint = ""

        timing_emoji = "🌅" if timing == "BMO" else ("🌙" if timing == "AMC" else "❓")
        timing_text = {"BMO": "盘前", "AMC": "盘后", "TBD": "待定"}.get(timing, "待定")

        mc_str = format_market_cap(info.get("marketCap", 0))
        name = info.get("name", ticker)  # Don't truncate name

        line = f"  {dt.strftime('%m/%d %a')} {timing_emoji}{timing_text} | {ticker:6} {name}"
        if mc_str:
            line += f" ({mc_str})"
        if day_hint:
            line += f" ← {day_hint}"
        print(line)

    print()

    # Risk warnings
    print("━━━ ⚠️ 财报风险提示 ━━━")

    imminent = [e for e in earnings if (e[0].date() - today).days <= 3]
    if imminent:
        print("🔔 3天内有财报:")
        for dt, timing, ticker, info in imminent:
            print(f"   - {ticker}: {dt.strftime('%m/%d')} {timing}")
        print("   → 考虑是否需要减仓或对冲期权风险")
    else:
        print("✓ 3天内无财报发布")

    print()
    print("提示: 财报前后波动较大，请提前做好仓位管理")


if __name__ == "__main__":
    main()
