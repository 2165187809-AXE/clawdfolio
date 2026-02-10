"""Market data fetching via yfinance."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from ..core.types import Quote, Symbol

# Lazy yfinance import
_yf = None


def _import_yf():
    global _yf
    if _yf is None:
        import yfinance as yf
        _yf = yf
    return _yf


# Simple in-memory cache
_cache: dict[str, tuple[float, Any]] = {}


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


def clear_cache() -> None:
    """Clear the market data cache."""
    _cache.clear()


def get_price(ticker: str) -> float | None:
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
            df = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=True)
            # Handle MultiIndex columns from yfinance (e.g., ('Close', 'AAPL'))
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
        except Exception:
            return pd.DataFrame()

    return _cached(f"hist:{sym}:{period}", 3600, _fetch)


def get_history_multi(tickers: list[str], period: str = "1y") -> pd.DataFrame:
    """Get price history for multiple tickers. Cached 1 hour."""
    yf = _import_yf()
    syms = [t.replace(".", "-") for t in tickers]
    sym_to_ticker = {sym: ticker for sym, ticker in zip(syms, tickers, strict=False)}
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
            return pd.DataFrame()

    return _cached(key, 3600, _fetch)


def get_quote(ticker: str) -> Quote | None:
    """Get a Quote object for a ticker."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

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
        return None


def get_quotes_yfinance(tickers: list[str]) -> dict[str, Quote]:
    """Get quotes for multiple tickers."""
    result = {}
    for ticker in tickers:
        quote = get_quote(ticker)
        if quote:
            result[ticker] = quote
    return result


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


def get_news(ticker: str, max_items: int = 5) -> list[NewsItem]:
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


def get_earnings_date(ticker: str) -> tuple[datetime, str] | None:
    """Get next earnings date and timing (BMO/AMC/TBD)."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

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
        return None


def get_sector(ticker: str) -> str | None:
    """Get sector from yfinance. Cached 1 hour."""
    yf = _import_yf()
    sym = ticker.replace(".", "-")

    def _fetch():
        try:
            return yf.Ticker(sym).info.get("sector") or None
        except Exception:
            return None

    return _cached(f"sector:{sym}", 3600, _fetch)


def get_sector_and_industry(ticker: str) -> tuple[str, str]:
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


def get_stock_info(ticker: str) -> dict[str, Any]:
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
