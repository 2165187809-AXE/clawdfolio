# Clawdfolio 🦙📊

[![CI](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YichengYang-Ethan/clawdfolio/branch/main/graph/badge.svg)](https://codecov.io/gh/YichengYang-Ethan/clawdfolio)
[![PyPI](https://img.shields.io/pypi/v/clawdfolio.svg)](https://pypi.org/project/clawdfolio/)
[![Downloads](https://static.pepy.tech/badge/clawdfolio/month)](https://pepy.tech/project/clawdfolio)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
English | [中文](README_CN.md)

> **Production-grade quantitative portfolio toolkit** — multi-broker aggregation, institutional risk analytics, options lifecycle management, and 20+ automated finance workflows.

---

## Why Clawdfolio?

| Traditional Tools | Clawdfolio |
|-------------------|------------|
| Manual data entry | Auto-sync from Longport, Moomoo/Futu |
| Basic P&L tracking | VaR, Sharpe, Beta, Max Drawdown, HHI |
| Single broker view | Multi-broker aggregation |
| Spreadsheet alerts | Smart RSI / price / P&L alerts |
| No extensibility | Python API + CLI |

---

## Features

- **Multi-Broker Support** — Longport (Longbridge), Moomoo/Futu, or demo mode
- **Risk Analytics** — Volatility, Beta, Sharpe Ratio, Value at Risk, Max Drawdown, GARCH forecasting
- **Bubble Risk Score** — Real-time market bubble detection powered by [Market-Bubble-Index-Dashboard](https://github.com/YichengYang-Ethan/Market-Bubble-Index-Dashboard), with SMA deviation, trend acceleration, and volatility regime analysis
- **Risk-Driven Covered Call Strategy** — Backtested over 11 years (2014-2026): sell CC only when Risk Score >= 66, achieving **83% win rate** and **+3.0% annualized alpha** over buy-and-hold
- **Technical Analysis** — RSI, SMA, EMA, Bollinger Bands
- **Concentration Analysis** — HHI index, sector exposure, correlation warnings
- **Stress Testing** — 5 historical scenarios (COVID crash, 2022 bear market, etc.) with leveraged ETF awareness
- **Smart Alerts** — Price movements, RSI extremes, P&L thresholds
- **Earnings Calendar** — Track upcoming earnings for holdings
- **Options Toolkit** — Option quote/Greeks, option chain snapshot, buyback trigger monitor
- **Options Strategy Playbook (v2.1)** — Covered Call and Sell Put lifecycle management with delta/gamma/margin guardrails
- **Finance Workflow Suite** — 20 production workflows for reports, alerts, market intel, and broker snapshots

---

## Quick Start

### Installation

```bash
pip install clawdfolio                  # Core
pip install clawdfolio[longport]        # + Longport broker
pip install clawdfolio[futu]            # + Moomoo/Futu broker
pip install clawdfolio[all]             # All brokers
```

### CLI Usage

```bash
clawdfolio summary                     # Portfolio overview
clawdfolio risk                        # Risk metrics (VaR, Sharpe, Beta, etc.)
clawdfolio quotes AAPL TSLA NVDA       # Real-time quotes
clawdfolio alerts                      # Check alerts
clawdfolio earnings                    # Upcoming earnings calendar
clawdfolio dca AAPL                    # DCA analysis
```

<details>
<summary><strong>Example Output: <code>clawdfolio summary</code></strong></summary>

```
╔══════════════════════════════════════════════════════════╗
║                  Portfolio Summary                       ║
╠══════════════════════════════════════════════════════════╣
║  Net Assets:     $41,863.57    Day Change:   +$327.42   ║
║  Total P&L:      +$6,847.23   Return:       +19.55%    ║
║  Positions:      15            Brokers:      2          ║
╠══════════════════════════════════════════════════════════╣
║  Top Holdings                                            ║
║  TQQQ     $11,058.00   26.4%   +32.1%                  ║
║  NVDA      $5,280.00   12.6%   +45.2%                  ║
║  AAPL      $4,125.00    9.9%   +12.8%                  ║
║  MSFT      $3,840.00    9.2%   +15.6%                  ║
║  QQQ       $3,520.00    8.4%   +22.3%                  ║
╚══════════════════════════════════════════════════════════╝
```

</details>

### Options Commands

```bash
clawdfolio options expiries TQQQ
clawdfolio options quote TQQQ --expiry 2026-06-18 --strike 60 --type C
clawdfolio options chain TQQQ --expiry 2026-06-18 --side both --limit 10
clawdfolio options buyback             # Trigger check from config
```

### Python API

```python
from clawdfolio.brokers import get_broker
from clawdfolio.analysis import analyze_risk

broker = get_broker("demo")  # or "longport", "futu"
broker.connect()

portfolio = broker.get_portfolio()
metrics = analyze_risk(portfolio)

print(f"Net Assets: ${portfolio.net_assets:,.2f}")
print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
print(f"VaR 95%: ${metrics.var_95:,.2f}")
```

---

## Risk Metrics

| Metric | Description |
|--------|-------------|
| **Volatility** | 20-day and 60-day annualized, GARCH(1,1) forecast |
| **Beta** | Correlation with SPY/QQQ |
| **Sharpe Ratio** | Risk-adjusted returns |
| **Sortino Ratio** | Downside-only risk-adjusted returns |
| **VaR / CVaR** | Value at Risk (95%/99%) + Expected Shortfall |
| **Max Drawdown** | Largest peak-to-trough decline |
| **HHI** | Portfolio concentration index |
| **Stress Testing** | COVID-19, 2022 bear, flash crash scenarios |

---

## Bubble Risk Score

Integrated from [Market-Bubble-Index-Dashboard](https://github.com/YichengYang-Ethan/Market-Bubble-Index-Dashboard) — a real-time composite market risk indicator.

**Components:**
- **SMA-200 Deviation** (0-40 pts) — How far the market has stretched above its 200-day moving average
- **Trend Acceleration** (0-30 pts) — Polynomial-fit measure of parabolic price acceleration
- **Volatility Regime** (0-30 pts) — Annualized realized volatility assessment

**Regime Classification:**

| Score | Regime | Action |
|-------|--------|--------|
| 0-39 | Low Risk | Hold shares, no CC |
| 40-54 | Moderate | Monitor |
| 55-65 | Elevated | Prepare CC orders |
| 66-100 | High Risk | Sell covered calls |

```python
from clawdfolio.analysis.bubble import fetch_bubble_risk

risk = fetch_bubble_risk()  # from Dashboard API (with live-calc fallback)
print(f"Risk Score: {risk.drawdown_risk_score:.1f} ({risk.regime})")
print(f"Should sell CC: {risk.should_sell_cc}")
print(f"Recommended delta: {risk.cc_delta}")
```

---

## Risk-Driven Covered Call Strategy

A quantitative covered call strategy that uses the Bubble Risk Score to determine **when** to sell calls and at **what delta**. Designed for long-term holders of leveraged ETFs (TQQQ) or broad-market ETFs (QQQ/SPY).

**Backtested Results (2014-2026, 64 parameter combinations):**

| Metric | Value |
|--------|-------|
| Optimal threshold | Risk Score >= 66 (P85 historical) |
| Optimal delta | 0.25 |
| Win rate | **83%** |
| Annualized alpha | **+3.0%** over buy-and-hold |
| Assignment rate | 1.5% (1 in 11 years) |
| Signal type | Asymmetric — sell-call only |

```python
from clawdfolio.strategies.covered_call import CoveredCallStrategy

strategy = CoveredCallStrategy(tickers=["TQQQ"])
signals = strategy.check_signals()

for sig in signals:
    print(f"{sig.ticker}: {sig.action.value} δ={sig.target_delta} "
          f"Risk={sig.bubble_risk_score:.0f} ({sig.regime})")

# Or get a quick one-liner:
from clawdfolio.strategies.covered_call import get_cc_recommendation
print(get_cc_recommendation("TQQQ"))
```

<details>
<summary><strong>Example Signal Dashboard Output</strong></summary>

```
━━━ Covered Call Signal Dashboard ━━━

  TQQQ
    Risk Score: 72.5 (high_risk)
    Action:     sell_call
    🔶 Risk signal active (72 ≥ 66) — sell CC at δ=0.25
    Target:     δ=0.25, DTE=35
    Mgmt:       PT=50%, SL=200%, Roll@14DTE
    Strength:   33%
```

</details>

---

## Options Toolkit

The built-in options module provides real-time Greeks inspection, chain analysis, and stateful buyback monitoring:

| Command | Description |
|---------|-------------|
| `options expiries` | List available expiry dates for a symbol |
| `options quote` | Single option quote with Greeks (delta, gamma, theta, vega, IV) |
| `options chain` | Full option chain snapshot with filtering |
| `options buyback` | Stateful trigger monitor for short option buyback |

Strategy methodology is documented in the [Options Strategy Playbook](docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md) — covering Covered Call and Sell Put lifecycle management with delta-based strike selection, roll/assignment rules, and margin guardrails.

---

## Configuration

### Environment Variables

```bash
# Longport
export LONGPORT_APP_KEY=your_app_key
export LONGPORT_APP_SECRET=your_app_secret
export LONGPORT_ACCESS_TOKEN=your_access_token

# Moomoo: Run OpenD locally on port 11111
```

### Config File (optional)

Create `config.yaml`:

```yaml
brokers:
  longport:
    enabled: true
  futu:
    enabled: true
    extra:
      host: "127.0.0.1"
      port: 11111

alerts:
  pnl_trigger: 500.0
  rsi_high: 80
  rsi_low: 20

option_buyback:
  enabled: true
  symbol: "TQQQ"
  targets:
    - name: "cc-june"
      strike: 60
      expiry: "2026-06-18"
      type: "C"
      trigger_price: 1.60
      qty: 2
      reset_pct: 0.20
```

### Supported Brokers

| Broker | Region | Status |
|--------|--------|--------|
| Demo | Global | Built-in |
| Longport | US/HK/SG | Optional |
| Moomoo/Futu | US/HK/SG | Optional |

---

## Finance Workflows

20 production workflows migrated from live trading infrastructure, organized by category:

| Category | Examples |
|----------|---------|
| **Portfolio Reports** | Account report, portfolio analysis, risk breakdown |
| **Briefing Cards** | Daily brief (console + Telegram), multi-format |
| **Alerts & Monitors** | Price/RSI alerts, option buyback trigger |
| **Market Intelligence** | Real-time quotes, earnings calendar, market news |
| **Broker Snapshots** | Longport / Moomoo asset summaries |
| **Strategy** | DCA proposals |

```bash
clawdfolio finance list                # Browse all workflows by category
clawdfolio finance init                # Bootstrap ~/.clawdfolio/finance workspace
clawdfolio finance run <workflow_id>   # Execute a workflow
```

---

<details>
<summary><strong>Changelog</strong></summary>

### v2.4.0 (2026-02-28)

- **Bubble Risk Score** — Real-time drawdown risk scoring (0-100) integrated from Market-Bubble-Index-Dashboard
- **Risk-driven Covered Call strategy** — Quantitative CC signals: 83% win rate, +3.0% alpha (11-year backtest)
- `CoveredCallStrategy`, `check_cc_signals()`, `get_cc_recommendation()` convenience API
- `fetch_bubble_risk()` with Dashboard API + live-calc fallback
- Comprehensive test coverage for bubble risk and covered call modules

### v2.3.0 (2026-02-16)

- Sortino ratio and CVaR/Expected Shortfall risk metrics
- Portfolio RSI in `analyze_risk()` output
- `clawdfolio export` CLI command (CSV/JSON)
- Dynamic US trading calendar with algorithmic holiday generation
- Batched SPY/QQQ benchmark fetching via `get_history_multi()`
- O(1) position lookup via `_ticker_index`
- `calculate_ema()` vectorized with `pd.Series.ewm()`
- Fixed invalid yfinance period strings in DCA calculation
- Coverage enforcement at 48%, Python 3.13 in CI, `pip-audit` scanning

### v2.2.0 (2026-02-14)

- Thread-safe market data caching (`threading.Lock`)
- Batch quote fetching via `yf.download` with per-ticker fallback
- Shared `suppress_stdio` utility (DRY refactor)
- Dynamic CLI version from `__version__`
- PEP 561 compliance (`py.typed` marker)
- Structured logging across core modules
- Centralized ticker normalization (`_yf_symbol()`)
- Config path migration to `clawdfolio` namespace (backward-compatible)

### v2.1.0 (2026-01-28)

- Options Strategy Playbook v2.1 (`docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md`)
- Research-to-execution framework for CC and Sell Put lifecycle
- Explicit gamma-risk, margin, leverage, and assignment decision rules

### v2.0.0 (2026-01-15)

- Full finance migration: 20 production workflows from live trading infrastructure
- `clawdfolio finance` command group (list, init, run)
- Mutable workspace bootstrap (`~/.clawdfolio/finance`)
- Options quote/chain/buyback monitor
- Wilder RSI smoothing, Longport symbol fix, yfinance hardening

See [CHANGELOG.md](CHANGELOG.md) for full details.

</details>

---

## Contributing

Contributions welcome! Please submit a Pull Request.

## License

MIT License — see [LICENSE](LICENSE)

## Links

- [GitHub Repository](https://github.com/YichengYang-Ethan/clawdfolio)
- [Report Issues](https://github.com/YichengYang-Ethan/clawdfolio/issues)
- [Options Strategy Playbook](docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md)
