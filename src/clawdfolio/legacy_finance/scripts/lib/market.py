"""Market data functions with caching (yfinance-based)."""

from __future__ import annotations

import socket
import time
import io
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

_yf = None


def _import_yf():
    global _yf
    if _yf is None:
        import yfinance as yf
        _yf = yf
    return _yf


# Simple in-memory cache
_cache: Dict[str, Tuple[float, Any]] = {}


def _cached(key: str, ttl: float, fn):
    """Return cached value if within TTL, else call fn and cache."""
    now = time.time()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < ttl:
            return val
    val = fn()
    _cache[key] = (now, val)
    return val


def get_price(ticker: str) -> Optional[float]:
    """Get current price via yfinance. Cached 5 minutes."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

    def _fetch():
        try:
            t = yf.Ticker(sym)
            fi = getattr(t, "fast_info", None)
            if fi:
                p = getattr(fi, "last_price", None)
                if p and float(p) > 0:
                    return float(p)
            info = t.info
            return float(info.get("currentPrice") or info.get("regularMarketPrice") or 0) or None
        except Exception:
            return None

    return _cached(f"price:{sym}", 300, _fetch)


def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Get price history. Cached 1 hour."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

    def _fetch():
        try:
            # Keep DataFrame shape even for single ticker callers.
            return yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=True)
        except Exception:
            return pd.DataFrame()

    return _cached(f"hist:{sym}:{period}", 3600, _fetch)


def get_history_multi(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """Get price history for multiple tickers. Cached 1 hour."""
    yf = _import_yf()
    syms = [t.replace(".", "-") for t in tickers]
    key = f"hist_multi:{','.join(sorted(syms))}:{period}"

    def _fetch():
        try:
            df = yf.download(syms, period=period, interval="1d", progress=False, auto_adjust=True)
            if len(syms) == 1:
                df = df[["Close"]].rename(columns={"Close": syms[0]})
            elif isinstance(df.columns, pd.MultiIndex):
                df = df["Close"]
            return df
        except Exception:
            return pd.DataFrame()

    return _cached(key, 3600, _fetch)


def get_earnings_date(ticker: str) -> Optional[Tuple[date, str]]:
    """Get next earnings date and timing (BMO/AMC/TBD)."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")
    try:
        t = yf.Ticker(sym)
        # yfinance may print transient HTTP noise to stderr for some tickers.
        # Keep callers' stdout/stderr clean and fail silently here.
        _sink = io.StringIO()
        with redirect_stdout(_sink), redirect_stderr(_sink):
            cal = t.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed is None:
                return None
            if isinstance(ed, list):
                ed = ed[0] if ed else None
            if ed is None:
                return None
            if hasattr(ed, "to_pydatetime"):
                dt = ed.to_pydatetime().date()
            else:
                dt = datetime.fromisoformat(str(ed)[:10]).date()

            timing = cal.get("Earnings Time", "TBD")
            timing_s = str(timing).lower()
            if timing_s in ("bmo", "before market open", "pre"):
                return dt, "BMO"
            if timing_s in ("amc", "after market close", "post"):
                return dt, "AMC"
            return dt, "TBD"
        if cal is None or getattr(cal, "empty", True):
            return None
        if "Earnings Date" not in cal.index:
            return None
        ed = cal.loc["Earnings Date"]
        if hasattr(ed, "iloc"):
            ed = ed.iloc[0]
        if ed is None or (isinstance(ed, float) and str(ed) == "nan"):
            return None
        if hasattr(ed, "to_pydatetime"):
            dt = ed.to_pydatetime().date()
        else:
            dt = datetime.fromisoformat(str(ed)[:10]).date()

        timing = "TBD"
        if "Earnings Time" in cal.index:
            et = cal.loc["Earnings Time"]
            if hasattr(et, "iloc"):
                et = et.iloc[0]
            if et and str(et).lower() in ("bmo", "before market open", "pre"):
                timing = "BMO"
            elif et and str(et).lower() in ("amc", "after market close", "post"):
                timing = "AMC"
        return dt, timing
    except Exception:
        return None


def get_sector(ticker: str) -> Optional[str]:
    """Get sector from yfinance. Cached 1 hour."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

    def _fetch():
        try:
            return yf.Ticker(sym).info.get("sector") or None
        except Exception:
            return None

    return _cached(f"sector:{sym}", 3600, _fetch)


def get_sector_and_industry(ticker: str) -> Tuple[str, str]:
    """Get sector and industry. Cached 1 hour."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

    def _fetch():
        try:
            info = yf.Ticker(sym).info
            return info.get("sector", ""), info.get("industry", "")
        except Exception:
            return "", ""

    return _cached(f"sec_ind:{sym}", 3600, _fetch)


def get_stock_info(ticker: str) -> Dict[str, Any]:
    """Get basic stock info (name, sector, marketCap). Cached 1 hour."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

    def _fetch():
        try:
            info = yf.Ticker(sym).info
            return {
                "name": info.get("shortName", info.get("longName", ticker)),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "marketCap": info.get("marketCap", 0),
            }
        except Exception:
            return {"name": ticker, "sector": "", "industry": "", "marketCap": 0}

    return _cached(f"info:{sym}", 3600, _fetch)


@dataclass
class NewsItem:
    title: str
    publisher: str = ""
    link: str = ""
    published: Optional[datetime] = None
    content_type: str = ""
    summary: str = ""
    ticker: str = ""


def get_news(ticker: str, max_items: int = 5) -> List[NewsItem]:
    """Get recent news for a ticker."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")
    try:
        t = yf.Ticker(sym)
        news = t.news
        if not news:
            return []

        result = []
        for item in news[:max_items]:
            content = item.get("content", item)

            pub_time = None
            if "pubDate" in content:
                try:
                    pub_time = datetime.fromisoformat(content["pubDate"].replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass
            elif "providerPublishTime" in item:
                pub_time = datetime.fromtimestamp(item["providerPublishTime"])

            provider = content.get("provider", {})
            publisher = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)

            link = ""
            if "canonicalUrl" in content and isinstance(content["canonicalUrl"], dict):
                link = content["canonicalUrl"].get("url", "")
            elif "link" in item:
                link = item["link"]

            title = content.get("title", item.get("title", ""))
            if not title:
                continue

            result.append(NewsItem(
                title=title,
                publisher=publisher,
                link=link,
                published=pub_time,
                content_type=content.get("contentType", item.get("type", "")),
                summary=content.get("summary", ""),
                ticker=ticker,
            ))
        return result
    except Exception:
        return []


# ==================== moomoo option helpers ====================

def _moomoo_available() -> bool:
    """Check if moomoo OpenD is reachable."""
    try:
        with socket.create_connection(("127.0.0.1", 11111), timeout=2.0):
            return True
    except Exception:
        return False


def _moomoo_option_code(ticker: str, expiry: str, strike: float, opt_type: str = "C") -> str:
    """Build moomoo option symbol, e.g. US.TQQQ260618C60000."""
    dt = datetime.strptime(expiry, "%Y-%m-%d")
    return f"US.{ticker}{dt.strftime('%y%m%d')}{opt_type.upper()}{int(round(strike * 1000))}"


def _safe_float(val, default=None):
    try:
        v = float(val)
        return v if v == v else default  # NaN check
    except (ValueError, TypeError):
        return default


def _get_option_quote_moomoo(
    ticker: str, expiry: str, strike: float, opt_type: str = "C",
) -> Optional[Dict[str, Any]]:
    """Fetch single option quote + Greeks from moomoo."""
    if not _moomoo_available():
        return None
    try:
        from futu.common import ft_logger
        ft_logger.logger.console_level = 50
        from futu import OpenQuoteContext, RET_OK

        code = _moomoo_option_code(ticker, expiry, strike, opt_type)
        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        try:
            ret, data = ctx.get_market_snapshot(code_list=[code])
            if ret != RET_OK or data.empty:
                return None
            row = data.iloc[0]
            bid = _safe_float(row.get("bid_price"))
            ask = _safe_float(row.get("ask_price"))
            last = _safe_float(row.get("last_price"))
            if bid is None and ask is None and last is None:
                return None
            return {
                "bid": bid, "ask": ask, "last": last,
                "iv": _safe_float(row.get("option_implied_volatility")),
                "delta": _safe_float(row.get("option_delta")),
                "gamma": _safe_float(row.get("option_gamma")),
                "theta": _safe_float(row.get("option_theta")),
                "vega": _safe_float(row.get("option_vega")),
                "rho": _safe_float(row.get("option_rho")),
                "oi": _safe_float(row.get("option_open_interest")),
                "volume": _safe_float(row.get("volume")),
                "source": "moomoo",
            }
        finally:
            ctx.close()
    except Exception:
        return None


def get_option_quote(
    ticker: str, expiry: str, strike: float, opt_type: str = "C",
) -> Optional[Dict[str, Any]]:
    """Get option quote with Greeks. moomoo first, yfinance fallback.

    Returns dict: bid, ask, last, iv, delta, gamma, theta, vega, oi, volume, source
    """
    key = f"optquote:{ticker}:{expiry}:{strike}:{opt_type}"

    def _fetch():
        result = _get_option_quote_moomoo(ticker, expiry, strike, opt_type)
        if result is not None:
            return result
        # yfinance fallback
        yf = _import_yf()
        sym = ticker.replace(".", "-")
        try:
            oc = yf.Ticker(sym).option_chain(expiry)
            df = oc.calls if opt_type.upper() == "C" else oc.puts
            row = df.loc[df["strike"] == strike].head(1)
            if row.empty:
                return None
            r = row.iloc[0]
            return {
                "bid": _safe_float(r.get("bid")),
                "ask": _safe_float(r.get("ask")),
                "last": _safe_float(r.get("lastPrice")),
                "iv": _safe_float(r.get("impliedVolatility")),
                "delta": None, "gamma": None, "theta": None,
                "vega": None, "rho": None,
                "oi": _safe_float(r.get("openInterest")),
                "volume": _safe_float(r.get("volume")),
                "source": "yfinance",
            }
        except Exception:
            return None

    return _cached(key, 300, _fetch)


# ==================== option chain ====================

class _OptionChain:
    """Lightweight option chain mirroring yfinance's OptionChain."""
    def __init__(self, calls: pd.DataFrame, puts: pd.DataFrame):
        self.calls = calls
        self.puts = puts


def _get_option_chain_moomoo(ticker: str, expiry: str) -> Optional[_OptionChain]:
    """Fetch full option chain from moomoo with quotes + Greeks."""
    if not _moomoo_available():
        return None
    try:
        from futu.common import ft_logger
        ft_logger.logger.console_level = 50
        from futu import OpenQuoteContext, RET_OK

        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        try:
            ret, chain = ctx.get_option_chain(
                code=f"US.{ticker}", start=expiry, end=expiry,
            )
            if ret != RET_OK or chain.empty:
                return None
            codes = chain["code"].tolist()
            if not codes:
                return None

            # Batch snapshot for all contracts
            ret, snap = ctx.get_market_snapshot(code_list=codes)
            if ret != RET_OK or snap.empty:
                return None

            calls_data, puts_data = [], []
            for _, row in snap.iterrows():
                opt_type = row.get("option_type", "")
                entry = {
                    "contractSymbol": row.get("code", ""),
                    "strike": _safe_float(row.get("option_strike_price"), 0),
                    "bid": _safe_float(row.get("bid_price")),
                    "ask": _safe_float(row.get("ask_price")),
                    "lastPrice": _safe_float(row.get("last_price")),
                    "volume": _safe_float(row.get("volume"), 0),
                    "openInterest": _safe_float(row.get("option_open_interest"), 0),
                    "impliedVolatility": _safe_float(row.get("option_implied_volatility")),
                }
                if opt_type == "CALL":
                    calls_data.append(entry)
                elif opt_type == "PUT":
                    puts_data.append(entry)

            calls_df = (
                pd.DataFrame(calls_data).sort_values("strike").reset_index(drop=True)
                if calls_data else pd.DataFrame()
            )
            puts_df = (
                pd.DataFrame(puts_data).sort_values("strike").reset_index(drop=True)
                if puts_data else pd.DataFrame()
            )
            return _OptionChain(calls_df, puts_df)
        finally:
            ctx.close()
    except Exception:
        return None


def get_option_chain(ticker: str, expiry: str) -> Optional[Any]:
    """Get option chain for a ticker and expiry date. moomoo first, yfinance fallback."""
    # Try moomoo first
    result = _get_option_chain_moomoo(ticker, expiry)
    if result is not None:
        return result
    # yfinance fallback
    yf = _import_yf()
    sym = ticker.replace(".", "-")
    try:
        t = yf.Ticker(sym)
        return t.option_chain(expiry)
    except Exception:
        return None


def risk_free_rate() -> float:
    """Get current 10Y Treasury yield from ^TNX. Falls back to 4.5%."""
    yf = _import_yf()

    def _fetch():
        try:
            t = yf.Ticker("^TNX")
            h = t.history(period="5d")
            if h is not None and not h.empty:
                last = float(h["Close"].iloc[-1])
                if 0 < last < 20:
                    return last / 100.0  # ^TNX quotes in percent
            return 0.045
        except Exception:
            return 0.045

    return _cached("risk_free_rate", 3600, _fetch)


def bid1_price(ticker: str) -> Tuple[Optional[float], str]:
    """Return (bid_price, source_string) for a ticker."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")
    try:
        t = yf.Ticker(sym)
        fi = getattr(t, "fast_info", None)
        b = getattr(fi, "bid", None) if fi is not None else None
        if b:
            b = float(b)
            if b > 0:
                return b, "Yahoo_fast_info"
    except Exception:
        pass

    try:
        info = yf.Ticker(sym).info
        b = info.get("bid")
        if b:
            b = float(b)
            if b > 0:
                return b, "Yahoo_info"
    except Exception:
        pass

    return None, "src_tried=Yahoo_fast_info,Yahoo_info"
