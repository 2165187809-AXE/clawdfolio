#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import datetime


def main():
    p = subprocess.run([sys.executable, "scripts/longport_assets_summary.py"], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(p.stderr.strip() or p.stdout.strip() or f"failed with code {p.returncode}")

    # The SDK may print a quote-package table to stdout before our JSON.
    # Parse the last JSON object from stdout.
    lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    json_line = None
    for ln in reversed(lines):
        if ln.startswith("{") and ln.endswith("}"):
            json_line = ln
            break
    if not json_line:
        raise SystemExit(p.stdout.strip() or "no json output")

    data = json.loads(json_line)

    net_assets = data.get("net_assets_usd")
    cash = data.get("cash_usd")
    holdings = data.get("holdings_mkt_value_usd")
    day_pnl = data.get("day_pnl_usd")

    if any(v is None for v in (net_assets, cash, holdings, day_pnl)):
        raise SystemExit("missing fields in summary")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # One-line message as requested
    msg = (
        f"长桥美股资产(USD)：净资产 {net_assets:,.2f}｜现金 {cash:,.2f}｜持仓市值 {holdings:,.2f}｜当日盈亏 {day_pnl:+,.2f}（{now}）"
    )
    print(msg)


if __name__ == "__main__":
    main()
