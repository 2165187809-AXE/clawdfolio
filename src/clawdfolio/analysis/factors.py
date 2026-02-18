"""Fama-French factor exposure analysis."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FF3_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"


@dataclass
class FactorExposure:
    """Factor regression results."""

    factor_loadings: dict[str, float] = field(default_factory=dict)
    t_stats: dict[str, float] = field(default_factory=dict)
    p_values: dict[str, float] = field(default_factory=dict)
    r_squared: float = 0.0
    alpha_annualized: float = 0.0
    alpha_t_stat: float = 0.0
    alpha_p_value: float = 0.0


def download_ff_factors(period: str = "1y") -> pd.DataFrame:
    """Download Fama-French 3-factor daily data.

    Args:
        period: Lookback period (e.g., "1y", "3y", "5y")

    Returns:
        DataFrame with columns: Mkt-RF, SMB, HML, RF (all in decimal form)
    """
    import urllib.request

    response = urllib.request.urlopen(FF3_URL, timeout=30)  # noqa: S310
    zip_data = response.read()

    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        csv_name = [n for n in zf.namelist() if n.endswith(".CSV") or n.endswith(".csv")][0]
        raw = zf.read(csv_name).decode("utf-8")

    # Parse the CSV: find the daily data section
    lines = raw.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and stripped[0].isdigit() and len(stripped.split(",")[0].strip()) == 8:
            start_idx = i
            break

    if start_idx is None:
        raise ValueError("Could not find daily data in Fama-French CSV")

    # Read until we hit a blank line or non-numeric row
    data_lines = []
    for line in lines[start_idx:]:
        stripped = line.strip()
        if not stripped or not stripped[0].isdigit():
            break
        data_lines.append(stripped)

    df = pd.read_csv(
        io.StringIO("\n".join(data_lines)),
        header=None,
        names=["date", "Mkt-RF", "SMB", "HML", "RF"],
    )
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df = df.set_index("date").sort_index()

    # Convert from percentage to decimal
    for col in ["Mkt-RF", "SMB", "HML", "RF"]:
        df[col] = df[col].astype(float) / 100.0

    # Filter by period
    period_map = {"1y": 252, "2y": 504, "3y": 756, "5y": 1260}
    n_days = period_map.get(period, 252)
    df = df.iloc[-n_days:]

    return df


def analyze_factor_exposure(
    portfolio_returns: pd.Series,
    period: str = "1y",
) -> FactorExposure:
    """Run Fama-French 3-factor regression on portfolio returns.

    Args:
        portfolio_returns: Daily portfolio return series (decimal form)
        period: Lookback period for factor data

    Returns:
        FactorExposure with loadings, t-stats, p-values, R-squared, alpha
    """
    from numpy.linalg import lstsq

    factors = download_ff_factors(period=period)

    # Align dates
    port = portfolio_returns.copy()
    port.index = pd.to_datetime(port.index)
    combined = pd.DataFrame({"port": port}).join(factors, how="inner").dropna()

    if len(combined) < 30:
        return FactorExposure()

    y = combined["port"].values - combined["RF"].values  # Excess returns
    X = combined[["Mkt-RF", "SMB", "HML"]].values
    X_with_const = np.column_stack([np.ones(len(X)), X])

    # OLS via least squares
    coeffs, residuals, rank, sv = lstsq(X_with_const, y, rcond=None)

    alpha = coeffs[0]
    betas = coeffs[1:]
    factor_names = ["Mkt-RF", "SMB", "HML"]

    # Compute statistics
    y_hat = X_with_const @ coeffs
    resid = y - y_hat
    n = len(y)
    k = X_with_const.shape[1]

    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Standard errors
    mse = ss_res / (n - k) if n > k else 1e-10
    try:
        cov_matrix = mse * np.linalg.inv(X_with_const.T @ X_with_const)
        se = np.sqrt(np.diag(cov_matrix))
    except np.linalg.LinAlgError:
        se = np.ones(k) * 1e-10

    t_values = coeffs / se

    # p-values from t-distribution
    from scipy import stats as sp_stats

    df = n - k
    p_vals = [float(2 * (1 - sp_stats.t.cdf(abs(t), df))) for t in t_values]

    result = FactorExposure(
        factor_loadings={name: float(b) for name, b in zip(factor_names, betas, strict=False)},
        t_stats={name: float(t) for name, t in zip(factor_names, t_values[1:], strict=False)},
        p_values={name: float(p) for name, p in zip(factor_names, p_vals[1:], strict=False)},
        r_squared=r_squared,
        alpha_annualized=float(alpha * 252),
        alpha_t_stat=float(t_values[0]),
        alpha_p_value=float(p_vals[0]),
    )

    return result
