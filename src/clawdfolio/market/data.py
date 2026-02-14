"""Market data fetching via yfinance."""

from __future__ import annotations

import logging
import math
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from ..core.types import Quote, Symbol

logger = logging.getLogger(__name__)

# Lazy yfinance import
_yf = None


def _import_yf():
    global _yf
    if _yf is None:
        import yfinance as yf
        _yf = yf
    return _yf


# ---------------------------------------------------------------------------
# Thread-safe in-memory cache
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _cached(key: str, ttl: float, fn):
    """Return cached value if within TTL, else call fn and cache."""
    now = time.time()
    with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < ttl:
                return val
    val = fn()
    with _cache_lock:
        _cache[key] = (now, val)
    return val


def clear_cache() -> None:
    """Clear the market data cache."""
    with _cache_lock:
        _cache.clear()


# ---------------------------------------------------------------------------
# Ticker normalisation helper
# ---------------------------------------------------------------------------

def _yf_symbol(ticker: str) -> str:
    """Normalise a ticker for yfinance (e.g. ``BRK.B`` → ``BRK-B``)."""
    return ticker.replace(".", "-")


# ---------------------------------------------------------------------------
# Price & history
# ---------------------------------------------------------------------------

def get_price(ticker: str) -> float | None:
    """Get current price via yfinance. Cached 5 minutes."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

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
            logger.debug("Failed to get price for %s", sym, exc_info=True)
            return None

    return _cached(f"price:{sym}", 300, _fetch)


def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Get price history. Cached 1 hour."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

    def _fetch():
        try:
            df = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=True)
            # Handle MultiIndex columns from yfinance (e.g., ('Close', 'AAPL'))
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
        except Exception:
            logger.debug("Failed to get history for %s", sym, exc_info=True)
            return pd.DataFrame()

    return _cached(f"hist:{sym}:{period}", 3600, _fetch)


def get_history_multi(tickers: list[str], period: str = "1y") -> pd.DataFrame:
    """Get price history for multiple tickers. Cached 1 hour."""
    yf = _import_yf()
    syms = [_yf_symbol(t) for t in tickers]
    sym_to_ticker = dict(zip(syms, tickers, strict=False))
    key = f"hist_multi:{','.join(sorted(syms))}:{period}"

    def _fetch():
        try:
            df = yf.download(syms, period=period, interval="1d", progress=False, auto_adjust=True)
            if df is None or df.empty:
                return pd.DataFrame()

            if isinstance(df.columns, pd.MultiIndex):
                # MultiIndex layout: first level is OHLCV, second level is ticker.
                if "Close" not in df.columns.get_level_values(0):
                    return pd.DataFrame()
                close = df["Close"]
                if isinstance(close, pd.Series):
                    close = close.to_frame(name=tickers[0] if tickers else "Close")
                else:
                    close = close.rename(columns=sym_to_ticker)
                return close

            # Single ticker may come back as OHLCV columns; normalize to one "ticker" column.
            if "Close" in df.columns and len(tickers) == 1:
                return df[["Close"]].rename(columns={"Close": tickers[0]})

            return df.rename(columns=sym_to_ticker)
        except Exception:
            logger.debug("Failed to get multi-history", exc_info=True)
            return pd.DataFrame()

    return _cached(key, 3600, _fetch)


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

def get_quote(ticker: str) -> Quote | None:
    """Get a Quote object for a ticker."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

    try:
        t = yf.Ticker(sym)
        info = t.info
        fast = getattr(t, "fast_info", None)

        price = None
        prev_close = None

        if fast:
            price = getattr(fast, "last_price", None)
            prev_close = getattr(fast, "previous_close", None)

        if price is None:
            price = info.get("currentPrice") or info.get("regularMarketPrice")
        if prev_close is None:
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

        # Fallback when fast_info/info misses price fields.
        if price is None or prev_close is None:
            try:
                hist = t.history(period="5d", interval="1d", auto_adjust=False)
                if isinstance(getattr(hist, "columns", None), pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                closes = hist["Close"].dropna() if hist is not None and not hist.empty and "Close" in hist else None
                if closes is not None and not closes.empty:
                    if price is None:
                        price = float(closes.iloc[-1])
                    if prev_close is None:
                        if len(closes) >= 2:
                            prev_close = float(closes.iloc[-2])
                        else:
                            prev_close = float(closes.iloc[-1])
            except Exception:
                pass

        if price is None:
            return None

        return Quote(
            symbol=Symbol(ticker=ticker),
            price=Decimal(str(price)),
            prev_close=Decimal(str(prev_close)) if prev_close else None,
            open=Decimal(str(info.get("open") or info.get("regularMarketOpen") or 0)) or None,
            high=Decimal(str(info.get("dayHigh") or info.get("regularMarketDayHigh") or 0)) or None,
            low=Decimal(str(info.get("dayLow") or info.get("regularMarketDayLow") or 0)) or None,
            volume=info.get("volume") or info.get("regularMarketVolume") or 0,
            timestamp=datetime.now(),
            source="yfinance",
        )
    except Exception:
        logger.debug("Failed to get quote for %s", sym, exc_info=True)
        return None


def get_quotes_yfinance(tickers: list[str]) -> dict[str, Quote]:
    """Get quotes for multiple tickers.

    Uses ``yfinance.download`` for batch fetching when possible, falling
    back to individual ``get_quote`` calls for any tickers that fail.
    """
    if not tickers:
        return {}

    yf = _import_yf()
    result: dict[str, Quote] = {}
    syms = [_yf_symbol(t) for t in tickers]
    sym_to_ticker = dict(zip(syms, tickers, strict=False))

    try:
        df = yf.download(syms, period="5d", interval="1d", progress=False, auto_adjust=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                close_df = df["Close"] if "Close" in df.columns.get_level_values(0) else None
            elif "Close" in df.columns:
                close_df = df[["Close"]].rename(columns={"Close": syms[0]}) if len(syms) == 1 else None
            else:
                close_df = None

            if close_df is not None:
                for sym in syms:
                    col = close_df[sym] if sym in close_df.columns else None
                    if col is None:
                        continue
                    closes = col.dropna()
                    if closes.empty:
                        continue
                    price = float(closes.iloc[-1])
                    prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else price
                    ticker = sym_to_ticker[sym]
                    result[ticker] = Quote(
                        symbol=Symbol(ticker=ticker),
                        price=Decimal(str(price)),
                        prev_close=Decimal(str(prev_close)),
                        timestamp=datetime.now(),
                        source="yfinance",
                    )
    except Exception:
        logger.debug("Batch quote download failed, falling back to individual", exc_info=True)

    # Fallback for any tickers not resolved via batch
    for ticker in tickers:
        if ticker not in result:
            quote = get_quote(ticker)
            if quote:
                result[ticker] = quote

    return result


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

@dataclass
class NewsItem:
    """News item data."""
    title: str
    publisher: str = ""
    link: str = ""
    published: datetime | None = None
    content_type: str = ""
    summary: str = ""
    ticker: str = ""


@dataclass
class OptionQuoteData:
    """Option quote with optional Greeks."""

    ticker: str
    expiry: str
    strike: float
    option_type: str = "C"
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None
    open_interest: float | None = None
    volume: float | None = None
    source: str = ""

    @property
    def ref_price(self) -> float | None:
        """Reference price used for trigger checks."""
        if self.last is not None and self.last > 0:
            return self.last
        if self.bid is not None and self.ask is not None and self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        if self.bid is not None and self.bid > 0:
            return self.bid
        if self.ask is not None and self.ask > 0:
            return self.ask
        return None


@dataclass
class OptionChainData:
    """Lightweight option chain representation."""

    ticker: str
    expiry: str
    calls: pd.DataFrame
    puts: pd.DataFrame


def get_news(ticker: str, max_items: int = 5) -> list[NewsItem]:
    """Get recent news for a ticker."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

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
                except (ValueError, TypeError):
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
        logger.debug("Failed to get news for %s", sym, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Options helpers
# ---------------------------------------------------------------------------

def _moomoo_available(host: str = "127.0.0.1", port: int = 11111) -> bool:
    """Check if moomoo OpenD is reachable."""
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (TimeoutError, OSError):
        return False


def _moomoo_option_code(
    ticker: str,
    expiry: str,
    strike: float,
    option_type: str = "C",
) -> str:
    """Build moomoo option symbol, e.g. US.TQQQ260618C60000."""
    dt = datetime.strptime(expiry, "%Y-%m-%d")
    return f"US.{ticker}{dt.strftime('%y%m%d')}{option_type.upper()}{int(round(strike * 1000))}"


def _safe_float(value: Any, default: float | None = None) -> float | None:
    """Convert to float with NaN handling."""
    try:
        num = float(value)
        return num if not math.isnan(num) else default
    except (TypeError, ValueError):
        return default


def _get_option_quote_moomoo(
    ticker: str,
    expiry: str,
    strike: float,
    option_type: str = "C",
) -> OptionQuoteData | None:
    """Fetch a single option quote + Greeks from moomoo."""
    if not _moomoo_available():
        return None

    try:
        from futu.common import ft_logger

        ft_logger.logger.console_level = 50

        from futu import RET_OK, OpenQuoteContext

        code = _moomoo_option_code(ticker, expiry, strike, option_type)
        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        try:
            ret, data = ctx.get_market_snapshot(code_list=[code])
            if ret != RET_OK or data is None or data.empty:
                return None

            row = data.iloc[0]
            bid = _safe_float(row.get("bid_price"))
            ask = _safe_float(row.get("ask_price"))
            last = _safe_float(row.get("last_price"))
            if bid is None and ask is None and last is None:
                return None

            return OptionQuoteData(
                ticker=ticker,
                expiry=expiry,
                strike=strike,
                option_type=option_type.upper(),
                bid=bid,
                ask=ask,
                last=last,
                implied_volatility=_safe_float(row.get("option_implied_volatility")),
                delta=_safe_float(row.get("option_delta")),
                gamma=_safe_float(row.get("option_gamma")),
                theta=_safe_float(row.get("option_theta")),
                vega=_safe_float(row.get("option_vega")),
                rho=_safe_float(row.get("option_rho")),
                open_interest=_safe_float(row.get("option_open_interest")),
                volume=_safe_float(row.get("volume")),
                source="moomoo",
            )
        finally:
            ctx.close()
    except Exception:
        logger.debug("moomoo option quote failed for %s", ticker, exc_info=True)
        return None


def get_option_quote(
    ticker: str,
    expiry: str,
    strike: float,
    option_type: str = "C",
) -> OptionQuoteData | None:
    """Get option quote with Greeks. moomoo first, yfinance fallback."""
    opt = option_type.upper()
    key = f"opt_quote:{ticker}:{expiry}:{strike}:{opt}"

    def _fetch() -> OptionQuoteData | None:
        quote = _get_option_quote_moomoo(ticker, expiry, strike, opt)
        if quote is not None:
            return quote

        yf = _import_yf()
        sym = _yf_symbol(ticker)
        try:
            chain = yf.Ticker(sym).option_chain(expiry)
            table = chain.calls if opt == "C" else chain.puts
            row = table.loc[table["strike"] == strike].head(1)
            if row.empty:
                return None

            r = row.iloc[0]
            return OptionQuoteData(
                ticker=ticker,
                expiry=expiry,
                strike=strike,
                option_type=opt,
                bid=_safe_float(r.get("bid")),
                ask=_safe_float(r.get("ask")),
                last=_safe_float(r.get("lastPrice")),
                implied_volatility=_safe_float(r.get("impliedVolatility")),
                open_interest=_safe_float(r.get("openInterest")),
                volume=_safe_float(r.get("volume")),
                source="yfinance",
            )
        except Exception:
            logger.debug("yfinance option quote failed for %s", ticker, exc_info=True)
            return None

    return _cached(key, 300, _fetch)


def _get_option_chain_moomoo(ticker: str, expiry: str) -> OptionChainData | None:
    """Fetch full option chain from moomoo with quotes + Greeks."""
    if not _moomoo_available():
        return None

    try:
        from futu.common import ft_logger

        ft_logger.logger.console_level = 50

        from futu import RET_OK, OpenQuoteContext

        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        try:
            ret, chain = ctx.get_option_chain(code=f"US.{ticker}", start=expiry, end=expiry)
            if ret != RET_OK or chain is None or chain.empty:
                return None

            codes = chain["code"].tolist()
            if not codes:
                return None

            ret, snap = ctx.get_market_snapshot(code_list=codes)
            if ret != RET_OK or snap is None or snap.empty:
                return None

            calls_data: list[dict[str, Any]] = []
            puts_data: list[dict[str, Any]] = []
            for _, row in snap.iterrows():
                entry = {
                    "contractSymbol": row.get("code", ""),
                    "strike": _safe_float(row.get("option_strike_price"), 0),
                    "bid": _safe_float(row.get("bid_price")),
                    "ask": _safe_float(row.get("ask_price")),
                    "lastPrice": _safe_float(row.get("last_price")),
                    "volume": _safe_float(row.get("volume"), 0),
                    "openInterest": _safe_float(row.get("option_open_interest"), 0),
                    "impliedVolatility": _safe_float(row.get("option_implied_volatility")),
                    "delta": _safe_float(row.get("option_delta")),
                    "gamma": _safe_float(row.get("option_gamma")),
                    "theta": _safe_float(row.get("option_theta")),
                    "vega": _safe_float(row.get("option_vega")),
                }
                opt_type = str(row.get("option_type", "")).upper()
                if opt_type == "CALL":
                    calls_data.append(entry)
                elif opt_type == "PUT":
                    puts_data.append(entry)

            calls_df = (
                pd.DataFrame(calls_data).sort_values("strike").reset_index(drop=True)
                if calls_data
                else pd.DataFrame()
            )
            puts_df = (
                pd.DataFrame(puts_data).sort_values("strike").reset_index(drop=True)
                if puts_data
                else pd.DataFrame()
            )
            return OptionChainData(ticker=ticker, expiry=expiry, calls=calls_df, puts=puts_df)
        finally:
            ctx.close()
    except Exception:
        logger.debug("moomoo option chain failed for %s", ticker, exc_info=True)
        return None


def get_option_chain(ticker: str, expiry: str) -> OptionChainData | None:
    """Get option chain for a ticker and expiry date. moomoo first, yfinance fallback."""
    key = f"opt_chain:{ticker}:{expiry}"

    def _fetch() -> OptionChainData | None:
        chain = _get_option_chain_moomoo(ticker, expiry)
        if chain is not None:
            return chain

        yf = _import_yf()
        sym = _yf_symbol(ticker)
        try:
            raw_chain = yf.Ticker(sym).option_chain(expiry)
            calls = raw_chain.calls if hasattr(raw_chain, "calls") else pd.DataFrame()
            puts = raw_chain.puts if hasattr(raw_chain, "puts") else pd.DataFrame()
            if calls is None:
                calls = pd.DataFrame()
            if puts is None:
                puts = pd.DataFrame()
            return OptionChainData(
                ticker=ticker,
                expiry=expiry,
                calls=calls.reset_index(drop=True),
                puts=puts.reset_index(drop=True),
            )
        except Exception:
            logger.debug("yfinance option chain failed for %s", ticker, exc_info=True)
            return None

    return _cached(key, 300, _fetch)


def get_option_expiries(ticker: str) -> list[str]:
    """Get available option expiry dates for ticker."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)
    try:
        expiries = yf.Ticker(sym).options
        return list(expiries) if expiries else []
    except Exception:
        logger.debug("Failed to get option expiries for %s", sym, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def get_earnings_date(ticker: str) -> tuple[datetime, str] | None:
    """Get next earnings date and timing (BMO/AMC/TBD)."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

    try:
        t = yf.Ticker(sym)
        cal = t.calendar
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
            dt = ed.to_pydatetime()
        else:
            dt = datetime.fromisoformat(str(ed)[:10])

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
        logger.debug("Failed to get earnings date for %s", sym, exc_info=True)
        return None


def get_sector(ticker: str) -> str | None:
    """Get sector from yfinance. Cached 1 hour."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

    def _fetch():
        try:
            return yf.Ticker(sym).info.get("sector") or None
        except Exception:
            return None

    return _cached(f"sector:{sym}", 3600, _fetch)


def get_sector_and_industry(ticker: str) -> tuple[str, str]:
    """Get sector and industry. Cached 1 hour."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

    def _fetch():
        try:
            info = yf.Ticker(sym).info
            return info.get("sector", ""), info.get("industry", "")
        except Exception:
            return "", ""

    return _cached(f"sec_ind:{sym}", 3600, _fetch)


def get_stock_info(ticker: str) -> dict[str, Any]:
    """Get basic stock info (name, sector, marketCap). Cached 1 hour."""
    yf = _import_yf()
    sym = _yf_symbol(ticker)

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
