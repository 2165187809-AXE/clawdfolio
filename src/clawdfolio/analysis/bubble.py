"""Market Bubble Index — composite sentiment + liquidity indicator."""

from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

TRADING_DAYS_YEAR = 252

SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLU", "XLB", "XLRE"]

SENTIMENT_WEIGHT = 0.6
LIQUIDITY_WEIGHT = 0.4

DANGER_THRESHOLD = 85


@dataclass
class IndicatorResult:
    """Result for a single bubble indicator."""

    name: str
    raw_value: float
    normalized_score: float
    percentile: float
    lookback_years: int


@dataclass
class BubbleIndexResult:
    """Complete bubble index result."""

    composite_score: float
    sentiment_score: float
    liquidity_score: float
    indicators: dict[str, IndicatorResult] = field(default_factory=dict)
    regime: str = "NORMAL"
    timestamp: str = ""


def _percentile_rank(value: float, history: pd.Series) -> float:
    """Compute percentile rank of value within history, scaled 0-100."""
    clean = history.dropna()
    if clean.empty:
        return 50.0
    return float((clean < value).sum() / len(clean) * 100)


def _safe_download(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Download yfinance data with error handling."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = yf.download(ticker, period=period, progress=False)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception:
        logger.warning("Failed to download %s", ticker)
        return pd.DataFrame()


def _get_close(df: pd.DataFrame) -> pd.Series:
    """Extract Close as a Series, handling yfinance 1.1.0 DataFrame quirk."""
    if df.empty:
        return pd.Series(dtype=float)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    return close.dropna()


# ── Indicator 1: QQQ 200D Deviation ──────────────────────────────────────


def calc_qqq_deviation(lookback_years: int = 5) -> IndicatorResult | None:
    """QQQ deviation from 200-day SMA, normalized via percentile."""
    df = _safe_download("QQQ", period=f"{lookback_years}y")
    close = _get_close(df)
    if len(close) < 200:
        return None

    sma200 = close.rolling(200).mean()
    deviation = (close - sma200) / sma200
    deviation = deviation.dropna()
    if deviation.empty:
        return None

    current = float(deviation.iloc[-1])
    pct = _percentile_rank(current, deviation)

    return IndicatorResult(
        name="QQQ 200D Deviation",
        raw_value=current,
        normalized_score=pct,
        percentile=pct,
        lookback_years=lookback_years,
    )


# ── Indicator 2: Put/Call Ratio (FRED PCCE) ──────────────────────────────


def calc_put_call_ratio(lookback_years: int = 5) -> IndicatorResult | None:
    """CBOE equity put/call ratio from FRED. Inverted: low P/C = high bubble risk."""
    try:
        from fredapi import Fred
    except ImportError:
        logger.warning("fredapi not installed — skipping Put/Call ratio indicator")
        return None

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.warning("FRED_API_KEY not set — skipping Put/Call ratio indicator")
        return None

    try:
        fred = Fred(api_key=api_key)
        data = fred.get_series("PCCE")
    except Exception:
        logger.warning("Failed to fetch PCCE from FRED")
        return None

    if data is None or data.empty:
        return None

    end = pd.Timestamp.now()
    start = end - pd.DateOffset(years=lookback_years)
    data = data.loc[start:]
    data = data.dropna()

    if data.empty:
        return None

    current = float(data.iloc[-1])
    # Invert: low P/C = bullish = higher bubble risk
    pct = _percentile_rank(current, data)
    inverted_score = 100.0 - pct

    return IndicatorResult(
        name="Put/Call Ratio (PCCE)",
        raw_value=current,
        normalized_score=inverted_score,
        percentile=pct,
        lookback_years=lookback_years,
    )


# ── Indicator 3: VIX Level ───────────────────────────────────────────────


def calc_vix_level(lookback_years: int = 5) -> IndicatorResult | None:
    """VIX level — inverted: low VIX = complacency = higher bubble risk."""
    df = _safe_download("^VIX", period=f"{lookback_years}y")
    close = _get_close(df)
    if close.empty:
        return None

    current = float(close.iloc[-1])
    pct = _percentile_rank(current, close)
    inverted_score = 100.0 - pct

    return IndicatorResult(
        name="VIX Level",
        raw_value=current,
        normalized_score=inverted_score,
        percentile=pct,
        lookback_years=lookback_years,
    )


# ── Indicator 4: Sector Breadth ──────────────────────────────────────────


def calc_sector_breadth(lookback_years: int = 1) -> IndicatorResult | None:
    """Fraction of sector ETFs trading above their 200-day SMA."""
    above_count = 0
    total = 0

    for etf in SECTOR_ETFS:
        df = _safe_download(etf, period=f"{max(lookback_years, 2)}y")
        close = _get_close(df)
        if len(close) < 200:
            continue
        sma200 = close.rolling(200).mean().dropna()
        if sma200.empty:
            continue
        total += 1
        if float(close.iloc[-1]) > float(sma200.iloc[-1]):
            above_count += 1

    if total == 0:
        return None

    breadth = above_count / total
    score = breadth * 100

    return IndicatorResult(
        name="Sector Breadth",
        raw_value=breadth,
        normalized_score=score,
        percentile=score,
        lookback_years=lookback_years,
    )


# ── Indicator 5: Credit Spread HYG/IEF ───────────────────────────────────


def calc_credit_spread(lookback_years: int = 2) -> IndicatorResult | None:
    """HYG/IEF rolling 60d return correlation as credit spread proxy."""
    hyg = _safe_download("HYG", period=f"{lookback_years}y")
    ief = _safe_download("IEF", period=f"{lookback_years}y")

    hyg_close = _get_close(hyg)
    ief_close = _get_close(ief)

    if len(hyg_close) < 61 or len(ief_close) < 61:
        return None

    hyg_ret = hyg_close.pct_change().dropna()
    ief_ret = ief_close.pct_change().dropna()

    # Align on common dates
    common = hyg_ret.index.intersection(ief_ret.index)
    if len(common) < 61:
        return None

    hyg_ret = hyg_ret.loc[common]
    ief_ret = ief_ret.loc[common]

    corr = hyg_ret.rolling(60).corr(ief_ret).dropna()
    if corr.empty:
        return None

    current = float(corr.iloc[-1])
    pct = _percentile_rank(current, corr)
    # High correlation = tight spreads = risk-on = higher bubble risk
    score = pct

    return IndicatorResult(
        name="Credit Spread (HYG/IEF)",
        raw_value=current,
        normalized_score=score,
        percentile=pct,
        lookback_years=lookback_years,
    )


# ── Indicator 6: Yield Curve 10Y-2Y (FRED T10Y2Y) ───────────────────────


def calc_yield_curve(lookback_years: int = 5) -> IndicatorResult | None:
    """10Y-2Y yield spread from FRED. Normal/steep curve = risk-on = higher bubble risk."""
    try:
        from fredapi import Fred
    except ImportError:
        logger.warning("fredapi not installed — skipping Yield Curve indicator")
        return None

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.warning("FRED_API_KEY not set — skipping Yield Curve indicator")
        return None

    try:
        fred = Fred(api_key=api_key)
        data = fred.get_series("T10Y2Y")
    except Exception:
        logger.warning("Failed to fetch T10Y2Y from FRED")
        return None

    if data is None or data.empty:
        return None

    end = pd.Timestamp.now()
    start = end - pd.DateOffset(years=lookback_years)
    data = data.loc[start:]
    data = data.dropna()

    if data.empty:
        return None

    current = float(data.iloc[-1])
    pct = _percentile_rank(current, data)
    # Positive/steep = risk-on = higher bubble risk
    score = pct

    return IndicatorResult(
        name="Yield Curve (10Y-2Y)",
        raw_value=current,
        normalized_score=score,
        percentile=pct,
        lookback_years=lookback_years,
    )


# ── Composite ────────────────────────────────────────────────────────────


def _classify_regime(score: float) -> str:
    """Classify bubble regime based on composite score."""
    if score >= DANGER_THRESHOLD:
        return "DANGER"
    if score >= 60:
        return "ELEVATED"
    return "NORMAL"


def calculate_bubble_index(
    *,
    qqq_lookback: int = 5,
    put_call_lookback: int = 5,
    vix_lookback: int = 5,
    breadth_lookback: int = 1,
    credit_lookback: int = 2,
    yield_curve_lookback: int = 5,
) -> BubbleIndexResult:
    """Calculate the composite Market Bubble Index.

    Each indicator has a configurable lookback_years parameter.
    FRED-based indicators are skipped gracefully if fredapi is not installed
    or FRED_API_KEY is not set.

    Returns:
        BubbleIndexResult with composite, sentiment, and liquidity scores.
    """
    # Sentiment indicators: (calc_func, weight_within_sentiment, kwargs)
    sentiment_specs: list[tuple[str, float, IndicatorResult | None]] = [
        ("qqq_deviation", 0.30, calc_qqq_deviation(lookback_years=qqq_lookback)),
        ("put_call_ratio", 0.25, calc_put_call_ratio(lookback_years=put_call_lookback)),
        ("vix_level", 0.20, calc_vix_level(lookback_years=vix_lookback)),
        ("sector_breadth", 0.25, calc_sector_breadth(lookback_years=breadth_lookback)),
    ]

    # Liquidity indicators
    liquidity_specs: list[tuple[str, float, IndicatorResult | None]] = [
        ("credit_spread", 0.50, calc_credit_spread(lookback_years=credit_lookback)),
        ("yield_curve", 0.50, calc_yield_curve(lookback_years=yield_curve_lookback)),
    ]

    indicators: dict[str, IndicatorResult] = {}

    def _weighted_avg(specs: list[tuple[str, float, IndicatorResult | None]]) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for key, weight, result in specs:
            if result is not None:
                indicators[key] = result
                weighted_sum += weight * result.normalized_score
                total_weight += weight
        if total_weight == 0:
            return 50.0  # neutral fallback
        return weighted_sum / total_weight

    sentiment_score = _weighted_avg(sentiment_specs)
    liquidity_score = _weighted_avg(liquidity_specs)

    composite = SENTIMENT_WEIGHT * sentiment_score + LIQUIDITY_WEIGHT * liquidity_score
    composite = max(0.0, min(100.0, composite))

    return BubbleIndexResult(
        composite_score=round(composite, 2),
        sentiment_score=round(sentiment_score, 2),
        liquidity_score=round(liquidity_score, 2),
        indicators=indicators,
        regime=_classify_regime(composite),
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )


# ═══════════════════════════════════════════════════════════════════
# Drawdown Risk Score — integrated from Market-Bubble-Index-Dashboard
# ═══════════════════════════════════════════════════════════════════

import json
import numpy as np

# Default Dashboard API endpoint (GitHub Pages hosted JSON)
_DEFAULT_BUBBLE_HISTORY_URL = (
    "https://yichengyangportfolio.com/Market-Bubble-Index-Dashboard"
    "/data/bubble_history.json"
)


@dataclass
class BubbleRiskResult:
    """Composite bubble / drawdown risk result.

    This complements BubbleIndexResult with a drawdown-focused score
    that has 100% monotonicity with forward drawdowns (validated
    over 2014-2026).
    """

    drawdown_risk_score: float          # 0-100, primary signal
    composite_score: float              # 0-100, multi-indicator composite
    regime: str                         # "low_risk" | "moderate" | "elevated" | "high_risk"
    date: str                           # YYYY-MM-DD of the reading
    components: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def should_sell_cc(self) -> bool:
        """Whether risk is high enough to sell covered calls (>= 66)."""
        return self.drawdown_risk_score >= 66.0

    @property
    def cc_delta(self) -> float:
        """Recommended covered call delta based on risk level.

        Higher risk -> closer ATM (more premium, more protection).
        """
        if self.drawdown_risk_score >= 75:
            return 0.30  # aggressive protection
        if self.drawdown_risk_score >= 66:
            return 0.25  # optimal zone (backtested +3% alpha)
        return 0.20  # income mode (when manually overriding)


def _sma200_deviation(prices: pd.Series) -> float:
    """Current price deviation from 200-day SMA, as percentage."""
    if len(prices) < 200:
        return 0.0
    sma200 = float(prices.rolling(200).mean().iloc[-1])
    current = float(prices.iloc[-1])
    if sma200 == 0:
        return 0.0
    return (current - sma200) / sma200 * 100


def _trend_acceleration(prices: pd.Series, window: int = 60) -> float:
    """Measure how sharply prices are accelerating above trend."""
    if len(prices) < window + 20:
        return 0.0
    log_prices = np.log(prices.values[-window:])
    x = np.arange(window)
    coeffs = np.polyfit(x, log_prices, 2)
    return float(coeffs[0]) * 10000


def _volatility_regime(prices: pd.Series, window: int = 20) -> float:
    """Annualised realised volatility."""
    if len(prices) < window + 1:
        return 0.5
    log_ret = np.log(prices.values[1:] / prices.values[:-1])
    vol = float(np.std(log_ret[-window:]) * np.sqrt(252))
    return vol


def calculate_bubble_risk(
    ticker: str = "QQQ",
    period: str = "2y",
) -> BubbleRiskResult:
    """Calculate bubble risk score from live market data.

    Uses a simplified version of the full Dashboard model:
      - SMA-200 deviation (0-40 pts)
      - Trend acceleration (0-30 pts)
      - Volatility regime (0-30 pts)

    For the full model with GSADF / Markov regime detection,
    use ``fetch_bubble_risk()`` which reads from the Dashboard API.
    """
    df = _safe_download(ticker, period=period)
    close = _get_close(df)
    if close.empty or len(close) < 200:
        logger.warning("Insufficient data for %s — returning neutral score", ticker)
        return BubbleRiskResult(
            drawdown_risk_score=50.0,
            composite_score=50.0,
            regime="moderate",
            date=datetime.now().strftime("%Y-%m-%d"),
        )

    prices = close

    # Component 1: SMA-200 deviation (0-40 pts)
    dev = _sma200_deviation(prices)
    dev_score = np.clip(dev / 30 * 40, 0, 40)

    # Component 2: Trend acceleration (0-30 pts)
    accel = _trend_acceleration(prices)
    accel_score = np.clip(accel / 5 * 30, 0, 30)

    # Component 3: Volatility regime (0-30 pts)
    vol = _volatility_regime(prices)
    vol_score = np.clip((vol - 0.20) / 0.50 * 30, 0, 30)

    composite = float(dev_score + accel_score + vol_score)
    composite = np.clip(composite, 0, 100)
    drawdown_risk = composite

    if drawdown_risk >= 66:
        regime = "high_risk"
    elif drawdown_risk >= 55:
        regime = "elevated"
    elif drawdown_risk >= 40:
        regime = "moderate"
    else:
        regime = "low_risk"

    return BubbleRiskResult(
        drawdown_risk_score=round(drawdown_risk, 1),
        composite_score=round(composite, 1),
        regime=regime,
        date=datetime.now().strftime("%Y-%m-%d"),
        components={
            "sma200_deviation": round(float(dev_score), 1),
            "trend_acceleration": round(float(accel_score), 1),
            "volatility_regime": round(float(vol_score), 1),
        },
    )


def fetch_bubble_risk(
    url: str = _DEFAULT_BUBBLE_HISTORY_URL,
) -> BubbleRiskResult:
    """Fetch the latest bubble risk score from the Dashboard API.

    Returns the full model output (GSADF + Markov + deviation +
    regime detection) computed by the Dashboard's daily pipeline.
    """
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        logger.warning("Failed to fetch from Dashboard API — falling back to live calc")
        return calculate_bubble_risk()

    history = data.get("history", [])
    if not history:
        return calculate_bubble_risk()

    latest = history[-1]
    risk = latest.get("drawdown_risk_score", 50.0)
    composite = latest.get("composite_score", 50.0)
    date = latest.get("date", datetime.now().strftime("%Y-%m-%d"))

    if risk >= 66:
        regime = "high_risk"
    elif risk >= 55:
        regime = "elevated"
    elif risk >= 40:
        regime = "moderate"
    else:
        regime = "low_risk"

    return BubbleRiskResult(
        drawdown_risk_score=risk,
        composite_score=composite,
        regime=regime,
        date=date,
        components=latest.get("components", {}),
    )
