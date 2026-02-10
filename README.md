# Clawdfolio 🦙📊

[![CI](https://github.com/2165187809-AXE/clawdfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/2165187809-AXE/clawdfolio/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://github.com/anthropics/claude-code)

English | [中文](README_CN.md)

> **AI-powered portfolio monitoring for the Claude Code ecosystem.**
>
> The ultimate Claude Code Skill for investors - aggregates portfolios from multiple brokers, calculates institutional-grade risk metrics, and generates intelligent trading alerts with production-grade data reliability.

---

## Why Clawdfolio?

| Traditional Tools | Clawdfolio |
|-------------------|------------|
| Manual data entry | Auto-sync from brokers |
| Basic P&L tracking | VaR, Sharpe, Beta, Max Drawdown |
| Single broker view | Multi-broker aggregation |
| Spreadsheet alerts | Smart RSI/price alerts |
| No AI integration | **Claude Code native skill** |

---

## Features

- **Multi-Broker Support** - Longport (Longbridge), Moomoo/Futu, or demo mode
- **Risk Analytics** - Volatility, Beta, Sharpe Ratio, Value at Risk, Max Drawdown
- **Technical Analysis** - RSI, SMA, EMA, Bollinger Bands
- **Concentration Analysis** - HHI index, sector exposure, correlation warnings
- **Smart Alerts** - Price movements, RSI extremes, P&L thresholds
- **Earnings Calendar** - Track upcoming earnings for holdings
- **DCA Analysis** - Dollar-cost averaging signals
- **Options Toolkit** - Option quote/Greeks, option chain snapshot, buyback trigger monitor
- **Finance Workflow Suite (v2)** - 20 migrated production workflows from local `~/clawd/scripts`, categorized and runnable via `clawdfolio finance`

---

## What's New in v2.0.0

- **Full finance migration** - Migrated all active local finance workflows (reports, briefs, alerts, market intel, snapshots, DCA, security) from `~/clawd/scripts`
- **Structured orchestration** - Added `clawdfolio finance` command group to list, initialize, and run workflows by id
- **Organized layout** - Added categorized workflow catalog and bundled `legacy_finance` package content, with archived historical scripts retained
- **Runtime safety** - Introduced mutable workspace bootstrap (`~/.clawdfolio/finance`) so legacy workflows keep writable config/state without polluting repo root
- **Prior reliability gains retained** - Wilder RSI smoothing, Longport symbol fix, yfinance hardening, options quote/chain/buyback monitor remain included

---

## Quick Start

### As Claude Code Skill

Simply ask Claude Code:

```
/clawdfolio summary
/clawdfolio risk
/clawdfolio quotes AAPL MSFT NVDA
/clawdfolio alerts
```

### CLI Installation

```bash
# Basic
pip install clawdfolio

# With broker support
pip install clawdfolio[longport]  # Longport
pip install clawdfolio[futu]      # Moomoo/Futu
pip install clawdfolio[all]       # All brokers
```

### CLI Usage

```bash
clawdfolio summary              # Portfolio overview
clawdfolio risk                 # Risk metrics
clawdfolio quotes AAPL TSLA     # Real-time quotes
clawdfolio alerts               # Check alerts
clawdfolio earnings             # Upcoming earnings
clawdfolio dca AAPL             # DCA analysis
clawdfolio options expiries TQQQ
clawdfolio options quote TQQQ --expiry 2026-06-18 --strike 60 --type C
clawdfolio options chain TQQQ --expiry 2026-06-18 --side both --limit 10
clawdfolio options buyback      # Trigger check from config option_buyback.targets
clawdfolio finance list         # List all migrated finance workflows
clawdfolio finance init         # Bootstrap ~/.clawdfolio/finance workspace
clawdfolio finance run portfolio_daily_brief_tg_clean
```

### Finance Workflows (v2)

`clawdfolio finance list` groups workflows by:
- Portfolio Reports
- Briefing Cards
- Alerts and Monitors
- Market Intelligence
- Broker Snapshots
- Strategy
- Security

---

## Python API

```python
from clawdfolio.brokers import get_broker
from clawdfolio.analysis import analyze_risk

# Connect to broker
broker = get_broker("demo")  # or "longport", "futu"
broker.connect()

# Get portfolio and analyze
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
| **Volatility** | 20-day and 60-day annualized |
| **Beta** | Correlation with SPY/QQQ |
| **Sharpe Ratio** | Risk-adjusted returns |
| **VaR** | Value at Risk (95%/99%) |
| **Max Drawdown** | Largest peak-to-trough decline |
| **HHI** | Portfolio concentration index |

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
  state_path: "~/.cache/clawdfolio/option_buyback_state.json"
  targets:
    - name: "target1"
      strike: 60
      expiry: "2026-06-18"
      type: "C"
      trigger_price: 1.60
      qty: 2
      reset_pct: 0.20
    - name: "target2"
      strike: 60
      expiry: "2026-06-18"
      type: "C"
      trigger_price: 0.80
      qty: 1
      reset_pct: 0.20
```

---

## Supported Brokers

| Broker | Region | Status |
|--------|--------|--------|
| Demo | Global | Built-in |
| Longport | US/HK/SG | Optional |
| Moomoo/Futu | US/HK/SG | Optional |

---

## Contributing

Contributions welcome! Please submit a Pull Request.

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Links

- [GitHub Repository](https://github.com/2165187809-AXE/clawdfolio)
- [Report Issues](https://github.com/2165187809-AXE/clawdfolio/issues)
- [Claude Code](https://github.com/anthropics/claude-code)

---

**If Clawdfolio helps you, please give it a ⭐ star!**
