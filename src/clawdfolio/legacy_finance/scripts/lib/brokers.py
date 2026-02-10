"""Broker connection and data fetching for LongPort + moomoo."""

from __future__ import annotations

import io
import os
import re
import socket
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .env_loader import load_longport_env


@dataclass
class HoldingInfo:
    ticker: str
    qty: float = 0.0
    mv: float = 0.0
    avg_cost: Optional[float] = None
    price: Optional[float] = None
    prev_close: Optional[float] = None
    day_contrib: float = 0.0
    name: str = ""
    source: str = ""


@dataclass
class BalanceInfo:
    net_assets: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    buying_power: float = 0.0
    day_pnl: float = 0.0
    error: Optional[str] = None


MOOMOO_HOST = "127.0.0.1"
MOOMOO_PORT = 11111


@contextmanager
def suppress_stdio_fds():
    """Suppress low-level stdout/stderr (C/Rust SDK prints that bypass redirect_stdout)."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        try:
            os.dup2(saved_out, 1)
            os.dup2(saved_err, 2)
        finally:
            os.close(saved_out)
            os.close(saved_err)
            os.close(devnull)


@contextmanager
def time_limit(seconds: int):
    """Best-effort wall-clock timeout."""
    try:
        import signal

        def _handler(_signum, _frame):
            raise TimeoutError(f"timeout after {seconds}s")

        old = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    except Exception:
        yield


def _is_option_symbol(sym: str) -> bool:
    """Check if a LongPort symbol looks like an option (e.g. AAPL230120C00150000.US)."""
    base = sym.replace(".US", "")
    return bool(re.match(r"^[A-Z]{1,6}\d{6}[CP]\d+$", base))


def get_longport_ctx():
    """Return (TradeContext, QuoteContext) with stdout suppressed."""
    # Ensure env exists even when running under cron/daemon.
    load_longport_env()

    _null = io.StringIO()
    with suppress_stdio_fds():
        with redirect_stdout(_null), redirect_stderr(_null):
            from longport.openapi import Config, TradeContext, QuoteContext
            cfg = Config.from_env()
            trade = TradeContext(cfg)
        with redirect_stdout(_null), redirect_stderr(_null):
            quote = QuoteContext(cfg)
    return trade, quote


def _call_with_timeout(fn, timeout_s: int, default):
    try:
        import threading

        result = {"value": default}

        def _run():
            try:
                result["value"] = fn()
            except Exception:
                result["value"] = default

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout_s)
        return result["value"]
    except Exception:
        return default


def _longport_holdings_and_balance() -> Tuple[BalanceInfo, Dict[str, HoldingInfo]]:
    """Fetch from LongPort. Returns (balance, holdings_dict)."""
    # Ensure env exists even when running under cron/daemon.
    load_longport_env()

    bal = BalanceInfo()
    holdings: Dict[str, HoldingInfo] = {}

    try:
        _null = io.StringIO()
        with suppress_stdio_fds():
            with redirect_stdout(_null), redirect_stderr(_null):
                from longport.openapi import Config, TradeContext, QuoteContext
                cfg = Config.from_env()
                trade = TradeContext(cfg)

            with redirect_stdout(_null), redirect_stderr(_null):
                acc_list = _call_with_timeout(lambda: trade.account_balance("USD"), 6, [])
                acc = acc_list[0] if acc_list else None

        if acc is None:
            return bal, holdings

        bal.net_assets = float(acc.net_assets)
        bal.cash = float(acc.total_cash)
        bal.buying_power = float(getattr(acc, "buy_power", 0.0) or 0.0)

        with suppress_stdio_fds():
            with redirect_stdout(_null), redirect_stderr(_null):
                quote = QuoteContext(cfg)

        pos = _call_with_timeout(lambda: trade.stock_positions(), 6, None)
        if pos is None:
            return bal, holdings
        syms: List[str] = []

        for ch in getattr(pos, "channels", []):
            for p in getattr(ch, "positions", []):
                mkt = str(getattr(p, "market", "")).split(".")[-1].upper()
                if mkt != "US":
                    continue
                sym = str(getattr(p, "symbol"))
                if _is_option_symbol(sym):
                    continue
                qty = float(getattr(p, "quantity"))
                if abs(qty) < 1e-9:
                    continue
                t = sym.replace(".US", "")
                holdings[t] = HoldingInfo(
                    ticker=t,
                    qty=qty,
                    avg_cost=float(getattr(p, "cost_price", 0.0) or 0.0),
                    name=str(getattr(p, "symbol_name", "")),
                    source="longport",
                )
                syms.append(sym)

        if syms:
            _null2 = io.StringIO()

            def _fetch_quotes():
                with suppress_stdio_fds():
                    with redirect_stdout(_null2), redirect_stderr(_null2):
                        return quote.quote(syms)

            quotes = _call_with_timeout(_fetch_quotes, 6, [])

            qmap = {q.symbol.replace(".US", ""): q for q in quotes}
            for t, h in holdings.items():
                q = qmap.get(t)
                if not q:
                    continue
                px = float(q.last_done)
                pc = float(q.prev_close)
                h.price = px
                h.prev_close = pc
                h.mv = h.qty * px
                h.day_contrib = h.qty * (px - pc)
                bal.day_pnl += h.day_contrib
                bal.market_value += h.mv
    except Exception as exc:
        bal.error = str(exc) or type(exc).__name__

    return bal, holdings


def _moomoo_holdings_and_balance() -> Tuple[BalanceInfo, Dict[str, HoldingInfo]]:
    """Fetch from moomoo. Returns (balance, holdings_dict)."""
    bal = BalanceInfo()
    holdings: Dict[str, HoldingInfo] = {}

    try:
        # Quick connectivity test
        with socket.create_connection((MOOMOO_HOST, MOOMOO_PORT), timeout=1.0):
            pass

        from futu.common import ft_logger
        ft_logger.logger.console_level = 50

        from futu import (
            OpenSecTradeContext, TrdMarket, TrdEnv, Currency, SecurityFirm, RET_OK,
        )

        trd = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.US,
            host=MOOMOO_HOST,
            port=MOOMOO_PORT,
            security_firm=SecurityFirm.FUTUINC,
        )

        try:
            ret, funds = trd.accinfo_query(trd_env=TrdEnv.REAL, currency=Currency.USD)
            if ret == RET_OK:
                row = funds.iloc[0]
                bal.net_assets = float(row.get("total_assets", 0.0))
                bal.cash = float(row.get("cash", 0.0))
                bal.market_value = float(row.get("market_val", 0.0))
                bal.buying_power = float(row.get("power", 0.0) or 0.0)

            ret, pos = trd.position_list_query(trd_env=TrdEnv.REAL, position_market=TrdMarket.US)
            if ret == RET_OK:
                bal.day_pnl = float(pos["today_pl_val"].fillna(0).sum()) if "today_pl_val" in pos.columns else 0.0

                for _, r in pos.iterrows():
                    code = str(r.get("code"))
                    if not code.startswith("US."):
                        continue
                    t = code.split(".", 1)[1]
                    holdings[t] = HoldingInfo(
                        ticker=t,
                        qty=float(r.get("qty", 0.0)),
                        avg_cost=float(r.get("cost_price", 0.0) or 0.0),
                        price=float(r.get("nominal_price", 0.0) or 0.0),
                        mv=float(r.get("market_val", 0.0) or 0.0),
                        day_contrib=float(r.get("today_pl_val", 0.0) or 0.0),
                        name=str(r.get("stock_name", "")),
                        source="moomoo",
                    )
        finally:
            trd.close()
    except Exception as exc:
        bal.error = str(exc) or type(exc).__name__

    return bal, holdings


def _merge_holdings(all_holdings: List[Dict[str, HoldingInfo]]) -> Dict[str, HoldingInfo]:
    merged: Dict[str, HoldingInfo] = {}
    cost_sums: Dict[str, float] = {}
    cost_qtys: Dict[str, float] = {}

    for src in all_holdings:
        for t, h in src.items():
            if t not in merged:
                merged[t] = HoldingInfo(ticker=t)
            m = merged[t]
            m.qty += h.qty
            m.mv += h.mv
            m.day_contrib += h.day_contrib
            if h.price:
                m.price = h.price
            if h.prev_close:
                m.prev_close = h.prev_close
            if h.name and not m.name:
                m.name = h.name

            if h.avg_cost and h.qty:
                cost_sums[t] = cost_sums.get(t, 0.0) + h.qty * h.avg_cost
                cost_qtys[t] = cost_qtys.get(t, 0.0) + h.qty

    for t, m in merged.items():
        if cost_qtys.get(t, 0) > 0:
            m.avg_cost = cost_sums[t] / cost_qtys[t]

    return merged


def fetch_holdings(sources: Optional[List[str]] = None) -> Dict[str, HoldingInfo]:
    """Fetch and merge holdings from both brokers.

    Returns dict keyed by clean ticker (e.g. 'AAPL').
    Merges quantities, market values, and computes weighted average cost.
    """
    if sources is None:
        sources = ["longport", "moomoo"]

    all_holdings: List[Dict[str, HoldingInfo]] = []

    if "longport" in sources:
        _, lp = _longport_holdings_and_balance()
        all_holdings.append(lp)
    if "moomoo" in sources:
        _, mm = _moomoo_holdings_and_balance()
        all_holdings.append(mm)

    return _merge_holdings(all_holdings)


def fetch_balances_and_holdings(
    sources: Optional[List[str]] = None,
) -> Tuple[Dict[str, BalanceInfo], Dict[str, HoldingInfo]]:
    """Fetch balances and holdings with a single broker pass."""
    if sources is None:
        sources = ["longport", "moomoo"]

    result: Dict[str, BalanceInfo] = {}
    combined = BalanceInfo()
    all_holdings: List[Dict[str, HoldingInfo]] = []

    errors: List[str] = []

    if "longport" in sources:
        lp_bal, lp_holdings = _longport_holdings_and_balance()
        result["longport"] = lp_bal
        all_holdings.append(lp_holdings)
        combined.net_assets += lp_bal.net_assets
        combined.cash += lp_bal.cash
        combined.market_value += lp_bal.market_value
        combined.buying_power += lp_bal.buying_power
        combined.day_pnl += lp_bal.day_pnl
        if lp_bal.error:
            errors.append(f"longport: {lp_bal.error}")

    if "moomoo" in sources:
        mm_bal, mm_holdings = _moomoo_holdings_and_balance()
        result["moomoo"] = mm_bal
        all_holdings.append(mm_holdings)
        combined.net_assets += mm_bal.net_assets
        combined.cash += mm_bal.cash
        combined.market_value += mm_bal.market_value
        combined.buying_power += mm_bal.buying_power
        combined.day_pnl += mm_bal.day_pnl
        if mm_bal.error:
            errors.append(f"moomoo: {mm_bal.error}")

    if errors:
        combined.error = "; ".join(errors)
    result["combined"] = combined
    return result, _merge_holdings(all_holdings)


def fetch_balances(sources: Optional[List[str]] = None) -> Dict[str, BalanceInfo]:
    """Fetch account balances from both brokers.

    Returns dict: {'longport': BalanceInfo, 'moomoo': BalanceInfo, 'combined': BalanceInfo}
    """
    if sources is None:
        sources = ["longport", "moomoo"]

    result: Dict[str, BalanceInfo] = {}
    combined = BalanceInfo()
    errors: List[str] = []

    if "longport" in sources:
        lp_bal, _ = _longport_holdings_and_balance()
        result["longport"] = lp_bal
        combined.net_assets += lp_bal.net_assets
        combined.cash += lp_bal.cash
        combined.market_value += lp_bal.market_value
        combined.buying_power += lp_bal.buying_power
        combined.day_pnl += lp_bal.day_pnl
        if lp_bal.error:
            errors.append(f"longport: {lp_bal.error}")

    if "moomoo" in sources:
        mm_bal, _ = _moomoo_holdings_and_balance()
        result["moomoo"] = mm_bal
        combined.net_assets += mm_bal.net_assets
        combined.cash += mm_bal.cash
        combined.market_value += mm_bal.market_value
        combined.buying_power += mm_bal.buying_power
        combined.day_pnl += mm_bal.day_pnl
        if mm_bal.error:
            errors.append(f"moomoo: {mm_bal.error}")

    if errors:
        combined.error = "; ".join(errors)
    result["combined"] = combined
    return result


def fetch_tickers_only(sources: Optional[List[str]] = None) -> List[str]:
    """Quick fetch of just ticker symbols from both brokers (no quotes)."""
    holdings = fetch_holdings(sources)
    return list(holdings.keys())


def fetch_quotes_longport(tickers: List[str]) -> Dict[str, Any]:
    """Fetch quotes via LongPort QuoteContext.

    Requires LongPort quote entitlement. If unavailable, caller should fall back.
    """
    result: Dict[str, Any] = {}
    if not tickers:
        return result
    try:
        _, quote_ctx = get_longport_ctx()
        syms = [f"{t}.US" for t in tickers]
        _null = io.StringIO()
        with suppress_stdio_fds():
            with redirect_stdout(_null), redirect_stderr(_null):
                quotes = quote_ctx.quote(syms)
        for q in quotes:
            t = q.symbol.replace(".US", "")
            result[t] = {
                "price": float(q.last_done),
                "prev_close": float(q.prev_close),
                "volume": int(getattr(q, "volume", 0) or 0),
                "turnover": float(getattr(q, "turnover", 0.0) or 0.0),
                "source": "longport",
            }
    except Exception:
        pass
    return result
