#!/usr/bin/env python3
"""Strict compact Portfolio daily brief (mobile, <=22 lines).

Style: box/terminal-like, arrows ▲▼.
Rules:
- Output only brief body (no explanations).
- Hide missing fields.
- Money: integer with thousands separators, prefixed with $.
- Percent: 1 decimal.
- Use ▲ for positive, ▼ for negative (no extra dots/arrows mixed).

Catalyst Radar: Alpha & Risk (best-effort from public data):
- Uses realized volatility percentile (not implied volatility) computed from 1y daily returns.
- Upcoming earnings (best-effort via yfinance calendar).

Data sources:
- LongPort: account_balance(USD), positions + quote for price/prev close
- moomoo OpenD: accinfo_query(USD), position_list_query(US)
- yfinance: prices, sector, earnings dates
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from lib.brokers import HoldingInfo, fetch_balances_and_holdings
from lib.market import get_earnings_date

HISTORY_PATH = Path(__file__).resolve().parent / "data/portfolio_history.jsonl"


def money(x: float) -> str:
    return f"${int(round(x)):,}"


def pct(x: float) -> str:
    return f"{x*100:.1f}%"


def arrow(x: float) -> str:
    return "▲" if x >= 0 else "▼"


def signed_money(x: float) -> str:
    return f"{arrow(x)}{money(abs(x))}"


def signed_pct(x: float) -> str:
    return f"{arrow(x)}{pct(abs(x))}"


def _yf_sym(t: str) -> str:
    return t.replace(".", "-")


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


def baseline(history: List[dict], y: int, m: Optional[int] = None) -> Optional[float]:
    for r in history:
        try:
            ts = datetime.fromisoformat(r["ts"])
        except Exception:
            continue
        if ts.year != y:
            continue
        if m is not None and ts.month != m:
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
    for src in (lp, mm):
        for t, d in src.items():
            h = out.get(t) or Holding(ticker=t)
            h.name = h.name or d.get("name", "")
            h.qty += float(d.get("qty", 0.0) or 0.0)
            h.mv += float(d.get("mv", 0.0) or 0.0)
            h.day_contrib += float(d.get("day_contrib", 0.0) or 0.0)
            if d.get("price"):
                h.price = float(d["price"])
            if d.get("prev_close"):
                h.prev_close = float(d["prev_close"])

            if d.get("avg_cost") is not None and d.get("qty"):
                if not hasattr(h, "_cq"):
                    h._cq = 0.0  # type: ignore
                    h._cs = 0.0  # type: ignore
                h._cq += float(d["qty"])  # type: ignore
                h._cs += float(d["qty"]) * float(d["avg_cost"])  # type: ignore

            out[t] = h

    for h in out.values():
        if hasattr(h, "_cq") and getattr(h, "_cq"):
            h.avg_cost = getattr(h, "_cs") / getattr(h, "_cq")
        for k in ("_cq", "_cs"):
            if hasattr(h, k):
                delattr(h, k)
    return out


def enrich_prices(hold: Dict[str, Holding], tickers: List[str]) -> None:
    try:
        syms = [_yf_sym(t) for t in tickers]
        px = yf.download(syms, period="5d", interval="1d", progress=False)["Close"].dropna(how="all")
        if isinstance(px, pd.Series) or px is None or len(px) < 2:
            return
        last = px.iloc[-1]
        prev = px.iloc[-2]
        for t in tickers:
            h = hold.get(t)
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


def vol_percentile(ticker: str) -> Optional[float]:
    # realized vol percentile over 1y daily returns (rolling 20d stdev)
    try:
        px = yf.download(_yf_sym(ticker), period="1y", interval="1d", progress=False)["Close"].squeeze().dropna()
        if px is None or len(px) < 60:
            return None
        r = px.pct_change().dropna()
        vol20 = r.rolling(20).std() * np.sqrt(252)
        vol20 = vol20.dropna()
        if len(vol20) < 30:
            return None
        cur = float(vol20.iloc[-1])
        perc = float((vol20 <= cur).mean())
        return perc
    except Exception:
        return None


def sector_weight(top: List[Holding], total_net: float) -> Tuple[Optional[str], Optional[float]]:
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
    if not sw:
        return None, None
    sec, w = sorted(sw.items(), key=lambda x: x[1], reverse=True)[0]
    return sec, w


def earnings_within_7d(tickers: List[str]) -> List[str]:
    out = []
    today = date.today()
    for t in tickers:
        try:
            result = get_earnings_date(t)
            if not result:
                continue
            dt, _ = result
            d = (dt - today).days
            if 0 <= d <= 7:
                out.append(f"{dt.strftime('%-m/%-d')} {t} Earnings (D-{d})")
        except Exception:
            continue
    return out[:3]


def main() -> None:
    now = datetime.now()
    ds = now.strftime("%Y-%m-%d")

    lp_net, lp_cash, lp_mv, lp_bp, lp_day, lp_h = longport_data()
    mm_net, mm_cash, mm_mv, mm_bp, mm_day, mm_h = moomoo_data()

    total_net = lp_net + mm_net
    total_cash = lp_cash + mm_cash
    total_bp = (lp_bp or 0.0) + (mm_bp or 0.0)
    day_pnl = lp_day + mm_day
    day_pct = day_pnl / total_net if total_net else 0.0

    hist = load_history()
    bm = baseline(hist, now.year, now.month) or total_net
    by = baseline(hist, now.year, None) or total_net
    mtd = total_net / bm - 1.0 if bm else 0.0
    ytd = total_net / by - 1.0 if by else 0.0
    append_history({"ts": now.isoformat(), "total_net": total_net})

    hold = merge(lp_h, mm_h)
    allh = list(hold.values())
    allh.sort(key=lambda x: x.mv, reverse=True)

    enrich_prices(hold, [h.ticker for h in allh[:15]])

    top5 = allh[:5]
    top5_share = sum(h.mv for h in top5) / total_net if total_net else None

    up = [h for h in sorted(allh, key=lambda x: x.day_contrib, reverse=True) if h.day_contrib > 0][:2]
    dn = [h for h in sorted(allh, key=lambda x: x.day_contrib) if h.day_contrib < 0][:2]

    # Risk flags
    risk_lines: List[str] = []
    if top5 and total_net:
        maxw = top5[0].mv / total_net
        if maxw > 0.15:
            risk_lines.append(f"• Concentration: {top5[0].ticker} {pct(maxw)}")

    sec, secw = sector_weight(allh[:10], total_net)
    if sec and secw and secw > 0.30:
        risk_lines.append(f"• Sector tilt: {sec} {pct(secw)}")

    for h in top5:
        if h.price is not None and h.prev_close is not None and h.prev_close != 0:
            d = h.price / h.prev_close - 1.0
            if d < -0.04:
                risk_lines.append(f"• Shock: {h.ticker} Day {pct(d)}")
        if h.price is not None and h.avg_cost is not None and h.avg_cost != 0:
            dd = h.price / h.avg_cost - 1.0
            if dd < -0.12:
                risk_lines.append(f"• Drawdown: {h.ticker} {pct(dd)}")

    # Catalyst Radar
    radar: List[str] = []
    # Vol alert: highest realized-vol percentile among Top5
    vol_list = []
    for h in top5:
        p = vol_percentile(h.ticker)
        if p is not None:
            vol_list.append((p, h.ticker))
    if vol_list:
        p, t = sorted(vol_list, reverse=True)[0]
        if p >= 0.85:
            radar.append(f"⚡ Vol alert: {t} {int(round(p*100))}pctl")
    # Sector transmission (only if sector tilt exists)
    if sec and secw and secw > 0.25:
        radar.append(f"📦 Sector: {sec} {pct(secw)}")
    # Earnings in 7d
    ev = earnings_within_7d([h.ticker for h in top5])
    if ev:
        radar.append("📅 " + "; ".join(ev))

    # ---- Output (<=22 lines)
    lines: List[str] = []

    lines.append(f"┏ Daily Brief | {ds} ┓")
    lines.append("┌ ACCOUNT ┐")
    lines.append(f"NetLiq {money(total_net)} | Day {arrow(day_pnl)}{money(abs(day_pnl))} ({arrow(day_pct)}{pct(abs(day_pct))})")
    lines.append(f"Cash {money(total_cash)} | BP {money(total_bp)}")
    lines.append(f"MTD {arrow(mtd)}{pct(abs(mtd))} | YTD {arrow(ytd)}{pct(abs(ytd))}")

    lines.append("┌ HIGHLIGHTS ┐")
    if up:
        lines.append(" ".join([f"▲ {h.ticker} +{money(h.day_contrib)}" for h in up]))
    if dn:
        lines.append(" ".join([f"▼ {h.ticker} -{money(abs(h.day_contrib))}" for h in dn]))

    if top5_share is not None:
        lines.append(f"┌ TOP5 ({pct(top5_share)}) ┐")
    else:
        lines.append("┌ TOP5 ┐")

    for h in top5:
        w = h.mv / total_net if total_net else 0.0
        parts = [f"{h.ticker} {pct(w)}"]
        if h.price is not None and h.prev_close is not None and h.prev_close != 0:
            d = h.price / h.prev_close - 1.0
            parts.append(f"{arrow(d)}{pct(abs(d))}")
        if h.price is not None and h.avg_cost is not None and h.avg_cost != 0:
            upl = h.price / h.avg_cost - 1.0
            parts.append(f"UPL {arrow(upl)}{pct(abs(upl))}")
        lines.append(" | ".join(parts))

    lines.append("┌ RISK ┐")
    if risk_lines:
        lines.extend(risk_lines[:3])
    else:
        lines.append("✓ No significant flags")

    lines.append("┌ Catalyst Radar: Alpha & Risk ┐")
    if radar:
        lines.extend(radar[:4])
    else:
        lines.append("✓ None")

    print("\n".join(lines[:22]))


if __name__ == "__main__":
    main()
