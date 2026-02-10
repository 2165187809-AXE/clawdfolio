#!/usr/bin/env python3
"""moomoo 完整报告 - 账户、持仓(含期权)、交易记录

包含:
- 账户余额
- 股票持仓
- 期权持仓
- 今日订单/成交
- 历史成交
"""

from __future__ import annotations

import socket
import sys
from datetime import datetime, timedelta
from typing import Any, List

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


# Suppress futu logs
from futu.common import ft_logger
ft_logger.logger.console_level = 50

from futu import (
    OpenSecTradeContext,
    TrdMarket,
    TrdEnv,
    Currency,
    SecurityFirm,
    RET_OK,
)


def format_money(x: float) -> str:
    return f"${x:,.2f}"


def safe_float(val, default=0.0) -> float:
    """Safely convert value to float."""
    if val is None or val == "N/A" or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def format_qty(x: float) -> str:
    if x == int(x):
        return str(int(x))
    return f"{x:.2f}"


def main():
    _check_opend()
    now = datetime.now()
    print(f"📊 moomoo 完整报告 ({now.strftime('%Y-%m-%d %H:%M')})")
    print("=" * 50)

    trd = OpenSecTradeContext(
        filter_trdmarket=TrdMarket.US,
        host=HOST,
        port=PORT,
        security_firm=SecurityFirm.FUTUINC,
    )

    try:
        # ========== 1. 账户余额 ==========
        print("\n━━━ 账户余额 ━━━")
        ret, funds = trd.accinfo_query(trd_env=TrdEnv.REAL, currency=Currency.USD)
        if ret == RET_OK and not funds.empty:
            row = funds.iloc[0]
            print(f"总资产: {format_money(safe_float(row.get('total_assets', 0)))}")
            print(f"现金: {format_money(safe_float(row.get('cash', 0)))}")
            print(f"持仓市值: {format_money(safe_float(row.get('market_val', 0)))}")
            print(f"购买力: {format_money(safe_float(row.get('power', 0) or 0))}")
            # Note: account-level only has realized_pl (cumulative). today_pl_val comes from positions (computed below).
            print(f"未实现盈亏: {format_money(safe_float(row.get('unrealized_pl', 0) or 0))}")
        else:
            print("获取失败")

        # ========== 2. 股票/期权持仓 ==========
        # Compute today's P&L from position-level data (account-level only has cumulative realized_pl)
        print("\n━━━ 股票持仓 ━━━")
        ret, pos = trd.position_list_query(trd_env=TrdEnv.REAL, position_market=TrdMarket.US)

        stocks = []
        options = []

        if ret == RET_OK and not pos.empty:
            # Print daily P&L from position-level today_pl_val
            if "today_pl_val" in pos.columns:
                daily_pl = pos["today_pl_val"].fillna(0).sum()
                print(f"当日盈亏: {format_money(daily_pl)}")

            for _, row in pos.iterrows():
                code = str(row.get("code", ""))
                name = str(row.get("stock_name", ""))
                qty = safe_float(row.get("qty", 0))
                cost = safe_float(row.get("cost_price", 0) or 0)
                mv = safe_float(row.get("market_val", 0) or 0)
                pl = safe_float(row.get("pl_val", 0) or 0)
                today_pl = safe_float(row.get("today_pl_val", 0) or 0)

                item = {
                    "code": code,
                    "name": name,
                    "qty": qty,
                    "cost": cost,
                    "mv": mv,
                    "pl": pl,
                    "today_pl": today_pl,
                }

                # 判断期权 (代码包含 C 或 P 且较长)
                ticker = code.replace("US.", "")
                if len(ticker) > 10 and any(c.isdigit() for c in ticker):
                    options.append(item)
                else:
                    stocks.append(item)

            if stocks:
                print(f"{'代码':<10} {'名称':<12} {'数量':>6} {'成本':>10} {'市值':>10} {'盈亏':>10}")
                print("-" * 65)
                for s in stocks:
                    code = s["code"].replace("US.", "")
                    name = s["name"][:10] if s["name"] else ""
                    pl_sign = "+" if s["pl"] >= 0 else ""
                    print(f"{code:<10} {name:<12} {format_qty(s['qty']):>6} {format_money(s['cost']):>10} {format_money(s['mv']):>10} {pl_sign}{format_money(s['pl']):>9}")
            else:
                print("无股票持仓")
        else:
            print("获取失败")

        # ========== 3. 期权持仓 ==========
        print("\n━━━ 期权持仓 ━━━")
        if options:
            print(f"{'合约':<20} {'数量':>6} {'成本':>10} {'市值':>10} {'盈亏':>10}")
            print("-" * 60)
            for o in options:
                code = o["code"].replace("US.", "")
                pl_sign = "+" if o["pl"] >= 0 else ""
                print(f"{code:<20} {format_qty(o['qty']):>6} {format_money(o['cost']):>10} {format_money(o['mv']):>10} {pl_sign}{format_money(o['pl']):>9}")
        else:
            print("无期权持仓")

        # ========== 4. 今日订单 ==========
        print("\n━━━ 今日订单 ━━━")
        ret, orders = trd.order_list_query(trd_env=TrdEnv.REAL)
        if ret == RET_OK and not orders.empty:
            print(f"{'代码':<10} {'方向':<6} {'数量':>8} {'价格':>10} {'状态':<15}")
            print("-" * 55)
            for _, row in orders.head(10).iterrows():
                code = str(row.get("code", "")).replace("US.", "")
                side = str(row.get("trd_side", ""))
                qty = safe_float(row.get("qty", 0))
                price = safe_float(row.get("price", 0))
                status = str(row.get("order_status", ""))

                side_cn = "买入" if "BUY" in side.upper() else ("卖出" if "SELL" in side.upper() else side)
                print(f"{code:<10} {side_cn:<6} {format_qty(qty):>8} {format_money(price):>10} {status:<15}")
        else:
            print("今日无订单")

        # ========== 5. 今日成交 ==========
        print("\n━━━ 今日成交 ━━━")
        ret, deals = trd.deal_list_query(trd_env=TrdEnv.REAL)
        if ret == RET_OK and not deals.empty:
            print(f"{'代码':<10} {'方向':<6} {'数量':>8} {'成交价':>10} {'时间':<10}")
            print("-" * 50)
            for _, row in deals.head(10).iterrows():
                code = str(row.get("code", "")).replace("US.", "")
                side = str(row.get("trd_side", ""))
                qty = safe_float(row.get("qty", 0))
                price = safe_float(row.get("price", 0))
                time_str = str(row.get("create_time", ""))[:16]

                side_cn = "买入" if "BUY" in side.upper() else ("卖出" if "SELL" in side.upper() else side)
                print(f"{code:<10} {side_cn:<6} {format_qty(qty):>8} {format_money(price):>10} {time_str:<10}")
        else:
            print("今日无成交")

        # ========== 6. 历史成交 ==========
        print("\n━━━ 历史成交 (最近7天) ━━━")
        end = now
        start = now - timedelta(days=7)
        ret, history = trd.history_deal_list_query(
            trd_env=TrdEnv.REAL,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )
        if ret == RET_OK and not history.empty:
            print(f"{'日期':<12} {'代码':<10} {'方向':<6} {'数量':>8} {'成交价':>10}")
            print("-" * 52)
            for _, row in history.head(15).iterrows():
                code = str(row.get("code", "")).replace("US.", "")
                side = str(row.get("trd_side", ""))
                qty = safe_float(row.get("qty", 0))
                price = safe_float(row.get("price", 0))
                time_str = str(row.get("create_time", ""))[:10]

                side_cn = "买入" if "BUY" in side.upper() else ("卖出" if "SELL" in side.upper() else side)
                print(f"{time_str:<12} {code:<10} {side_cn:<6} {format_qty(qty):>8} {format_money(price):>10}")

            if len(history) > 15:
                print(f"... 还有 {len(history) - 15} 条记录")
        else:
            print("最近7天无成交记录")

    finally:
        trd.close()

    print("\n" + "=" * 50)
    print(f"报告生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
