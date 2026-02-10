"""Tests for yfinance data normalization helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from clawdfolio.market import data as market_data


class _FakeYF:
    def __init__(self, download_df: pd.DataFrame | None = None, ticker_obj=None):
        self._download_df = download_df
        self._ticker_obj = ticker_obj

    def download(self, *_args, **_kwargs):
        return self._download_df

    def Ticker(self, _sym):
        return self._ticker_obj


class _FakeTicker:
    def __init__(self, info: dict, fast_info=None, history_df: pd.DataFrame | None = None):
        self.info = info
        self.fast_info = fast_info
        self._history_df = history_df if history_df is not None else pd.DataFrame()

    def history(self, *_args, **_kwargs):
        return self._history_df


def test_get_history_multi_single_ticker_close_normalization(monkeypatch):
    market_data.clear_cache()
    idx = pd.date_range("2026-01-01", periods=3, freq="D")
    raw = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000, 1200, 1100],
        },
        index=idx,
    )
    monkeypatch.setattr(market_data, "_import_yf", lambda: _FakeYF(download_df=raw))

    out = market_data.get_history_multi(["AAPL"], period="1mo")

    assert list(out.columns) == ["AAPL"]
    assert float(out.iloc[-1, 0]) == 102.5


def test_get_history_multi_multiindex_close_extraction(monkeypatch):
    market_data.clear_cache()
    idx = pd.date_range("2026-01-01", periods=2, freq="D")
    cols = pd.MultiIndex.from_tuples(
        [
            ("Open", "AAPL"),
            ("Open", "MSFT"),
            ("Close", "AAPL"),
            ("Close", "MSFT"),
        ]
    )
    raw = pd.DataFrame(
        [
            [100.0, 200.0, 101.0, 201.0],
            [101.0, 201.0, 102.0, 202.0],
        ],
        index=idx,
        columns=cols,
    )
    monkeypatch.setattr(market_data, "_import_yf", lambda: _FakeYF(download_df=raw))

    out = market_data.get_history_multi(["AAPL", "MSFT"], period="1mo")

    assert list(out.columns) == ["AAPL", "MSFT"]
    assert float(out.iloc[-1]["AAPL"]) == 102.0
    assert float(out.iloc[-1]["MSFT"]) == 202.0


def test_get_quote_prev_close_falls_back_to_history(monkeypatch):
    idx = pd.date_range("2026-01-01", periods=3, freq="D")
    history = pd.DataFrame({"Close": [99.0, 101.0, 103.0]}, index=idx)
    ticker = _FakeTicker(
        info={
            "open": 102.0,
            "dayHigh": 104.0,
            "dayLow": 100.0,
            "volume": 123456,
        },
        fast_info=SimpleNamespace(last_price=103.0, previous_close=None),
        history_df=history,
    )
    monkeypatch.setattr(market_data, "_import_yf", lambda: _FakeYF(ticker_obj=ticker))

    quote = market_data.get_quote("AAPL")

    assert quote is not None
    assert float(quote.price) == 103.0
    assert quote.prev_close is not None
    assert float(quote.prev_close) == 101.0
