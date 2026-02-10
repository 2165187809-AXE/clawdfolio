#!/usr/bin/env python3
"""Moomoo (Futu OpenD) US assets snapshot + top holdings.

Requires:
- OpenD running on localhost (GUI OpenD is fine)
- futu-api installed

Outputs ONE message with:
- Total assets / cash / holdings market value (USD)
- Today P/L value (today_pl_val) if available
- Top 10 holdings by market_val (trade-side numbers)

This does NOT require purchasing US Securities quote package.
"""

import socket
import sys
from datetime import datetime

HOST = "127.0.0.1"
PORT = 11111


def _check_opend():
    """Fail fast if FutuOpenD is not reachable."""
    try:
        with socket.create_connection((HOST, PORT), timeout=2.0):
            pass
    except (OSError, TimeoutError):
        print("moomoo OpenD 未运行或不可达，跳过。", file=sys.stderr)
        sys.exit(1)


# Reduce futu-api console logs; we only want clean output.
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


def _get(df, key, default=None):
    try:
        if key in df.columns:
            return df.iloc[0][key]
    except Exception:
        pass
    return default


def _fmt_money(x) -> str:
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "N/A"


def main():
    _check_opend()
    trd_ctx = OpenSecTradeContext(
        filter_trdmarket=TrdMarket.US,
        host=HOST,
        port=PORT,
        security_firm=SecurityFirm.FUTUINC,  # moomoo US
    )

    try:
        # 1) Funds in USD
        ret, funds = trd_ctx.accinfo_query(trd_env=TrdEnv.REAL, currency=Currency.USD)
        if ret != RET_OK:
            raise RuntimeError(f"accinfo_query failed: {funds}")

        total_assets = _get(funds, "total_assets", 0.0)
        cash = _get(funds, "cash", 0.0)
        mkt_val = _get(funds, "market_val", 0.0)

        # 2) Positions (US) and top 10 holdings by market_val
        ret, pos = trd_ctx.position_list_query(trd_env=TrdEnv.REAL, position_market=TrdMarket.US)
        if ret != RET_OK:
            raise RuntimeError(f"position_list_query failed: {pos}")

        # today_pl_val is trade-side today P/L for the position (if available)
        try:
            top = pos.sort_values("market_val", ascending=False).head(10)
        except Exception:
            top = pos

        top_lines = []
        for _, r in top.iterrows():
            code = r.get("code")
            mv = r.get("market_val")
            qty = r.get("qty")
            tpn = r.get("today_pl_val")
            # code in futu is like US.AAPL; keep as-is
            part = f"{code} x{int(qty) if qty==qty else qty}={_fmt_money(mv)}"
            if tpn not in (None, "N/A"):
                try:
                    part += f"({_fmt_money(tpn)})"
                except Exception:
                    pass
            top_lines.append(part)

        today_pl_total = None
        try:
            if "today_pl_val" in pos.columns:
                today_pl_total = float(pos["today_pl_val"].fillna(0).sum())
        except Exception:
            today_pl_total = None

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        header = (
            f"moomoo美股资产(USD)：总资产 {_fmt_money(total_assets)}｜现金 {_fmt_money(cash)}｜持仓市值 {_fmt_money(mkt_val)}"
        )
        if today_pl_total is not None:
            header += f"｜当日盈亏 {_fmt_money(today_pl_total)}"
        header += f"（{now}）"

        # Keep message compact
        body = "｜".join(top_lines)
        print(header + "\nTop10持仓市值：" + body)

    finally:
        trd_ctx.close()


if __name__ == "__main__":
    main()
