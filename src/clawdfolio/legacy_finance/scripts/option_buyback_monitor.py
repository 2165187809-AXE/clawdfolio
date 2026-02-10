#!/usr/bin/env python3
"""Monitor an option's market price and notify when buyback targets are hit.

- Uses moomoo for option quotes (with yfinance fallback) via lib/market.
- Does NOT place orders.
- Maintains state with file locking (via lib/state).
- Auto-reset: when ref price rises above trigger_price * (1 + reset_pct),
  the target is automatically re-armed for future triggers.
- Targets read from config.json.

State file: data/option_buyback_state.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.fmt import fmt_money
from lib.market import get_option_quote
from lib.state import StateFile

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
STATE = StateFile("data/option_buyback_state.json")


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fetch_call_quote(symbol: str, expiry: str, strike: float) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (bid, ask, last) for the specified call. moomoo first, yfinance fallback."""
    q = get_option_quote(symbol, expiry, strike, opt_type="C")
    if q is None:
        return None, None, None
    return q.get("bid"), q.get("ask"), q.get("last")


def main() -> None:
    cfg = load_config()
    ob_cfg = cfg.get("option_buyback", {})

    symbol = ob_cfg.get("symbol", "TQQQ")
    targets = ob_cfg.get("targets", [])

    if not targets:
        print("")
        return

    st = STATE.load()
    done: Dict[str, Any] = st.setdefault("done", {})

    # Use first target's expiry/strike as default (all should share same contract)
    first = targets[0]
    expiry = first.get("expiry", "2026-06-18")
    strike = float(first.get("strike", 60.0))

    bid, ask, last = fetch_call_quote(symbol, expiry, strike)

    # Reference price
    ref = None
    if last is not None and last > 0:
        ref = last
    elif bid is not None and ask is not None and bid > 0 and ask > 0:
        ref = (bid + ask) / 2
    elif bid is not None and bid > 0:
        ref = bid
    elif ask is not None and ask > 0:
        ref = ask

    st["lastQuote"] = {"ts": int(time.time()), "bid": bid, "ask": ask, "last": last, "ref": ref}

    # Auto-reset: if ref price has risen above trigger * (1 + reset_pct), re-arm
    for t in targets:
        name = t["name"]
        trg = float(t["trigger_price"])
        reset_pct = float(t.get("reset_pct", 0.20))

        if name in done and ref is not None:
            reset_threshold = trg * (1 + reset_pct)
            if ref > reset_threshold:
                del done[name]

    # Check triggers
    alerts = []
    for t in targets:
        name = t["name"]
        trg = float(t["trigger_price"])
        qty = int(t.get("qty", 1))

        if done.get(name):
            continue
        if ref is not None and ref <= trg:
            alerts.append((name, trg, qty, ref))

    if not alerts:
        STATE.save(st)
        print("")
        return

    # Mark as alerted
    for name, trg, qty, ref_val in alerts:
        done[name] = {"alertedAt": int(time.time()), "trigger": trg, "qty": qty, "ref": ref_val}

    STATE.save(st)

    opt_type = first.get("type", "C")

    def _fmt(v: Optional[float]) -> str:
        return fmt_money(v, 2) if v is not None else "N/A"

    lines = [
        "⚠️ 期权回补触发（待确认2）",
        "",
        f"合约: {symbol} {expiry} {opt_type}{int(strike)}",
        f"当前报价: bid={_fmt(bid)} ask={_fmt(ask)} last={_fmt(last)} (ref={_fmt(ref)})",
        "",
    ]
    for name, trg, qty, ref_val in alerts:
        label = "目标1" if name == "target1" else ("目标2" if name == "target2" else name)
        lines.append(f"- {label}: 触发价≤{fmt_money(trg, 2)}，建议回补 {qty} 张（现ref={fmt_money(ref_val, 2)}）")

    lines += [
        "",
        "请回复：确认2-目标1 / 确认2-目标2 / 确认2-两者都执行",
        "（我会回传订单明细再让你最终确认）",
    ]

    print("\n".join(lines).strip())


if __name__ == "__main__":
    main()
