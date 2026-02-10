#!/usr/bin/env python3
"""生成综合账户报告 Excel（长桥 + moomoo）

输出：
- summary 资产汇总
- positions 股票持仓
- options 期权持仓
- orders 今日挂单
- today_deals 今日成交
- history_deals 最近7天成交
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from account_report import get_longport_data, get_moomoo_data


def _as_df(rows: List[Dict[str, Any]], columns: List[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    # 对齐列顺序
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def main():
    now = datetime.now()

    lp = get_longport_data()
    mm = get_moomoo_data()

    total_net = lp["net"] + mm["net"]
    total_cash = lp["cash"] + mm["cash"]
    total_bp = lp["buying_power"] + mm["buying_power"]

    all_stocks = lp["stocks"] + mm["stocks"]
    all_options = lp["options"] + mm["options"]
    all_orders = lp["today_orders"] + mm["today_orders"]
    all_today_deals = lp["today_deals"] + mm["today_deals"]
    all_history = lp["history_deals"] + mm["history_deals"]

    # 排序
    all_stocks.sort(key=lambda x: x.get("mv", x.get("qty", 0) * x.get("cost", 0)), reverse=True)
    all_history.sort(key=lambda x: x.get("time", ""), reverse=True)

    # summary
    summary_rows = [
        {"项目": "净资产", "长桥": lp["net"], "moomoo": mm["net"], "合计": total_net},
        {"项目": "现金", "长桥": lp["cash"], "moomoo": mm["cash"], "合计": total_cash},
        {"项目": "购买力", "长桥": lp["buying_power"], "moomoo": mm["buying_power"], "合计": total_bp},
    ]
    df_summary = pd.DataFrame(summary_rows)

    # positions
    df_positions = _as_df(
        all_stocks,
        ["symbol", "name", "qty", "cost", "mv", "broker", "market"],
    )

    # options
    df_options = _as_df(
        all_options,
        ["symbol", "name", "qty", "cost", "mv", "broker", "market"],
    )

    # orders
    df_orders = _as_df(
        all_orders,
        ["symbol", "side", "qty", "price", "status", "broker"],
    )

    # today deals
    df_today_deals = _as_df(
        all_today_deals,
        ["symbol", "side", "qty", "price", "broker"],
    )

    # history deals
    df_history = _as_df(
        all_history,
        ["time", "symbol", "side", "qty", "price", "broker"],
    )

    out_dir = Path(__file__).resolve().parent.parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"account_report_{now.strftime('%Y%m%d_%H%M')}.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="summary", index=False)
        df_positions.to_excel(writer, sheet_name="positions", index=False)
        df_options.to_excel(writer, sheet_name="options", index=False)
        df_orders.to_excel(writer, sheet_name="orders", index=False)
        df_today_deals.to_excel(writer, sheet_name="today_deals", index=False)
        df_history.to_excel(writer, sheet_name="history_deals", index=False)

    print(str(out_path))


if __name__ == "__main__":
    main()
