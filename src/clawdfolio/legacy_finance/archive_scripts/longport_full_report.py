#!/usr/bin/env python3
"""长桥完整报告 - 账户、持仓(含期权)、交易记录

包含:
- 账户余额
- 股票持仓
- 期权持仓
- 今日订单/成交
- 历史成交 (最近7天)
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
from typing import Any, List, Optional

# Suppress SDK output
_null = io.StringIO()


def get_trade_context():
    from longport.openapi import Config, TradeContext
    cfg = Config.from_env()
    return TradeContext(cfg)


def format_money(x: float) -> str:
    return f"${x:,.2f}"


def format_qty(x: float) -> str:
    if x == int(x):
        return str(int(x))
    return f"{x:.2f}"


def main():
    with redirect_stdout(_null), redirect_stderr(_null):
        trade = get_trade_context()

    now = datetime.now()
    print(f"📊 长桥完整报告 ({now.strftime('%Y-%m-%d %H:%M')})")
    print("=" * 50)

    # ========== 1. 账户余额 ==========
    print("\n━━━ 账户余额 ━━━")
    try:
        with redirect_stdout(_null), redirect_stderr(_null):
            balances = trade.account_balance("USD")
        if balances:
            acc = balances[0]
            print(f"净资产: {format_money(float(acc.net_assets))}")
            print(f"现金: {format_money(float(acc.total_cash))}")
            print(f"购买力: {format_money(float(getattr(acc, 'buy_power', 0) or 0))}")
            print(f"冻结资金: {format_money(float(getattr(acc, 'frozen_cash', 0) or 0))}")
    except Exception as e:
        print(f"获取失败: {e}")

    # ========== 2. 股票持仓 ==========
    print("\n━━━ 股票持仓 ━━━")
    try:
        with redirect_stdout(_null), redirect_stderr(_null):
            pos = trade.stock_positions()

        stocks = []
        options = []

        for ch in getattr(pos, "channels", []):
            for p in getattr(ch, "positions", []):
                sym = str(getattr(p, "symbol", ""))
                qty = float(getattr(p, "quantity", 0))
                if abs(qty) < 1e-9:
                    continue

                mkt = str(getattr(p, "market", "")).split(".")[-1].upper()
                name = str(getattr(p, "symbol_name", ""))
                cost = float(getattr(p, "cost_price", 0) or 0)

                item = {
                    "symbol": sym,
                    "name": name,
                    "qty": qty,
                    "cost": cost,
                    "market": mkt,
                }

                # 判断是否为期权 (包含日期+C/P+行权价的格式)
                is_option = False
                if mkt == "US" and len(sym) > 10:
                    # 期权格式: AAPL240119C00150000.US
                    if any(c.isdigit() for c in sym[:-3]) and ("C" in sym.upper() or "P" in sym.upper()):
                        is_option = True

                if is_option:
                    options.append(item)
                else:
                    stocks.append(item)

        if stocks:
            print(f"{'代码':<10} {'名称':<15} {'数量':>8} {'成本':>10}")
            print("-" * 48)
            for s in stocks:
                sym = s["symbol"].replace(".US", "").replace(".HK", "")
                name = s["name"][:12] if s["name"] else ""
                print(f"{sym:<10} {name:<15} {format_qty(s['qty']):>8} {format_money(s['cost']):>10}")
        else:
            print("无股票持仓")

    except Exception as e:
        print(f"获取失败: {e}")
        options = []

    # ========== 3. 期权持仓 ==========
    print("\n━━━ 期权持仓 ━━━")
    if options:
        print(f"{'合约':<25} {'数量':>8} {'成本':>10}")
        print("-" * 48)
        for o in options:
            sym = o["symbol"].replace(".US", "")
            print(f"{sym:<25} {format_qty(o['qty']):>8} {format_money(o['cost']):>10}")
    else:
        print("无期权持仓")

    # ========== 4. 今日订单 ==========
    print("\n━━━ 今日订单 ━━━")
    try:
        with redirect_stdout(_null), redirect_stderr(_null):
            today_orders = trade.today_orders()

        if today_orders:
            print(f"{'代码':<10} {'方向':<6} {'数量':>8} {'价格':>10} {'状态':<10}")
            print("-" * 50)
            for o in today_orders[:10]:  # 最多显示10条
                sym = str(getattr(o, "symbol", "")).replace(".US", "")
                side = str(getattr(o, "side", ""))
                qty = float(getattr(o, "quantity", 0))
                price = float(getattr(o, "price", 0) or 0)
                status = str(getattr(o, "status", ""))

                side_cn = "买入" if "Buy" in side else ("卖出" if "Sell" in side else side)
                print(f"{sym:<10} {side_cn:<6} {format_qty(qty):>8} {format_money(price):>10} {status:<10}")
        else:
            print("今日无订单")
    except Exception as e:
        print(f"获取失败: {e}")

    # ========== 5. 今日成交 ==========
    print("\n━━━ 今日成交 ━━━")
    try:
        with redirect_stdout(_null), redirect_stderr(_null):
            today_exec = trade.today_executions()

        if today_exec:
            print(f"{'代码':<10} {'方向':<6} {'数量':>8} {'成交价':>10} {'时间':<10}")
            print("-" * 50)
            for e in today_exec[:10]:
                sym = str(getattr(e, "symbol", "")).replace(".US", "")
                side = str(getattr(e, "side", ""))
                qty = float(getattr(e, "quantity", 0))
                price = float(getattr(e, "price", 0))
                trade_time = getattr(e, "trade_done_at", "")

                side_cn = "买入" if "Buy" in side else ("卖出" if "Sell" in side else side)
                time_str = str(trade_time)[:10] if trade_time else ""
                print(f"{sym:<10} {side_cn:<6} {format_qty(qty):>8} {format_money(price):>10} {time_str:<10}")
        else:
            print("今日无成交")
    except Exception as e:
        print(f"获取失败: {e}")

    # ========== 6. 历史成交 (最近7天) ==========
    print("\n━━━ 最近7天成交 ━━━")
    try:
        from longport.openapi import TopicType

        end = datetime.now()
        start = end - timedelta(days=7)

        with redirect_stdout(_null), redirect_stderr(_null):
            history = trade.history_executions(
                symbol=None,
                start_at=start,
                end_at=end,
            )

        if history:
            print(f"{'日期':<12} {'代码':<10} {'方向':<6} {'数量':>8} {'成交价':>10}")
            print("-" * 52)
            for h in history[:15]:  # 最多显示15条
                sym = str(getattr(h, "symbol", "")).replace(".US", "")
                side = str(getattr(h, "side", ""))
                qty = float(getattr(h, "quantity", 0))
                price = float(getattr(h, "price", 0))
                trade_time = getattr(h, "trade_done_at", None)

                side_cn = "买入" if "Buy" in side else ("卖出" if "Sell" in side else side)
                date_str = trade_time.strftime("%m-%d %H:%M") if trade_time else ""
                print(f"{date_str:<12} {sym:<10} {side_cn:<6} {format_qty(qty):>8} {format_money(price):>10}")

            if len(history) > 15:
                print(f"... 还有 {len(history) - 15} 条记录")
        else:
            print("最近7天无成交记录")
    except Exception as e:
        print(f"获取失败: {e}")

    print("\n" + "=" * 50)
    print(f"报告生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
