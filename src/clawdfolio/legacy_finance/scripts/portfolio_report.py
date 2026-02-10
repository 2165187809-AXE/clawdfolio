#!/usr/bin/env python3
"""Daily portfolio report (LongPort + moomoo).

Design goal: ~30s read, actionable.

Data sources:
- LongPort (longport SDK): account_balance(USD), stock_positions() + quote.quote() for prices
- moomoo OpenD (futu-api): accinfo_query(USD), position_list_query(US)
- Benchmarks/prices/earnings/dividends: yfinance (best-effort, may be missing)

Caveats:
- MTD/YTD depend on local history file; first run initializes baselines.
- Sector/industry concentration: best-effort via yfinance info; may be missing.
"""

from __future__ import annotations

import json
import os
import socket
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from lib.brokers import suppress_stdio_fds
from lib.env_loader import load_longport_env

# -------- config
HISTORY_PATH = Path(__file__).resolve().parent / "data/portfolio_history.jsonl"
MOOMOO_HOST = "127.0.0.1"
MOOMOO_PORT = 11111


def fmt(x: float, digits: int = 2) -> str:
    try:
        return f"{x:,.{digits}f}"
    except Exception:
        return "N/A"


def fmt_pct(x: float, digits: int = 2) -> str:
    try:
        return f"{x*100:.{digits}f}%"
    except Exception:
        return "N/A"


@dataclass
class BrokerSummary:
    name: str
    net: float
    cash: float
    mv: float
    buying_power: float | None
    day_pnl: float


def longport_snapshot() -> Tuple[BrokerSummary, Dict[str, Dict[str, Any]]]:
    from longport.openapi import Config, TradeContext, QuoteContext
    import io

    load_longport_env()
    _null = io.StringIO()
    with suppress_stdio_fds():
        with redirect_stdout(_null), redirect_stderr(_null):
            cfg = Config.from_env()
            trade = TradeContext(cfg)
            quote = QuoteContext(cfg)

    with suppress_stdio_fds():
        with redirect_stdout(_null), redirect_stderr(_null):
            balances = trade.account_balance("USD")
    if not balances:
        return BrokerSummary("长桥", 0.0, 0.0, 0.0, 0.0, 0.0), {}
    acc = balances[0]
    net = float(acc.net_assets)
    cash = float(acc.total_cash)
    buying_power = float(getattr(acc, "buy_power", 0.0))

    with suppress_stdio_fds():
        with redirect_stdout(_null), redirect_stderr(_null):
            pos = trade.stock_positions()
    holdings: Dict[str, Dict[str, Any]] = {}

    for ch in getattr(pos, "channels", []):
        for p in getattr(ch, "positions", []):
            mkt = str(getattr(p, "market", "")).split(".")[-1].upper()
            if mkt not in ("US", "USA"):
                continue
            sym = str(getattr(p, "symbol"))
            # ignore options-like symbols
            if sym.endswith(".US") and any(c.isdigit() for c in sym[:-3]) and len(sym) > 10 and ("C" in sym or "P" in sym):
                continue
            qty = float(getattr(p, "quantity"))
            if abs(qty) < 1e-9:
                continue
            holdings[sym] = {
                "ticker": sym.replace(".US", ""),
                "name": str(getattr(p, "symbol_name", "")),
                "qty": qty,
                "cost": float(getattr(p, "cost_price", 0.0) or 0.0),
            }

    mv = 0.0
    day_pnl = 0.0

    if holdings:
        with suppress_stdio_fds():
            with redirect_stdout(_null), redirect_stderr(_null):
                quotes = quote.quote(list(holdings.keys()))
        qmap = {str(q.symbol): q for q in quotes}
        for sym, h in holdings.items():
            q = qmap.get(sym)
            if not q:
                continue
            last = float(q.last_done)
            prev = float(q.prev_close)
            h["price"] = last
            h["prev_close"] = prev
            h["mv"] = h["qty"] * last
            h["day_pnl"] = h["qty"] * (last - prev)
            mv += h["mv"]
            day_pnl += h["day_pnl"]

    return BrokerSummary("长桥", net, cash, mv, buying_power, day_pnl), holdings


def moomoo_snapshot() -> Tuple[BrokerSummary, Dict[str, Dict[str, Any]]]:
    # Fail fast if FutuOpenD is not reachable
    try:
        with socket.create_connection((MOOMOO_HOST, MOOMOO_PORT), timeout=2.0):
            pass
    except (OSError, TimeoutError):
        return BrokerSummary("moomoo", 0.0, 0.0, 0.0, None, 0.0), {}

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
        host=MOOMOO_HOST,
        port=MOOMOO_PORT,
        security_firm=SecurityFirm.FUTUINC,
    )

    try:
        ret, funds = trd.accinfo_query(trd_env=TrdEnv.REAL, currency=Currency.USD)
        if ret != RET_OK:
            raise RuntimeError(f"moomoo accinfo_query failed: {funds}")
        row = funds.iloc[0]
        net = float(row.get("total_assets", 0.0))
        cash = float(row.get("cash", 0.0))
        mv = float(row.get("market_val", 0.0))
        buying_power = float(row.get("power", 0.0)) if "power" in funds.columns else None

        ret, pos = trd.position_list_query(trd_env=TrdEnv.REAL, position_market=TrdMarket.US)
        if ret != RET_OK:
            raise RuntimeError(f"moomoo position_list_query failed: {pos}")

        holdings: Dict[str, Dict[str, Any]] = {}
        day_pnl_total = 0.0
        if "today_pl_val" in pos.columns:
            day_pnl_total = float(pos["today_pl_val"].fillna(0).sum())

        for _, r in pos.iterrows():
            code = str(r.get("code"))  # e.g. US.AAPL
            if not code.startswith("US."):
                continue
            ticker = code.split(".", 1)[1]
            holdings[ticker] = {
                "ticker": ticker,
                "name": str(r.get("stock_name", "")),
                "qty": float(r.get("qty", 0.0)),
                "cost": float(r.get("cost_price", 0.0) or 0.0),
                "price": float(r.get("nominal_price", 0.0) or 0.0),
                "mv": float(r.get("market_val", 0.0) or 0.0),
                "day_pnl": float(r.get("today_pl_val", 0.0) or 0.0),
                "upl": float(r.get("pl_val", 0.0) or 0.0),
                "upl_ratio": float(r.get("pl_ratio", 0.0) or 0.0) / 100.0 if r.get("pl_ratio") not in (None, "N/A") else None,
            }

        return BrokerSummary("moomoo", net, cash, mv, buying_power, day_pnl_total), holdings

    finally:
        trd.close()


def merge_holdings(lp: Dict[str, Dict[str, Any]], mm: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    # normalize longport key to ticker
    for sym, h in lp.items():
        t = h["ticker"]
        merged.setdefault(t, {"ticker": t, "sources": []})
        merged[t]["sources"].append("longport")
        merged[t]["name"] = merged[t].get("name") or h.get("name")
        merged[t]["qty"] = merged[t].get("qty", 0.0) + float(h.get("qty", 0.0))
        merged[t]["mv"] = merged[t].get("mv", 0.0) + float(h.get("mv", 0.0) or 0.0)
        merged[t]["day_pnl"] = merged[t].get("day_pnl", 0.0) + float(h.get("day_pnl", 0.0) or 0.0)
        # cost basis: keep weighted avg if possible
        if h.get("qty") and h.get("cost"):
            merged[t].setdefault("_cost_qty", 0.0)
            merged[t].setdefault("_cost_sum", 0.0)
            merged[t]["_cost_qty"] += float(h["qty"])
            merged[t]["_cost_sum"] += float(h["qty"]) * float(h["cost"])
        merged[t]["price"] = merged[t].get("price") or h.get("price")

    for t, h in mm.items():
        merged.setdefault(t, {"ticker": t, "sources": []})
        merged[t]["sources"].append("moomoo")
        merged[t]["name"] = merged[t].get("name") or h.get("name")
        merged[t]["qty"] = merged[t].get("qty", 0.0) + float(h.get("qty", 0.0))
        merged[t]["mv"] = merged[t].get("mv", 0.0) + float(h.get("mv", 0.0) or 0.0)
        merged[t]["day_pnl"] = merged[t].get("day_pnl", 0.0) + float(h.get("day_pnl", 0.0) or 0.0)
        if h.get("qty") and h.get("cost"):
            merged[t].setdefault("_cost_qty", 0.0)
            merged[t].setdefault("_cost_sum", 0.0)
            merged[t]["_cost_qty"] += float(h["qty"])
            merged[t]["_cost_sum"] += float(h["qty"]) * float(h["cost"])
        merged[t]["price"] = merged[t].get("price") or h.get("price")

    for t, h in merged.items():
        if h.get("_cost_qty"):
            h["avg_cost"] = h["_cost_sum"] / h["_cost_qty"]
        h.pop("_cost_qty", None)
        h.pop("_cost_sum", None)

    return merged


def load_history() -> List[dict]:
    if not HISTORY_PATH.exists():
        return []
    out = []
    with HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
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


def find_baseline(history: List[dict], key: str, y: int, m: int | None = None) -> float | None:
    # first record matching year (+ month)
    for r in history:
        try:
            ts = datetime.fromisoformat(r["ts"])
        except Exception:
            continue
        if ts.year != y:
            continue
        if m is not None and ts.month != m:
            continue
        if key in r:
            return float(r[key])
    return None


def benchmark_excess(port_daily: float, spy_daily: float, qqq_daily: float) -> str:
    # daily excess vs both
    return f"vsSPY {fmt_pct(port_daily-spy_daily)} / vsQQQ {fmt_pct(port_daily-qqq_daily)}"


def get_bench_returns() -> Tuple[float | None, float | None]:
    try:
        df = yf.download(["SPY", "QQQ"], period="5d", interval="1d", progress=False)["Close"]
        if isinstance(df, pd.Series):
            return None, None
        df = df.dropna()
        if len(df) < 2:
            return None, None
        r = df.pct_change().iloc[-1]
        return float(r.get("SPY")), float(r.get("QQQ"))
    except Exception:
        return None, None


def _yf_sym(t: str) -> str:
    # yfinance uses '-' for class shares like BRK-B
    return t.replace('.', '-')


def portfolio_beta_vol(tickers: List[str], weights: np.ndarray) -> Tuple[float | None, float | None, float | None]:
    # beta vs SPY and vol/drawdown from daily prices (best-effort)
    try:
        tick_yf = [_yf_sym(t) for t in tickers]
        px = yf.download(["SPY"] + tick_yf, period="3mo", interval="1d", progress=False)["Close"]
        px = px.dropna(how="all")
        if px is None or len(px) < 20:
            return None, None, None
        rets = px.pct_change().dropna()
        if "SPY" not in rets.columns:
            return None, None, None
        # keep only columns we actually have, with aligned weights
        cols = []
        aligned_w = []
        for i, c in enumerate(tick_yf):
            if c in rets.columns and i < len(weights):
                cols.append(c)
                aligned_w.append(weights[i])
        if len(cols) < 2:
            return None, None, None
        w = np.array(aligned_w)
        w = w / w.sum() if w.sum() else w
        spy = rets["SPY"].values
        port = rets[cols].values @ w
        beta = float(np.cov(port, spy)[0, 1] / np.var(spy)) if np.var(spy) > 0 else None
        vol20 = float(np.std(port[-20:]) * np.sqrt(252))
        cum = np.cumprod(1 + port)
        peak = np.maximum.accumulate(cum)
        dd = (cum / peak) - 1
        mdd = float(dd.min())
        return beta, vol20, mdd
    except Exception:
        return None, None, None


def sector_breakdown(tickers: List[str], weights: np.ndarray) -> Tuple[Dict[str, float], Dict[str, float]]:
    sector_w: Dict[str, float] = {}
    industry_w: Dict[str, float] = {}
    for t, w in zip(tickers, weights):
        try:
            info = yf.Ticker(_yf_sym(t)).info
            sec = info.get("sector") or "Unknown"
            ind = info.get("industry") or "Unknown"
        except Exception:
            sec, ind = "Unknown", "Unknown"
        sector_w[sec] = sector_w.get(sec, 0.0) + float(w)
        industry_w[ind] = industry_w.get(ind, 0.0) + float(w)
    return sector_w, industry_w


def next_events(tickers: List[str]) -> List[str]:
    lines = []
    for t in tickers:
        try:
            tk = yf.Ticker(_yf_sym(t))
            cal = tk.calendar
            earn = None
            if cal is not None and hasattr(cal, "empty") and not cal.empty:
                if "Earnings Date" in cal.index:
                    v = cal.loc["Earnings Date"].values
                    if len(v) > 0:
                        earn = v[0]
            if earn is not None and str(earn) != "nan":
                dt = pd.to_datetime(earn).to_pydatetime()
                days = (dt.date() - datetime.now().date()).days
                if -1 <= days <= 14:
                    lines.append(f"{t} 财报：{dt.date()} (D{days:+d})")
        except Exception:
            continue
    return lines[:10]


def main() -> None:
    now_local = datetime.now()

    lp_sum, lp_hold = longport_snapshot()
    mm_sum, mm_hold = moomoo_snapshot()

    total_net = lp_sum.net + mm_sum.net
    total_cash = lp_sum.cash + mm_sum.cash
    total_mv = lp_sum.mv + mm_sum.mv
    total_day_pnl = lp_sum.day_pnl + mm_sum.day_pnl
    daily_ret = total_day_pnl / total_net if total_net else 0.0

    # history for MTD/YTD
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    hist = load_history()
    baseline_m = find_baseline(hist, "total_net", now_local.year, now_local.month)
    baseline_y = find_baseline(hist, "total_net", now_local.year, None)
    if baseline_m is None:
        baseline_m = total_net
    if baseline_y is None:
        baseline_y = total_net

    mtd = (total_net / baseline_m - 1.0) if baseline_m else 0.0
    ytd = (total_net / baseline_y - 1.0) if baseline_y else 0.0

    append_history({"ts": datetime.now(timezone.utc).isoformat(), "total_net": total_net})

    # merged holdings
    merged = merge_holdings(lp_hold, mm_hold)
    # weights by MV
    items = [h for h in merged.values() if h.get("mv")]
    items.sort(key=lambda x: float(x.get("mv", 0.0)), reverse=True)

    top5 = items[:5]
    top10 = items[:10]

    top5_weight = sum(h["mv"] for h in top5) / total_net if total_net else 0.0
    max_weight = (top5[0]["mv"] / total_net) if (top5 and total_net) else 0.0

    tickers = [h["ticker"] for h in items[:20]]
    weights = np.array([h["mv"] for h in items[:20]], dtype=float)
    weights = weights / weights.sum() if weights.sum() else weights

    spy_r, qqq_r = get_bench_returns()
    bench = "vsSPY N/A / vsQQQ N/A" if spy_r is None or qqq_r is None else benchmark_excess(daily_ret, spy_r, qqq_r)

    beta, vol20, mdd = (None, None, None)
    if len(tickers) >= 2 and weights.size >= 2:
        beta, vol20, mdd = portfolio_beta_vol(tickers, weights)

    sector_w, industry_w = sector_breakdown([h["ticker"] for h in top10], np.array([h["mv"] for h in top10]) / (sum(h["mv"] for h in top10) or 1))
    # top sector/industry
    top_sector = sorted(sector_w.items(), key=lambda x: x[1], reverse=True)[:3]
    top_ind = sorted(industry_w.items(), key=lambda x: x[1], reverse=True)[:3]

    # contributors/detractors by day_pnl
    contrib = sorted(items, key=lambda x: float(x.get("day_pnl", 0.0)), reverse=True)
    detr = sorted(items, key=lambda x: float(x.get("day_pnl", 0.0)))

    def fmt_contrib(h):
        c = float(h.get("day_pnl", 0.0))
        return f"{h['ticker']} {c:+.0f}"

    # ---- Output
    lines: List[str] = []
    lines.append(f"【Portfolio 总览】({now_local.strftime('%Y-%m-%d %H:%M')})")
    lines.append(
        f"Total Net Liq {fmt(total_net)} | Cash {fmt(total_cash)} | MV {fmt(total_mv)} | P&L {total_day_pnl:+,.2f} ({fmt_pct(daily_ret)})"
    )
    # Performance line (drop benchmark if unavailable)
    perf_parts = [f"MTD {fmt_pct(mtd)}", f"YTD {fmt_pct(ytd)}"]
    if "N/A" not in bench:
        perf_parts.append(f"Benchmark {bench}")
    lines.append(" | ".join(perf_parts))

    bp = (lp_sum.buying_power or 0.0) + (mm_sum.buying_power or 0.0)
    if bp:
        lines.append(f"Buying Power(估算) {fmt(bp)}")

    # Risk line (only include available parts)
    risk_parts = []
    if beta is not None:
        risk_parts.append(f"Beta {fmt(beta)}")
    if vol20 is not None:
        risk_parts.append(f"Vol20 {fmt_pct(vol20)}")
    if mdd is not None:
        risk_parts.append(f"MaxDD(3mo) {fmt_pct(mdd)}")
    if risk_parts:
        lines.append("Risk: " + " | ".join(risk_parts))

    # Concentration (drop Unknown-only sector info)
    sec_str = ", ".join([f"{k} {fmt_pct(v)}" for k, v in top_sector if k != "Unknown"])
    conc_parts = [f"Top5 {fmt_pct(top5_weight)}", f"Max {fmt_pct(max_weight)}"]
    if sec_str:
        conc_parts.append(f"Sector {sec_str}")
    lines.append("Concentration: " + " | ".join(conc_parts))

    lines.append(f"Top Contributors: {', '.join(fmt_contrib(x) for x in contrib[:5])}")
    lines.append(f"Top Detractors: {', '.join(fmt_contrib(x) for x in detr[:5])}")

    lines.append("\n【Top 5 持仓（关键字段）】")
    for h in top5:
        w = h["mv"] / total_net if total_net else 0.0
        price = h.get("price")
        avg = h.get("avg_cost")
        upl = (float(price) - float(avg)) * float(h.get("qty", 0.0)) if (price is not None and avg is not None) else None
        upl_pct = (float(price) / float(avg) - 1.0) if (price is not None and avg is not None) else None
        contrib_today = float(h.get("day_pnl", 0.0))

        parts = [
            h["ticker"],
            f"W {fmt_pct(w)}",
            f"MV {fmt(h['mv'])}",
            f"DayPnL {contrib_today:+.2f}",
        ]
        if price is not None:
            parts.insert(3, f"Px {fmt(float(price))}")
        if avg is not None:
            parts.append(f"Cost {fmt(float(avg))}")
        if upl is not None and upl_pct is not None:
            parts.append(f"UPL {upl:+,.0f} ({fmt_pct(upl_pct)})")

        lines.append(" | ".join(parts))

    lines.append("\n【Catalyst Radar（未来7-14天硬事件）】")
    ev = next_events([h["ticker"] for h in top5])
    if ev:
        lines.extend(ev)
    else:
        lines.append("(未从公开源可靠获取到财报/分红硬事件；如需更准，建议用券商日历或付费日历源。)")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
