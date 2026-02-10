"""Unified market data helpers (broker-first, Yahoo fallback).

Goal: Prefer broker APIs for near-real-time prices.
- LongPort: QuoteContext.quote
- moomoo: OpenQuoteContext.get_market_snapshot
- Fallback: yfinance

All functions return dicts keyed by ticker.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .brokers import fetch_quotes_longport, suppress_stdio_fds


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _attach_change_pct(q: Dict[str, Any]) -> None:
    px = _safe_float(q.get("price"))
    pc = _safe_float(q.get("prev_close"))
    if px is not None and pc is not None and pc > 0:
        q["change_pct"] = (px / pc - 1) * 100


def fetch_quotes_moomoo(tickers: List[str]) -> Dict[str, Any]:
    """Fetch quotes via moomoo OpenD quote API (best effort)."""
    result: Dict[str, Any] = {}
    if not tickers:
        return result

    try:
        from futu.common import ft_logger
        ft_logger.logger.console_level = 50

        from futu import OpenQuoteContext, RET_OK

        with suppress_stdio_fds():
            quote_ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        try:
            codes = [f"US.{t}" for t in tickers]

            # Snapshot is the most compact way to get last/prev_close/volume.
            with suppress_stdio_fds():
                ret, df = quote_ctx.get_market_snapshot(codes)
            if ret == RET_OK and df is not None and not df.empty:
                for _, r in df.iterrows():
                    code = str(r.get("code", ""))
                    if not code.startswith("US."):
                        continue
                    t = code.split(".", 1)[1]
                    px = r.get("last_price")
                    pc = r.get("prev_close_price")
                    vol = r.get("volume")
                    to = r.get("turnover")
                    if px is None:
                        continue
                    item = {
                        "price": float(px),
                        "prev_close": float(pc) if pc is not None else None,
                        "volume": int(vol) if vol is not None else None,
                        "turnover": float(to) if to is not None else None,
                        "source": "moomoo",
                    }
                    _attach_change_pct(item)
                    result[t] = item
            else:
                # Fallback per-ticker quote
                for t in tickers:
                    with suppress_stdio_fds():
                        ret2, df2 = quote_ctx.get_stock_quote([f"US.{t}"])
                    if ret2 != RET_OK or df2 is None or df2.empty:
                        continue
                    r = df2.iloc[0]
                    px = r.get("last_price")
                    pc = r.get("prev_close")
                    if px is None:
                        continue
                    item = {
                        "price": float(px),
                        "prev_close": float(pc) if pc is not None else None,
                        "source": "moomoo",
                    }
                    _attach_change_pct(item)
                    result[t] = item
        finally:
            quote_ctx.close()
    except Exception:
        return result

    return result


def fetch_quotes_yfinance(tickers: List[str]) -> Dict[str, Any]:
    """Yahoo fallback (delayed 1-2 min)."""
    out: Dict[str, Any] = {}
    if not tickers:
        return out
    try:
        import concurrent.futures
        import yfinance as yf

        def one(ticker: str) -> Optional[Dict[str, Any]]:
            try:
                t = yf.Ticker(ticker.replace(".", "-"))
                info = t.info
                fast = t.fast_info if hasattr(t, "fast_info") else None

                price = None
                prev_close = None
                if fast:
                    price = getattr(fast, "last_price", None)
                    prev_close = getattr(fast, "previous_close", None)

                if price is None:
                    price = info.get("currentPrice") or info.get("regularMarketPrice")
                if prev_close is None:
                    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

                if price is None:
                    return None

                item = {
                    "price": float(price),
                    "prev_close": float(prev_close) if prev_close else None,
                    "volume": info.get("volume") or info.get("regularMarketVolume"),
                    "avg_volume": info.get("averageVolume"),
                    "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
                    "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
                    "source": "yahoo",
                }
                _attach_change_pct(item)
                return item
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(one, t): t for t in tickers}
            for f in concurrent.futures.as_completed(futs):
                t = futs[f]
                q = f.result()
                if q:
                    out[t] = q
    except Exception:
        return out

    return out


def fetch_best_quotes(tickers: List[str]) -> Dict[str, Any]:
    """Broker-first quotes with Yahoo fallback.

    Priority: LongPort -> moomoo -> Yahoo
    """
    tickers = list(dict.fromkeys(tickers))
    out: Dict[str, Any] = {}

    lp = fetch_quotes_longport(tickers)
    for q in lp.values():
        if isinstance(q, dict):
            _attach_change_pct(q)
    out.update(lp)

    remaining = [t for t in tickers if t not in out]
    mm = fetch_quotes_moomoo(remaining)
    out.update(mm)

    remaining = [t for t in tickers if t not in out]
    yf = fetch_quotes_yfinance(remaining)
    out.update(yf)

    return out
