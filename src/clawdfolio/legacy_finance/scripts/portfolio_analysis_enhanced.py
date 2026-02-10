#!/usr/bin/env python3
"""Enhanced Portfolio Analysis - 深度风险分析工具

提供比 portfolio_daily_brief.py 更详细的风险指标：
- 波动率 (Volatility)
- 夏普比率 (Sharpe Ratio) — 无风险利率从 ^TNX 动态获取
- 最大回撤 (Max Drawdown)
- 贝塔值 (Beta vs SPY)
- VaR (Value at Risk, 95%)
- 相关性矩阵
- 行业分布详情
- 技术指标 (RSI, 均线)
- HHI 集中度 (0-10000 标准量纲)

数据源: yfinance (历史数据), 长桥/moomoo (持仓, via lib/brokers)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.brokers import fetch_holdings
from lib.fmt import fmt_money, fmt_pct
from lib.market import (
    get_history_multi, get_sector_and_industry, risk_free_rate,
)


@dataclass
class HoldingAnalysis:
    ticker: str
    name: str = ""
    qty: float = 0.0
    mv: float = 0.0
    weight: float = 0.0
    avg_cost: Optional[float] = None
    current_price: Optional[float] = None
    volatility: Optional[float] = None
    beta: Optional[float] = None
    rsi_14: Optional[float] = None
    ma_50: Optional[float] = None
    ma_200: Optional[float] = None
    above_ma_50: Optional[bool] = None
    above_ma_200: Optional[bool] = None
    sector: str = ""
    industry: str = ""


@dataclass
class PortfolioRisk:
    total_net: float = 0.0
    total_mv: float = 0.0
    portfolio_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    portfolio_beta: Optional[float] = None
    var_95: Optional[float] = None
    var_95_pct: Optional[float] = None
    top5_weight: float = 0.0
    hhi: float = 0.0  # 0-10000 scale
    sector_weights: Dict[str, float] = field(default_factory=dict)
    high_corr_pairs: List[Tuple[str, str, float]] = field(default_factory=list)
    holdings: List[HoldingAnalysis] = field(default_factory=list)


def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna()


def calculate_volatility(returns: pd.Series) -> float:
    return float(returns.std() * np.sqrt(252))


def calculate_sharpe(returns: pd.Series, rf: float) -> float:
    excess = returns.mean() * 252 - rf
    vol = returns.std() * np.sqrt(252)
    return float(excess / vol) if vol > 0 else 0.0


def calculate_max_drawdown(prices: pd.Series) -> float:
    peak = prices.expanding().max()
    dd = (prices - peak) / peak
    return float(dd.min())


def calculate_beta(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    cov = stock_returns.cov(market_returns)
    var = market_returns.var()
    return float(cov / var) if var > 0 else 1.0


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / period, min_periods=period).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / period, min_periods=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def calculate_var_95(returns: pd.Series, portfolio_value: float) -> Tuple[float, float]:
    mean = returns.mean()
    std = returns.std()
    var_pct = mean - 1.645 * std
    var_dollar = portfolio_value * abs(var_pct)
    return float(var_dollar), float(abs(var_pct))


def calculate_hhi(weights: List[float]) -> float:
    """HHI on 0-10000 scale (standard)."""
    return sum((w * 100) ** 2 for w in weights)


def find_high_correlations(returns: pd.DataFrame, threshold: float = 0.7) -> List[Tuple[str, str, float]]:
    if returns.empty or len(returns.columns) < 2:
        return []
    corr = returns.corr()
    pairs = []
    cols = list(corr.columns)
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            val = corr.loc[c1, c2]
            if abs(val) > threshold:
                pairs.append((c1, c2, float(val)))
    pairs.sort(key=lambda x: -abs(x[2]))
    return pairs[:5]


def analyze_portfolio() -> PortfolioRisk:
    result = PortfolioRisk()

    # 1. Get holdings via shared lib
    raw_holdings = fetch_holdings()
    if not raw_holdings:
        return result

    # Broker-first quote enrichment (fill missing price/prev_close if any)
    try:
        from lib.market_data import fetch_best_quotes

        tickers = list(raw_holdings.keys())
        qmap = fetch_best_quotes(tickers)
        for t, h in raw_holdings.items():
            q = qmap.get(t)
            if not q:
                continue
            if (h.price is None or h.price == 0) and q.get("price") is not None:
                h.price = float(q["price"])
            if h.prev_close is None and q.get("prev_close") is not None:
                h.prev_close = float(q["prev_close"])
            if (h.mv is None or h.mv == 0) and h.price is not None:
                h.mv = h.qty * float(h.price)
    except Exception:
        pass

    total_mv = sum(h.mv for h in raw_holdings.values())
    result.total_mv = total_mv
    result.total_net = total_mv

    # 2. Build holdings list with weights
    tickers = list(raw_holdings.keys())
    for t, data in raw_holdings.items():
        h = HoldingAnalysis(
            ticker=t,
            name=data.name,
            qty=data.qty,
            mv=data.mv,
            weight=data.mv / total_mv if total_mv > 0 else 0,
            avg_cost=data.avg_cost,
            current_price=data.price,
        )
        result.holdings.append(h)

    result.holdings.sort(key=lambda x: x.mv, reverse=True)

    # 3. Concentration metrics
    weights = [h.weight for h in result.holdings]
    result.top5_weight = sum(weights[:5])
    result.hhi = calculate_hhi(weights)

    # 4. Fetch historical data (including SPY for beta)
    all_tickers = tickers + ["SPY"]
    prices = get_history_multi(all_tickers, period="1y")
    if prices.empty:
        return result

    returns = calculate_returns(prices)
    spy_col = "SPY" if "SPY" in returns.columns else None

    # 5. Individual stock metrics
    for idx, h in enumerate(result.holdings):
        t_col = h.ticker.replace(".", "-")
        if t_col not in returns.columns:
            continue

        stock_ret = returns[t_col].dropna()
        if len(stock_ret) < 20:
            continue

        h.volatility = calculate_volatility(stock_ret)
        if spy_col and spy_col in returns.columns:
            h.beta = calculate_beta(stock_ret, returns[spy_col])

        if t_col in prices.columns:
            stock_prices = prices[t_col].dropna()
            h.rsi_14 = calculate_rsi(stock_prices)
            if len(stock_prices) >= 50:
                h.ma_50 = float(stock_prices.rolling(50).mean().iloc[-1])
                h.above_ma_50 = float(stock_prices.iloc[-1]) > h.ma_50
            if len(stock_prices) >= 200:
                h.ma_200 = float(stock_prices.rolling(200).mean().iloc[-1])
                h.above_ma_200 = float(stock_prices.iloc[-1]) > h.ma_200

        # Sector info (top 10 only to avoid rate limits)
        if idx < 10:
            h.sector, h.industry = get_sector_and_industry(h.ticker)

    # 6. Portfolio-level metrics
    rf = risk_free_rate()

    portfolio_ret = pd.Series(0.0, index=returns.index)
    for h in result.holdings:
        t_col = h.ticker.replace(".", "-")
        if t_col in returns.columns:
            portfolio_ret += returns[t_col].fillna(0) * h.weight

    if len(portfolio_ret.dropna()) > 20:
        result.portfolio_volatility = calculate_volatility(portfolio_ret)
        result.sharpe_ratio = calculate_sharpe(portfolio_ret, rf)

        cum_ret = (1 + portfolio_ret).cumprod()
        result.max_drawdown = calculate_max_drawdown(cum_ret)

        if spy_col and spy_col in returns.columns:
            result.portfolio_beta = calculate_beta(portfolio_ret, returns[spy_col])

        result.var_95, result.var_95_pct = calculate_var_95(portfolio_ret, total_mv)

    # 7. Correlation analysis
    stock_cols = [h.ticker.replace(".", "-") for h in result.holdings if h.ticker.replace(".", "-") in returns.columns]
    if len(stock_cols) >= 2:
        result.high_corr_pairs = find_high_correlations(returns[stock_cols])

    # 8. Sector weights
    for h in result.holdings:
        if h.sector:
            result.sector_weights[h.sector] = result.sector_weights.get(h.sector, 0) + h.weight

    return result


def format_output(r: PortfolioRisk) -> str:
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"📈 投资组合深度分析 ({now})")
    lines.append("")

    # Risk metrics
    rf = risk_free_rate()
    lines.append("━━━ 风险指标 ━━━")
    if r.portfolio_volatility is not None:
        vol_level = "低" if r.portfolio_volatility < 0.15 else ("中" if r.portfolio_volatility < 0.25 else "高")
        lines.append(f"组合波动率: {r.portfolio_volatility * 100:.1f}% ({vol_level})")
    if r.sharpe_ratio is not None:
        sr_level = "差" if r.sharpe_ratio < 0 else ("一般" if r.sharpe_ratio < 1 else ("良好" if r.sharpe_ratio < 2 else "优秀"))
        lines.append(f"夏普比率: {r.sharpe_ratio:.2f} ({sr_level}, rf={rf * 100:.1f}%)")
    if r.max_drawdown is not None:
        lines.append(f"最大回撤: {r.max_drawdown * 100:.1f}%")
    if r.portfolio_beta is not None:
        beta_level = "防守" if r.portfolio_beta < 1 else ("中性" if r.portfolio_beta < 1.2 else "激进")
        lines.append(f"组合Beta: {r.portfolio_beta:.2f} ({beta_level})")
    if r.var_95 is not None:
        lines.append(f"日VaR(95%): {fmt_money(r.var_95)} ({r.var_95_pct * 100:.1f}%)")

    lines.append("")

    # Concentration (HHI on 0-10000 scale)
    lines.append("━━━ 集中度分析 ━━━")
    lines.append(f"Top5 占比: {r.top5_weight * 100:.1f}%")
    if r.holdings:
        lines.append(f"最大单股: {r.holdings[0].ticker} ({r.holdings[0].weight * 100:.1f}%)")
    hhi_level = "分散" if r.hhi < 1000 else ("适中" if r.hhi < 1800 else "集中")
    lines.append(f"HHI指数: {r.hhi:.0f} ({hhi_level})")

    lines.append("")

    # Sector breakdown
    if r.sector_weights:
        lines.append("━━━ 行业分布 ━━━")
        sorted_sectors = sorted(r.sector_weights.items(), key=lambda x: -x[1])
        for sec, w in sorted_sectors[:5]:
            bar = "█" * int(w * 20)
            lines.append(f"{sec[:12]:12} {bar} {w * 100:.1f}%")

    lines.append("")

    # Correlation warnings
    if r.high_corr_pairs:
        lines.append("━━━ 高相关性警告 ━━━")
        for t1, t2, corr in r.high_corr_pairs[:3]:
            lines.append(f"⚠️ {t1} ↔ {t2}: {corr:.2f}")

    lines.append("")

    # Top holdings with metrics
    lines.append("━━━ 重仓股分析 ━━━")
    for idx, h in enumerate(r.holdings[:8]):
        parts = [f"{h.ticker:6}"]
        parts.append(f"{h.weight * 100:5.1f}%")
        if h.volatility is not None:
            parts.append(f"波动{h.volatility * 100:.0f}%")
        if h.beta is not None:
            parts.append(f"β{h.beta:.1f}")
        if h.rsi_14 is not None:
            rsi_signal = "超买" if h.rsi_14 > 70 else ("超卖" if h.rsi_14 < 30 else "")
            rsi_text = f"RSI{h.rsi_14:.0f}"
            if rsi_signal:
                rsi_text += f"({rsi_signal})"
            # Always show RSI for Top5 so Wilder EMA results are directly verifiable.
            if idx < 5 or rsi_signal:
                parts.append(rsi_text)
        signals = []
        if h.above_ma_50 is not None:
            signals.append("↑MA50" if h.above_ma_50 else "↓MA50")
        if h.above_ma_200 is not None:
            signals.append("↑MA200" if h.above_ma_200 else "↓MA200")
        if signals:
            parts.append(" ".join(signals))

        lines.append(" | ".join(parts))

    lines.append("")

    # Risk summary
    lines.append("━━━ 风险总结 ━━━")
    risks = []
    if r.holdings and r.holdings[0].weight > 0.15:
        risks.append(f"⚠️ 单股集中: {r.holdings[0].ticker} 占比过高")
    if r.sector_weights:
        top_sec = max(r.sector_weights.items(), key=lambda x: x[1])
        if top_sec[1] > 0.35:
            risks.append(f"⚠️ 行业集中: {top_sec[0]} {top_sec[1] * 100:.0f}%")
    if r.portfolio_volatility and r.portfolio_volatility > 0.30:
        risks.append("⚠️ 高波动组合，注意风控")
    if r.max_drawdown and r.max_drawdown < -0.20:
        risks.append(f"⚠️ 历史最大回撤 {r.max_drawdown * 100:.0f}%")
    for h in r.holdings[:5]:
        if h.rsi_14 and h.rsi_14 > 75:
            risks.append(f"⚠️ {h.ticker} RSI超买({h.rsi_14:.0f})")
        if h.rsi_14 and h.rsi_14 < 25:
            risks.append(f"💡 {h.ticker} RSI超卖({h.rsi_14:.0f})")

    if risks:
        lines.extend(risks[:5])
    else:
        lines.append("✓ 无显著风险提示")

    return "\n".join(lines)


def main():
    result = analyze_portfolio()
    print(format_output(result))


if __name__ == "__main__":
    main()
