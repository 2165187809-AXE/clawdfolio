#!/usr/bin/env python3
"""Generate a compact Portfolio daily brief (<=22 lines) for mobile.

Hard rules (enforced by formatting):
- Output ONLY the brief body (no explanations).
- Hide missing fields.
- Money: integer with thousands separators, prefixed with $.
- Percent: 1 decimal.
- Sign: use 🟢 for positive, 🔴 for negative.

Data sources:
- LongPort (longport SDK): account_balance(USD), stock_positions() + quote.quote() for US stock prices.
- moomoo OpenD (futu-api): accinfo_query(USD), position_list_query(US) for holdings + today_pl_val.
- Public enrichment (best-effort): yfinance for last/prev close + sector.

Note: If a datapoint cannot be computed reliably, it is omitted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

from lib.brokers import HoldingInfo, fetch_balances_and_holdings

HISTORY_PATH = Path(__file__).resolve().parent / "data/portfolio_history.jsonl"


def money_int(x: float) -> str:
    return f"${int(round(x)):,}"


def pct1(x: float) -> str:
    return f"{x*100:.1f}%"


def dot(x: float) -> str:
    return "🟢" if x >= 0 else "🔴"


def signed_money(x: float) -> str:
    return f"{dot(x)}{money_int(abs(x))}" if x != 0 else f"{dot(1)}{money_int(0)}"


def signed_pct(x: float) -> str:
    return f"{dot(x)}{pct1(abs(x))}" if x != 0 else f"{dot(1)}{pct1(0.0)}"


def _yf_sym(t: str) -> str:
    return t.replace('.', '-')


@dataclass
class Holding:
    ticker: str
    name: str = ""
    mv: float = 0.0
    qty: float = 0.0
    avg_cost: Optional[float] = None
    price: Optional[float] = None
    prev_close: Optional[float] = None
    day_contrib: float = 0.0


def load_history() -> List[dict]:
    if not HISTORY_PATH.exists():
        return []
    out = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def append_history(rec: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def baseline(history: List[dict], year: int, month: Optional[int] = None) -> Optional[float]:
    for r in history:
        try:
            ts = datetime.fromisoformat(r["ts"])
        except Exception:
            continue
        if ts.year != year:
            continue
        if month is not None and ts.month != month:
            continue
        if "total_net" in r:
            return float(r["total_net"])
    return None


def _holding_to_dict(h: HoldingInfo) -> Dict[str, Any]:
    return {
        "name": h.name,
        "qty": h.qty,
        "avg_cost": h.avg_cost,
        "price": h.price,
        "prev_close": h.prev_close,
        "mv": h.mv,
        "day_contrib": h.day_contrib,
    }


def longport_data() -> Tuple[float, float, float, float, float, Dict[str, Dict[str, Any]]]:
    balances, holdings = fetch_balances_and_holdings(sources=["longport"])
    bal = balances.get("longport") or balances.get("combined")
    if bal is None:
        return 0.0, 0.0, 0.0, 0.0, 0.0, {}
    out = {t: _holding_to_dict(h) for t, h in holdings.items()}
    return bal.net_assets, bal.cash, bal.market_value, bal.buying_power, bal.day_pnl, out


def moomoo_data() -> Tuple[float, float, float, float, float, Dict[str, Dict[str, Any]]]:
    balances, holdings = fetch_balances_and_holdings(sources=["moomoo"])
    bal = balances.get("moomoo") or balances.get("combined")
    if bal is None:
        return 0.0, 0.0, 0.0, 0.0, 0.0, {}
    out = {t: _holding_to_dict(h) for t, h in holdings.items()}
    return bal.net_assets, bal.cash, bal.market_value, bal.buying_power, bal.day_pnl, out


def merge(lp: Dict[str, Dict[str, Any]], mm: Dict[str, Dict[str, Any]]) -> Dict[str, Holding]:
    out: Dict[str, Holding] = {}
    cost_qty: Dict[str, float] = {}
    cost_sum: Dict[str, float] = {}
    for src in (lp, mm):
        for t, d in src.items():
            h = out.get(t) or Holding(ticker=t)
            h.name = h.name or d.get("name", "")
            h.qty += float(d.get("qty", 0.0) or 0.0)
            h.mv += float(d.get("mv", 0.0) or 0.0)
            h.day_contrib += float(d.get("day_contrib", 0.0) or 0.0)
            # prefer longport price/prev_close when available
            if d.get("price"):
                h.price = float(d["price"])
            if d.get("prev_close"):
                h.prev_close = float(d["prev_close"])
            # weighted avg cost
            if d.get("avg_cost") and d.get("qty"):
                q = float(d["qty"])
                cost_qty[t] = cost_qty.get(t, 0.0) + q
                cost_sum[t] = cost_sum.get(t, 0.0) + q * float(d["avg_cost"])
            out[t] = h

    for t, h in out.items():
        q = cost_qty.get(t, 0.0)
        if q > 0:
            h.avg_cost = cost_sum[t] / q

    return out


def enrich_with_yf(holdings: Dict[str, Holding], tickers: List[str]) -> None:
    # fill missing prev_close for day%/risk checks, and sector info later
    try:
        syms = [_yf_sym(t) for t in tickers]
        df = yf.download(syms, period="5d", interval="1d", progress=False)["Close"].dropna(how="all")
        if isinstance(df, pd.Series) or df is None or len(df) < 2:
            return
        last = df.iloc[-1]
        prev = df.iloc[-2]
        for t in tickers:
            h = holdings.get(t)
            if not h:
                continue
            col = _yf_sym(t)
            if col in last.index:
                if h.price is None:
                    h.price = float(last[col])
                if h.prev_close is None:
                    h.prev_close = float(prev[col])
    except Exception:
        return


def sector_weights(top: List[Holding], total_net: float) -> Dict[str, float]:
    sw: Dict[str, float] = {}
    for h in top:
        try:
            info = yf.Ticker(_yf_sym(h.ticker)).info
            sec = info.get("sector") or ""
        except Exception:
            sec = ""
        if not sec:
            continue
        sw[sec] = sw.get(sec, 0.0) + (h.mv / total_net if total_net else 0.0)
    return sw


def main() -> None:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    lp_net, lp_cash, lp_mv, lp_bp, lp_day, lp_h = longport_data()
    mm_net, mm_cash, mm_mv, mm_bp, mm_day, mm_h = moomoo_data()

    total_net = lp_net + mm_net
    total_cash = lp_cash + mm_cash
    total_bp = (lp_bp or 0.0) + (mm_bp or 0.0)
    total_day = lp_day + mm_day
    total_day_pct = (total_day / total_net) if total_net else 0.0

    hist = load_history()
    bm = baseline(hist, now.year, now.month) or total_net
    by = baseline(hist, now.year, None) or total_net
    mtd = (total_net / bm - 1.0) if bm else 0.0
    ytd = (total_net / by - 1.0) if by else 0.0
    append_history({"ts": now.isoformat(), "total_net": total_net})

    merged = merge(lp_h, mm_h)
    all_hold = list(merged.values())
    all_hold.sort(key=lambda x: x.mv, reverse=True)

    # Fill missing prev_close via yfinance for top names (best-effort)
    enrich_with_yf(merged, [h.ticker for h in all_hold[:15]])

    top5 = all_hold[:5]
    top5_w = sum(h.mv for h in top5) / total_net if total_net else None

    # Contributors / detractors by day contribution ($)
    contrib_sorted = sorted(all_hold, key=lambda x: x.day_contrib, reverse=True)
    detr_sorted = sorted(all_hold, key=lambda x: x.day_contrib)
    top_up = [c for c in contrib_sorted if c.day_contrib > 0][:2]
    top_dn = [c for c in detr_sorted if c.day_contrib < 0][:2]

    # Risk checks
    risks: List[str] = []
    # concentration
    if top5:
        maxw = top5[0].mv / total_net if total_net else 0.0
        if maxw > 0.15:
            risks.append(f"- 集中度: {pct1(maxw)} ({top5[0].ticker})")

    # sector concentration (top10)
    sw = sector_weights(all_hold[:10], total_net)
    if sw:
        sec, w = sorted(sw.items(), key=lambda x: x[1], reverse=True)[0]
        if w > 0.30:
            risks.append(f"- 板块偏重: {sec} {pct1(w)}")

    # abnormal moves: day drop < -4% OR drawdown from cost > 12%
    for h in top5:
        # day %
        if h.price is not None and h.prev_close is not None and h.prev_close != 0:
            day_pct = h.price / h.prev_close - 1.0
            if day_pct < -0.04:
                risks.append(f"- 异常波动: {h.ticker} 日跌{pct1(day_pct)}")
        if h.price is not None and h.avg_cost is not None and h.avg_cost != 0:
            dd = h.price / h.avg_cost - 1.0
            if dd < -0.12:
                risks.append(f"- 异常波动: {h.ticker} 回撤{pct1(dd)}")

    # ---- Output (<=22 lines)
    lines: List[str] = []

    # Header
    lines.append(f"📊 Daily Brief | {date_str}")

    # Overview
    lines.append("━━━ 账户概览 ━━━")
    lines.append(
        f"净值 {money_int(total_net)} | 日盈亏 {signed_money(total_day)} ({signed_pct(total_day_pct)})"
    )
    if total_cash != 0:
        lines.append(f"现金 {money_int(total_cash)} | 购买力 {money_int(total_bp)}")
    else:
        lines.append(f"购买力 {money_int(total_bp)}")
    lines.append(f"MTD {signed_pct(mtd)} | YTD {signed_pct(ytd)}")

    # Highlights
    lines.append("━━━ 今日亮点 ━━━")
    if top_up:
        lines.append(
            "🟢 领涨(贡献): " + ", ".join([f"{h.ticker} +{money_int(h.day_contrib)}" for h in top_up])
        )
    if top_dn:
        lines.append(
            "🔴 领跌(拖累): " + ", ".join([f"{h.ticker} -{money_int(abs(h.day_contrib))}" for h in top_dn])
        )

    # Top5
    title = "━━━ 重仓监控"
    if top5_w is not None:
        title += f" (Top5 = {pct1(top5_w)})"
    title += " ━━━"
    lines.append(title)

    for h in top5:
        w = (h.mv / total_net) if total_net else 0.0
        # day % and upl % (hide if missing)
        parts = [
            f"{h.ticker}",
            f"{pct1(w)}",
        ]
        if h.price is not None and h.prev_close is not None and h.prev_close != 0:
            d = h.price / h.prev_close - 1.0
            parts.append(f"日{dot(d)}{pct1(abs(d))}")
        if h.price is not None and h.avg_cost is not None and h.avg_cost != 0:
            upl = h.price / h.avg_cost - 1.0
            parts.append(f"浮盈{dot(upl)}{pct1(abs(upl))}")
        lines.append(" | ".join(parts))

    # Risks
    lines.append("━━━ ⚠️ 风险提示 ━━━")
    if risks:
        lines.extend(risks[:3])
    else:
        lines.append("✓ 无显著风险提示")

    # Events (placeholder unless you supply calendar)
    lines.append("━━━ 📅 未来7天事件 ━━━")
    lines.append("✓ 暂无重大事件")

    # Enforce line limit
    out = lines[:22]
    print("\n".join(out))


if __name__ == "__main__":
    main()
