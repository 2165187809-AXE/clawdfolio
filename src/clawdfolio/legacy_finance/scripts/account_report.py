#!/usr/bin/env python3
"""综合账户报告 - 长桥 + moomoo 合并

一个脚本输出所有信息：
- 总资产汇总
- 全部持仓（股票+期权）
- 今日交易
- 最近成交记录
"""

from __future__ import annotations

import io
import socket
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from lib.env_loader import load_longport_env
from lib.fmt import fmt_change, fmt_money, fmt_pct

_null = io.StringIO()


def safe_float(val, default=0.0) -> float:
    if val is None or val == "N/A" or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_trade_time(val: Any) -> Tuple[int, str]:
    """Return (sort_ts, display_text) for mixed broker time formats."""
    if val is None:
        return 0, ""

    dt: Optional[datetime] = None
    if isinstance(val, datetime):
        dt = val
    else:
        raw = str(val).strip()
        if not raw:
            return 0, ""
        cands = [raw, raw.replace("/", "-")]
        for s in cands:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                break
            except Exception:
                continue
        if dt is None:
            for s in cands:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(s, fmt)
                        break
                    except Exception:
                        continue
                if dt is not None:
                    break
        if dt is None:
            return 0, raw[:16]

    try:
        sort_ts = int(dt.timestamp())
    except Exception:
        sort_ts = 0

    if (dt.hour, dt.minute, dt.second) == (0, 0, 0):
        disp = dt.strftime("%Y-%m-%d")
    else:
        disp = dt.strftime("%Y-%m-%d %H:%M")
    return sort_ts, disp


# ==================== 长桥 ====================
def get_longport_data() -> Dict[str, Any]:
    result = {
        "net": 0, "cash": 0, "buying_power": 0,
        "stocks": [], "options": [],
        "today_orders": [], "today_deals": [], "history_deals": [],
        "connected": False,
        "error": None,
    }

    # Ensure LongPort creds are available even when running under cron/daemon
    # (those environments typically don't source ~/.zshrc).
    load_longport_env()

    try:
        from longport.openapi import Config, TradeContext

        with redirect_stdout(_null), redirect_stderr(_null):
            cfg = Config.from_env()
            trade = TradeContext(cfg)
        result["connected"] = True

        # 账户余额
        with redirect_stdout(_null), redirect_stderr(_null):
            balances = trade.account_balance("USD")
        if balances:
            acc = balances[0]
            result["net"] = float(acc.net_assets)
            result["cash"] = float(acc.total_cash)
            result["buying_power"] = float(getattr(acc, 'buy_power', 0) or 0)

        # 持仓
        with redirect_stdout(_null), redirect_stderr(_null):
            pos = trade.stock_positions()

        for ch in getattr(pos, "channels", []):
            for p in getattr(ch, "positions", []):
                sym = str(getattr(p, "symbol", ""))
                qty = float(getattr(p, "quantity", 0))
                if abs(qty) < 1e-9:
                    continue

                mkt = str(getattr(p, "market", "")).split(".")[-1].upper()
                cost_price = float(getattr(p, "cost_price", 0) or 0)
                item = {
                    "symbol": sym.replace(".US", "").replace(".HK", ""),
                    "name": str(getattr(p, "symbol_name", "")),
                    "qty": qty,
                    "cost": cost_price,
                    "cost_value": abs(qty) * cost_price,
                    "broker": "长桥",
                    "market": mkt,
                }

                # 判断期权
                is_option = mkt == "US" and len(sym) > 10 and any(c.isdigit() for c in sym[:-3])
                if is_option:
                    result["options"].append(item)
                else:
                    result["stocks"].append(item)

        # 今日订单
        try:
            with redirect_stdout(_null), redirect_stderr(_null):
                orders = trade.today_orders()
            for o in orders[:10]:
                result["today_orders"].append({
                    "symbol": str(getattr(o, "symbol", "")).replace(".US", ""),
                    "side": "买入" if "Buy" in str(getattr(o, "side", "")) else "卖出",
                    "qty": float(getattr(o, "quantity", 0)),
                    "price": float(getattr(o, "price", 0) or 0),
                    "status": str(getattr(o, "status", "")),
                    "broker": "长桥",
                })
        except Exception:
            pass

        # 历史成交
        try:
            end = datetime.now()
            start = end - timedelta(days=7)
            with redirect_stdout(_null), redirect_stderr(_null):
                history = trade.history_executions(symbol=None, start_at=start, end_at=end)
            for h in history[:10]:
                trade_time = getattr(h, "trade_done_at", None)
                sort_ts, display_time = _parse_trade_time(trade_time)
                result["history_deals"].append({
                    "time": display_time,
                    "sort_ts": sort_ts,
                    "symbol": str(getattr(h, "symbol", "")).replace(".US", ""),
                    "side": "买入" if "Buy" in str(getattr(h, "side", "")) else "卖出",
                    "qty": float(getattr(h, "quantity", 0)),
                    "price": float(getattr(h, "price", 0)),
                    "broker": "长桥",
                })
        except Exception:
            pass

    except Exception as e:
        # Don't crash the whole report; just mark longport unavailable.
        result["connected"] = False
        result["error"] = str(e)

    return result


# ==================== moomoo ====================
def get_moomoo_data() -> Dict[str, Any]:
    result = {
        "net": 0, "cash": 0, "buying_power": 0,
        "stocks": [], "options": [],
        "today_orders": [], "today_deals": [], "history_deals": [],
        "error": None,
    }

    try:
        # Fail fast if FutuOpenD is not reachable
        with socket.create_connection(("127.0.0.1", 11111), timeout=2.0):
            pass

        from futu.common import ft_logger
        ft_logger.logger.console_level = 50
        from futu import OpenSecTradeContext, TrdMarket, TrdEnv, Currency, SecurityFirm, RET_OK

        trd = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.US,
            host="127.0.0.1", port=11111,
            security_firm=SecurityFirm.FUTUINC,
        )

        try:
            # 账户余额
            ret, funds = trd.accinfo_query(trd_env=TrdEnv.REAL, currency=Currency.USD)
            if ret == RET_OK and not funds.empty:
                row = funds.iloc[0]
                result["net"] = safe_float(row.get("total_assets"))
                result["cash"] = safe_float(row.get("cash"))
                result["buying_power"] = safe_float(row.get("power"))

            # 持仓
            ret, pos = trd.position_list_query(trd_env=TrdEnv.REAL, position_market=TrdMarket.US)
            if ret == RET_OK and not pos.empty:
                for _, row in pos.iterrows():
                    code = str(row.get("code", "")).replace("US.", "")
                    qty = safe_float(row.get("qty"))
                    if abs(qty) < 1e-9:
                        continue

                    item = {
                        "symbol": code,
                        "name": str(row.get("stock_name", "")),
                        "qty": qty,
                        "cost": safe_float(row.get("cost_price")),
                        "mv": safe_float(row.get("market_val")),
                        "pl": safe_float(row.get("pl_val")),
                        "today_pl": safe_float(row.get("today_pl_val")),
                        "broker": "moomoo",
                    }

                    is_option = len(code) > 10 and any(c.isdigit() for c in code)
                    if is_option:
                        result["options"].append(item)
                    else:
                        result["stocks"].append(item)

            # 今日订单
            ret, orders = trd.order_list_query(trd_env=TrdEnv.REAL)
            if ret == RET_OK and not orders.empty:
                for _, row in orders.head(10).iterrows():
                    result["today_orders"].append({
                        "symbol": str(row.get("code", "")).replace("US.", ""),
                        "side": "买入" if "BUY" in str(row.get("trd_side", "")).upper() else "卖出",
                        "qty": safe_float(row.get("qty")),
                        "price": safe_float(row.get("price")),
                        "status": str(row.get("order_status", "")),
                        "broker": "moomoo",
                    })

            # 今日成交
            ret, deals = trd.deal_list_query(trd_env=TrdEnv.REAL)
            if ret == RET_OK and not deals.empty:
                for _, row in deals.head(10).iterrows():
                    result["today_deals"].append({
                        "symbol": str(row.get("code", "")).replace("US.", ""),
                        "side": "买入" if "BUY" in str(row.get("trd_side", "")).upper() else "卖出",
                        "qty": safe_float(row.get("qty")),
                        "price": safe_float(row.get("price")),
                        "broker": "moomoo",
                    })

            # 历史成交
            end = datetime.now()
            start = end - timedelta(days=7)
            ret, history = trd.history_deal_list_query(
                trd_env=TrdEnv.REAL,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
            )
            if ret == RET_OK and not history.empty:
                for _, row in history.head(10).iterrows():
                    sort_ts, display_time = _parse_trade_time(row.get("create_time", ""))
                    result["history_deals"].append({
                        "time": display_time,
                        "sort_ts": sort_ts,
                        "symbol": str(row.get("code", "")).replace("US.", ""),
                        "side": "买入" if "BUY" in str(row.get("trd_side", "")).upper() else "卖出",
                        "qty": safe_float(row.get("qty")),
                        "price": safe_float(row.get("price")),
                        "broker": "moomoo",
                    })

        finally:
            trd.close()

    except Exception as e:
        # Keep moomoo errors silent, but record for future debugging if needed.
        result["error"] = str(e)

    return result


def main():
    now = datetime.now()

    # 获取数据
    lp = get_longport_data()
    mm = get_moomoo_data()

    # 合并计算
    total_net = lp["net"] + mm["net"]
    total_cash = lp["cash"] + mm["cash"]
    total_bp = lp["buying_power"] + mm["buying_power"]

    all_stocks = lp["stocks"] + mm["stocks"]
    all_options = lp["options"] + mm["options"]
    all_orders = lp["today_orders"] + mm["today_orders"]
    all_today_deals = lp["today_deals"] + mm["today_deals"]
    all_history = lp["history_deals"] + mm["history_deals"]

    # 按市值排序股票
    all_stocks.sort(key=lambda x: x.get("mv", x.get("cost_value", x["qty"] * x["cost"])), reverse=True)

    print(f"📊 综合账户报告")
    print(f"生成时间: {now.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    # ========== 资产汇总 ==========
    print("\n💰 资产汇总")
    print("-" * 55)
    print(f"{'':12} {'长桥':>14} {'moomoo':>14} {'合计':>14}")
    print(f"{'净资产':12} {fmt_money(lp['net'], 2):>14} {fmt_money(mm['net'], 2):>14} {fmt_money(total_net, 2):>14}")
    print(f"{'现金':12} {fmt_money(lp['cash'], 2):>14} {fmt_money(mm['cash'], 2):>14} {fmt_money(total_cash, 2):>14}")
    print(f"{'购买力':12} {fmt_money(lp['buying_power'], 2):>14} {fmt_money(mm['buying_power'], 2):>14} {fmt_money(total_bp, 2):>14}")
    if lp["cash"] < 0 or mm["cash"] < 0 or total_cash < 0:
        who = []
        if lp["cash"] < 0:
            who.append("长桥")
        if mm["cash"] < 0:
            who.append("moomoo")
        who_text = "、".join(who) if who else "账户"
        print(f"注: {who_text}现金为负，通常表示融资/保证金占用，不是数据错误。")

    # ========== 股票持仓 ==========
    print(f"\n📈 股票持仓 ({len(all_stocks)}只)")
    print("-" * 55)
    if all_stocks:
        print(f"{'代码':<8} {'券商':<6} {'数量':>6} {'成本':>10} {'盈亏':>12}")
        for s in all_stocks[:20]:
            sym = s["symbol"][:8]
            broker = s["broker"]
            qty = int(s["qty"]) if s["qty"] == int(s["qty"]) else s["qty"]
            cost = s["cost"]
            pl = s.get("pl", 0)
            pl_str = fmt_change(pl) if pl != 0 else "-"
            print(f"{sym:<8} {broker:<6} {qty:>6} {fmt_money(cost, 2):>10} {pl_str:>12}")
        if len(all_stocks) > 20:
            print(f"... 还有 {len(all_stocks) - 20} 只")
    else:
        print("无股票持仓")

    # ========== 期权持仓 ==========
    print(f"\n📜 期权持仓 ({len(all_options)}个)")
    print("-" * 55)
    if all_options:
        print(f"{'合约':<20} {'券商':<6} {'数量':>6} {'成本':>10}")
        for o in all_options:
            sym = o["symbol"][:20]
            broker = o["broker"]
            qty = int(o["qty"]) if o["qty"] == int(o["qty"]) else o["qty"]
            cost = o["cost"]
            print(f"{sym:<20} {broker:<6} {qty:>6} {fmt_money(cost, 2):>10}")
    else:
        print("无期权持仓")

    # ========== 今日订单 ==========
    print(f"\n📝 今日挂单 ({len(all_orders)}个)")
    print("-" * 55)
    if all_orders:
        print(f"{'代码':<10} {'方向':<4} {'数量':>6} {'价格':>10} {'券商':<6} {'状态'}")
        for o in all_orders[:10]:
            print(f"{o['symbol']:<10} {o['side']:<4} {int(o['qty']):>6} {fmt_money(o['price'], 2):>10} {o['broker']:<6} {o['status']}")
    else:
        print("今日无挂单")

    # ========== 今日成交 ==========
    print(f"\n✅ 今日成交 ({len(all_today_deals)}笔)")
    print("-" * 55)
    if all_today_deals:
        print(f"{'代码':<10} {'方向':<4} {'数量':>6} {'成交价':>10} {'券商':<6}")
        for d in all_today_deals:
            print(f"{d['symbol']:<10} {d['side']:<4} {int(d['qty']):>6} {fmt_money(d['price'], 2):>10} {d['broker']:<6}")
    else:
        print("今日无成交")

    # ========== 最近成交 ==========
    print(f"\n📅 最近7天成交")
    print("-" * 55)
    if all_history:
        # 按时间排序
        all_history.sort(key=lambda x: (x.get("sort_ts", 0), x.get("time", "")), reverse=True)
        print(f"{'日期':<16} {'代码':<10} {'方向':<4} {'数量':>6} {'价格':>10} {'券商':<6}")
        for h in all_history[:15]:
            print(f"{h['time']:<16} {h['symbol']:<10} {h['side']:<4} {int(h['qty']):>6} {fmt_money(h['price'], 2):>10} {h['broker']:<6}")
        if len(all_history) > 15:
            print(f"... 还有 {len(all_history) - 15} 笔")
    else:
        print("最近7天无成交")

    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
