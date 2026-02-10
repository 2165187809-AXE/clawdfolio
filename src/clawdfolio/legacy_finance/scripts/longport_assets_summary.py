#!/usr/bin/env python3
"""LongPort (Longbridge) assets summary for US market, USD-denominated.

Outputs JSON with:
- net_assets_usd
- cash_usd
- holdings_mkt_value_usd (stocks/ETFs only; excludes options if quote not available)
- day_pnl_usd (stocks/ETFs only)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from longport.openapi import Config, TradeContext, QuoteContext


def is_option_symbol(symbol: str) -> bool:
    # LongPort option symbols often contain an expiry/strike pattern like TQQQ260618C60000.US
    # Treat anything containing 'C'/'P' with a long numeric run as option-like.
    s = symbol.upper()
    return ("C" in s or "P" in s) and any(ch.isdigit() for ch in s[:-3]) and s.endswith(".US") and len(s) > 10


def main() -> None:
    import os, sys
    # Suppress SDK quote-rights table output that pollutes stdout
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)

    try:
        cfg = Config.from_env()
        trade = TradeContext(cfg)
        quote = QuoteContext(cfg)
    finally:
        # Restore stdout/stderr even if context init fails
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(devnull)
        os.close(saved_out)
        os.close(saved_err)

    # 1) Account balance in USD
    acc_list = trade.account_balance("USD")
    acc = acc_list[0]  # assume single account
    net_assets_usd = float(acc.net_assets)
    cash_usd = float(acc.total_cash)

    # 2) US stock positions
    pos = trade.stock_positions()
    symbols: list[tuple[str, float]] = []  # (symbol, qty)

    for ch in getattr(pos, "channels", []):
        for p in getattr(ch, "positions", []):
            mkt = str(getattr(p, "market", ""))
            mkt = mkt.split(".")[-1].upper()
            if mkt not in ("US", "USA"):
                continue
            sym = str(getattr(p, "symbol"))
            if is_option_symbol(sym):
                continue
            qty = float(getattr(p, "quantity"))
            # skip zero positions
            if abs(qty) < 1e-9:
                continue
            symbols.append((sym, qty))

    # 3) Quotes and compute holdings market value + day PnL (stocks only)
    holdings_mkt_value = 0.0
    day_pnl = 0.0
    missing: list[str] = []

    if symbols:
        # Quote API supports batching
        sym_list = [s for s, _ in symbols]
        quotes = quote.quote(sym_list)
        qmap: dict[str, Any] = {str(getattr(q, "symbol")): q for q in quotes}

        for sym, qty in symbols:
            q = qmap.get(sym)
            if not q:
                missing.append(sym)
                continue
            last = float(getattr(q, "last_done"))
            prev = float(getattr(q, "prev_close"))
            holdings_mkt_value += qty * last
            day_pnl += qty * (last - prev)

    out = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "net_assets_usd": net_assets_usd,
        "cash_usd": cash_usd,
        "holdings_mkt_value_usd": holdings_mkt_value,
        "day_pnl_usd": day_pnl,
        "excluded_options": True,
        "missing_quotes": missing,
    }

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
