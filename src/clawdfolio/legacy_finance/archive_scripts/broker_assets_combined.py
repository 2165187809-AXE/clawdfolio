#!/usr/bin/env python3
"""Combine LongPort(长桥) + moomoo(OpenD) US assets and output ONE text message.

Outputs:
- 合计：净资产/现金/持仓市值/当日盈亏（USD）
- 分别：长桥、moomoo

Notes:
- LongPort 侧：净资产/现金来自 account_balance("USD")；持仓市值/当日盈亏按可获取到报价的美股股票/ETF 计算（期权默认不计）。
- moomoo 侧：用 OpenD Trade 数据 accinfo_query/position_list_query（不依赖购买 US 行情）。

Requires:
- longport SDK installed (pip: longport)
- futu-api installed (pip: futu-api)
- moomoo OpenD running locally on 127.0.0.1:11111 and Connected
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime


def _run_py(path: str) -> dict:
    p = subprocess.run([sys.executable, path], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f"failed: {path}")
    # last JSON line
    lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.startswith("{") and ln.endswith("}"):
            return json.loads(ln)
    raise RuntimeError(f"no json from {path}")


def _fmt(x) -> str:
    return f"{float(x):,.2f}"


def main() -> None:
    # --- LongPort summary (USD)
    lp = _run_py("scripts/longport_assets_summary.py")
    lp_net = float(lp.get("net_assets_usd") or 0.0)
    lp_cash = float(lp.get("cash_usd") or 0.0)
    lp_mv = float(lp.get("holdings_mkt_value_usd") or 0.0)
    lp_pnl = float(lp.get("day_pnl_usd") or 0.0)

    # --- moomoo summary (USD) via futu-api
    from futu.common import ft_logger

    ft_logger.logger.console_level = 50  # CRITICAL

    from futu import (
        OpenSecTradeContext,
        TrdMarket,
        TrdEnv,
        Currency,
        SecurityFirm,
        RET_OK,
    )

    trd = OpenSecTradeContext(
        filter_trdmarket=TrdMarket.US,
        host="127.0.0.1",
        port=11111,
        security_firm=SecurityFirm.FUTUINC,
    )

    try:
        ret, funds = trd.accinfo_query(trd_env=TrdEnv.REAL, currency=Currency.USD)
        if ret != RET_OK:
            raise RuntimeError(f"moomoo accinfo_query failed: {funds}")

        # single row
        total_assets = float(funds.iloc[0].get("total_assets", 0.0))
        cash = float(funds.iloc[0].get("cash", 0.0))
        mv = float(funds.iloc[0].get("market_val", 0.0))

        ret, pos = trd.position_list_query(trd_env=TrdEnv.REAL, position_market=TrdMarket.US)
        if ret != RET_OK:
            raise RuntimeError(f"moomoo position_list_query failed: {pos}")

        mo_pnl = 0.0
        if "today_pl_val" in pos.columns:
            try:
                mo_pnl = float(pos["today_pl_val"].fillna(0).sum())
            except Exception:
                mo_pnl = 0.0

    finally:
        trd.close()

    # --- Combine
    total_net = lp_net + total_assets
    total_cash = lp_cash + cash
    total_mv = lp_mv + mv
    total_pnl = lp_pnl + mo_pnl

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    msg = (
        f"合计(USD)：净资产 {_fmt(total_net)}｜现金 {_fmt(total_cash)}｜持仓市值 {_fmt(total_mv)}｜当日盈亏 {total_pnl:+,.2f}（{now}）\n"
        f"长桥(USD)：净资产 {_fmt(lp_net)}｜现金 {_fmt(lp_cash)}｜持仓市值 {_fmt(lp_mv)}｜当日盈亏 {lp_pnl:+,.2f}\n"
        f"moomoo(USD)：净资产 {_fmt(total_assets)}｜现金 {_fmt(cash)}｜持仓市值 {_fmt(mv)}｜当日盈亏 {mo_pnl:+,.2f}"
    )

    print(msg)


if __name__ == "__main__":
    main()
