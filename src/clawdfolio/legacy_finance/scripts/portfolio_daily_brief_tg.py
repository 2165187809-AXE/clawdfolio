#!/usr/bin/env python3
"""Telegram-friendly Portfolio Daily Brief card.

Hard requirements:
- Output MUST be a Markdown code block with ```text ... ``` and ONLY the card body.
- No box/line drawing chars like ┏┓┌┐━━━.
- Use ONLY section emojis (one per section title): 📊 💼 ⚡️ 🧱 🛡️ 🎯 🗓️
- Hide missing fields; money = integer w/ commas; percent = 1 decimal.
- Use ▲/▼ only for sign.
- Total lines <= 22; each line <= 88 chars.

Catalyst Radar:
- MUST attempt external lookups for Top5: Earnings / Ex-div / Options expiry.
- Radar outputs 1–3 items (prefer events, else risk signal). Never output 'None'.
- Never fabricate dates: if unavailable, silently skip.

Data:
- LongPort + moomoo for holdings and PnL (via lib/brokers).
- yfinance for events and price history (via lib/market).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.brokers import fetch_holdings, fetch_balances, HoldingInfo
from lib.fmt import (
    fmt_money, fmt_pct, arrow_sign, signed_money, signed_pct,
    clamp_line, clamp_lines, yf_sym,
)
from lib.market import get_earnings_date, get_history

HISTORY_PATH = Path(__file__).resolve().parent / "data/portfolio_history.jsonl"
BASELINES_PATH = Path(__file__).resolve().parent / "data/portfolio_baselines.json"

MAX_LINES = 22
MAX_COLS = 88
W_TKR = 5


def load_history() -> List[dict]:
    if not HISTORY_PATH.exists():
        return []
    out: List[dict] = []
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


def load_baselines() -> Optional[dict]:
    if not BASELINES_PATH.exists():
        return None
    try:
        return json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def enrich_prices(hold: Dict[str, HoldingInfo], tickers: List[str]) -> None:
    """Broker-first fill for price/prev_close; Yahoo only as last resort."""
    # 1) Broker quotes (LongPort -> moomoo)
    try:
        from lib.market_data import fetch_best_quotes

        qmap = fetch_best_quotes(tickers)
        for t in tickers:
            h = hold.get(t)
            if not h:
                continue
            q = qmap.get(t)
            if not q:
                continue
            if h.price is None and q.get("price") is not None:
                h.price = float(q["price"])
            if h.prev_close is None and q.get("prev_close") is not None:
                h.prev_close = float(q["prev_close"])
    except Exception:
        pass

    # 2) Yahoo fallback for anything still missing
    try:
        import yfinance as yf
        syms = [yf_sym(t) for t in tickers]
        px = yf.download(syms, period="5d", interval="1d", progress=False)["Close"].dropna(how="all")
        if isinstance(px, pd.Series) or px is None or len(px) < 2:
            return
        last = px.iloc[-1]
        prev = px.iloc[-2]
        for t in tickers:
            h = hold.get(t)
            if not h:
                continue
            col = yf_sym(t)
            if col in last.index:
                if h.price is None:
                    h.price = float(last[col])
                if h.prev_close is None:
                    h.prev_close = float(prev[col])
    except Exception:
        return


@dataclass
class RadarItem:
    prio: int
    line: str


def _fmt_date(d: date) -> str:
    return d.strftime("%m/%d")


def _tminus(dt: date) -> str:
    td = (dt - date.today()).days
    return f"T-{td}" if td >= 0 else f"T+{abs(td)}"


def fetch_events_for(ticker: str) -> List[RadarItem]:
    """Return radar items for events within 7 days. Silently skip failures."""
    import yfinance as yf
    ok: List[RadarItem] = []

    # Earnings
    try:
        result = get_earnings_date(ticker)
        if result:
            dt, _ = result
            if 0 <= (dt - date.today()).days <= 7:
                ok.append(RadarItem(1, f"{ticker} Earnings {_fmt_date(dt)} {_tminus(dt)} impact=Gap src=Yahoo"))
    except Exception:
        pass

    # Ex-div
    try:
        info = yf.Ticker(yf_sym(ticker)).info
        ex = info.get("exDividendDate")
        if ex:
            try:
                dt = datetime.fromtimestamp(int(ex)).date()
            except Exception:
                dt = None
            if dt is None:
                raise ValueError("bad exDividendDate")
            if 0 <= (dt - date.today()).days <= 7:
                ok.append(RadarItem(2, f"{ticker} Ex-div {_fmt_date(dt)} {_tminus(dt)} impact=PriceAdj src=Yahoo"))
    except Exception:
        pass

    # Options expiry
    try:
        opts = yf.Ticker(yf_sym(ticker)).options
        if opts:
            dts = []
            for s in opts[:10]:
                try:
                    dts.append(datetime.strptime(s, "%Y-%m-%d").date())
                except Exception:
                    continue
            if dts:
                dt = sorted(dts)[0]
                if 0 <= (dt - date.today()).days <= 7:
                    ok.append(RadarItem(3, f"{ticker} OptExp {_fmt_date(dt)} {_tminus(dt)} impact=Gamma src=Yahoo"))
    except Exception:
        pass

    return ok


def realized_vol_pctl(ticker: str) -> Optional[int]:
    try:
        import yfinance as yf
        px = yf.download(yf_sym(ticker), period="1y", interval="1d", progress=False)["Close"].squeeze().dropna()
        if px is None or len(px) < 80:
            return None
        r = px.pct_change().dropna()
        v = (r.rolling(20).std() * np.sqrt(252)).dropna()
        if len(v) < 40:
            return None
        cur = float(v.iloc[-1])
        p = int(round(float((v <= cur).mean()) * 100))
        return p
    except Exception:
        return None


def fmt_top_line(tkr: str, w: float, day: Optional[float], upl: Optional[float]) -> str:
    tk = f"{tkr:<{W_TKR}}"
    w_s = f"{w * 100:>4.1f}%"
    parts = [f"{tk} {w_s:>5}"]
    if day is not None:
        parts.append(f"{arrow_sign(day)}{abs(day) * 100:>4.1f}%")
    if upl is not None:
        parts.append(f"UPL {arrow_sign(upl)}{abs(upl) * 100:>4.1f}%")
    return " ".join(parts)


def main() -> None:
    ds = datetime.now().strftime("%Y-%m-%d")

    # Fetch data via shared lib
    balances = fetch_balances()
    combined = balances["combined"]
    netliq = combined.net_assets
    cash = combined.cash
    bp = combined.buying_power
    day_pnl = combined.day_pnl
    day_pct = day_pnl / netliq if netliq else 0.0

    # Guard: if all brokers failed, output error instead of misleading $0
    if netliq == 0 and combined.error:
        print("```text")
        print(f"📊 Daily Brief | {ds}")
        print(f"⚠️ 数据获取失败: {combined.error}")
        print("请检查 LongPort/moomoo 连接状态")
        print("```")
        return

    hold = fetch_holdings()

    hist = load_history()
    b = load_baselines() or {}

    bm = float(b.get("month_start_net")) if b.get("month_start_net") else (baseline(hist, datetime.now().year, datetime.now().month) or netliq)
    by = float(b.get("year_start_net")) if b.get("year_start_net") else (baseline(hist, datetime.now().year, None) or netliq)

    mtd = netliq / bm - 1.0 if bm else 0.0
    ytd = netliq / by - 1.0 if by else 0.0

    append_history({"ts": datetime.now().isoformat(), "total_net": netliq})

    allh = sorted(hold.values(), key=lambda x: x.mv, reverse=True)
    enrich_prices(hold, [h.ticker for h in allh[:15]])

    # Highlights
    up = [h for h in sorted(allh, key=lambda x: x.day_contrib, reverse=True) if h.day_contrib > 0][:2]
    dn = [h for h in sorted(allh, key=lambda x: x.day_contrib) if h.day_contrib < 0][:2]

    # Top5
    top5 = allh[:5]
    top5_sum = sum(h.mv for h in top5) / netliq if netliq else None

    # Risk
    max_tkr = top5[0].ticker if top5 else ""
    max_w = (top5[0].mv / netliq) if (top5 and netliq) else None

    # Radar: attempt external lookups for Top5
    radar_ok: List[RadarItem] = []
    for h in top5:
        radar_ok.extend(fetch_events_for(h.ticker))

    picked: List[str] = []

    # Prefer hard events in next 7d
    for it in sorted(radar_ok, key=lambda x: x.prio):
        if it.line not in picked:
            picked.append(it.line)
        if len(picked) >= 3:
            break

    # Vol signal if not enough events
    if len(picked) < 2 and top5:
        vp = realized_vol_pctl(top5[0].ticker)
        if vp is not None:
            picked.append(f"{top5[0].ticker} Vol {vp}pctl {_tminus(date.today())} impact=Var src=Yahoo")

    # Concentration risk as fallback
    if len(picked) < 2 and max_tkr and max_w is not None:
        picked.append(f"{max_tkr} Concentration {fmt_pct(max_w)} impact=Risk src=internal")

    picked = picked[:3]

    # Build card
    lines: List[str] = []
    lines.append(f"📊 Daily Brief | {ds}")

    lines.append("💼 ACCOUNT")
    lines.append(f"NetLiq {fmt_money(netliq)}  Day {arrow_sign(day_pnl)}{fmt_money(abs(day_pnl))} ({signed_pct(day_pct)})")
    lines.append(f"Cash {fmt_money(cash)}  BP {fmt_money(bp)}")
    lines.append(f"MTD {signed_pct(mtd)}  YTD {signed_pct(ytd)}")

    lines.append("⚡️ HIGHLIGHTS (PnL $)")
    ups = "  ".join([f"▲ {h.ticker} +{fmt_money(h.day_contrib)}" for h in up])
    dns = "  ".join([f"▼ {h.ticker} -{fmt_money(abs(h.day_contrib))}" for h in dn])
    if ups:
        lines.append(ups)
    if dns:
        lines.append(dns)

    top5_head = "🧱 TOP5"
    if top5_sum is not None:
        top5_head += f" ({fmt_pct(top5_sum)})"
    lines.append(top5_head)

    if not top5:
        lines.append("无持仓数据")
    else:
        for h in top5:
            w = h.mv / netliq if netliq else 0.0
            day_move = None
            upl_move = None
            if h.price is not None and h.prev_close is not None and h.prev_close != 0:
                day_move = h.price / h.prev_close - 1.0
            if h.price is not None and h.avg_cost is not None and h.avg_cost != 0:
                upl_move = h.price / h.avg_cost - 1.0
            lines.append(fmt_top_line(h.ticker, w, day_move, upl_move))

    risk_items: List[str] = []
    if max_tkr and max_w is not None and max_w > 0.15:
        risk_items.append(f"Concentration: {max_tkr} {fmt_pct(max_w)}")

    lines.append("🛡️ RISK")
    if risk_items:
        for r in risk_items[:2]:
            lines.append(f"• {r}")
    else:
        lines.append("• None")

    lines.append("🎯 Catalyst Radar: Alpha & Risk")
    for s in picked:
        lines.append(s)

    lines = [clamp_line(ln, MAX_COLS) for ln in lines if ln.strip()]
    lines = clamp_lines(lines, MAX_LINES)

    print("```text")
    print("\n".join(lines))
    print("```")


if __name__ == "__main__":
    main()
