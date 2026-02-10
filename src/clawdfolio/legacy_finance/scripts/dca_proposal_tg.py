#!/usr/bin/env python3
"""Daily DCA / add-position proposal (Telegram-friendly, confirmation required).

Outputs ONLY one Markdown ```text``` block.
Rules:
- US stocks/ETFs only
- Cash-only (no margin)
- Daily total < max_budget (from config)
- Limit price = Bid1 if available (Yahoo/yfinance). If missing, mark DATA_MISSING.
- No fractional shares; shares rounded DOWN (floor) to avoid over-budget.
- Prefer broker with more cash.

This script does NOT place orders.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.brokers import fetch_balances
from lib.fmt import fmt_money, clamp_line
from lib.market import bid1_price

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

MAX_LINES = 22
MAX_COLS = 88


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    cfg = load_config()
    dca_cfg = cfg.get("dca", {})

    daily_budget = dca_cfg.get("daily_budget", 2000.0)
    max_budget = dca_cfg.get("max_budget", 5000.0)
    allocation = dca_cfg.get("allocation", {"QQQ": 0.7, "VOO": 0.3})

    ds = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Fetch cash from both brokers
    balances = fetch_balances()
    lp_cash = balances.get("longport", balances["combined"]).cash if "longport" in balances else 0.0
    mm_cash = balances.get("moomoo", balances["combined"]).cash if "moomoo" in balances else 0.0

    # Pick broker with more cash
    if lp_cash >= mm_cash:
        use_name, use_cash = "LongPort", lp_cash
    else:
        use_name, use_cash = "moomoo", mm_cash

    budget = min(daily_budget, max_budget, use_cash)

    plan = list(allocation.items())

    lines: List[str] = []
    lines.append("```text")
    lines.append(f"📊 DCA Proposal | {ds}")
    lines.append(f"💼 Broker Cash  LongPort {fmt_money(lp_cash)}  moomoo {fmt_money(mm_cash)}")
    lines.append(f"💼 Use          {use_name} (cash higher)")
    lines.append(f"💼 Budget       {fmt_money(budget)} (< {fmt_money(max_budget)})")

    lines.append("🧱 Orders (LIMIT@Bid1, shares=floor)")

    total_est = 0.0
    for tkr, w in plan:
        amt = budget * w
        bid, src = bid1_price(tkr)
        if bid is None:
            lines.append(f"DATA_MISSING {tkr} Bid1 {src}")
            continue
        # FIX: use floor() instead of round() to prevent over-budget
        sh = math.floor(amt / bid)
        if sh <= 0:
            lines.append(f"- {tkr}: 单价 ${bid:.2f} 超出分配额 ${amt:.0f}，跳过")
            continue
        est = sh * bid
        total_est += est
        lines.append(f"BUY {tkr:<4} {sh:>3} sh  LMT {bid:,.2f}  est {fmt_money(est, 2)}  src={src}")

    unallocated = max(budget - total_est, 0.0)
    utilization = (total_est / budget * 100) if budget > 0 else 0.0
    lines.append(f"💰 Estimated    {fmt_money(total_est, 2)} / {fmt_money(budget)}")
    lines.append(f"📐 Utilization  {utilization:.1f}%  Unallocated {fmt_money(unallocated, 2)}")

    lines.append("🛡️ Notes")
    lines.append("- Cash-only; no margin; confirm required")
    lines.append("🎯 Reply")
    lines.append("- 回复：确认1 / 取消 / 调整(例如 QQQ 5股, VOO 2股)")
    lines.append("- 我将回传同一订单，等待你回复：确认2 才会执行下单")
    lines.append("```")

    out = [clamp_line(x, MAX_COLS) for x in lines]
    print("\n".join(out[:MAX_LINES]))


if __name__ == "__main__":
    main()
