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

---

## What's New in v1.0.2

- **Finance reliability sync** - Ported proven reliability improvements from real production workflows
- **More realistic RSI** - RSI now uses **Wilder EMA smoothing** for steadier signal quality
- **Longport quote refresh fix** - Corrected symbol wiring in `LongportBroker.get_positions()`
- **Market data hardening** - Better yfinance history normalization (single ticker + MultiIndex) and `prev_close` fallback
- **CI stability** - Full lint/type/test pipeline now passes consistently on Python 3.10/3.11/3.12

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
```

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
