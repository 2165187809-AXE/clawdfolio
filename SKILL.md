---
name: clawdfolio
version: 2.0.0
description: AI-powered portfolio monitoring for Clawdbot - Multi-broker support with professional risk analytics and finance workflows
author: YICHENG YANG
license: MIT
keywords:
  - clawdbot
  - claude-code-compatible
  - ai
  - finance
  - portfolio
  - trading
  - risk-analysis
  - investment
dependencies:
  - pandas>=2.0.0
  - numpy>=1.24.0
  - yfinance>=0.2.30
  - pyyaml>=6.0
  - rich>=13.0.0
optional_dependencies:
  longport:
    - longport>=1.0.0
  futu:
    - futu-api>=7.0.0
---

# Clawdfolio 🦙📊

AI-powered portfolio monitoring for professional investors in the Clawdbot ecosystem.
Supports multiple brokers including Longport (Longbridge) and Moomoo/Futu.

## Features

- **Multi-Broker Support**: Aggregate portfolios from Longport, Moomoo/Futu, or use demo mode
- **Risk Analytics**: Volatility, Beta, Sharpe Ratio, VaR, Max Drawdown
- **Technical Analysis**: RSI, SMA, EMA, Bollinger Bands
- **Concentration Analysis**: HHI, sector exposure, correlation warnings
- **Price Alerts**: Automated alerts for significant price movements
- **Earnings Calendar**: Track upcoming earnings for portfolio holdings
- **DCA Signals**: Dollar-cost averaging analysis and buy-the-dip signals

## Commands

### Portfolio Summary
```
/clawdfolio summary
```
Show portfolio overview with positions, P&L, and key metrics.

### Risk Analysis
```
/clawdfolio risk
```
Display comprehensive risk metrics including volatility, beta, Sharpe ratio, and VaR.

### Get Quotes
```
/clawdfolio quotes AAPL MSFT NVDA
```
Fetch real-time quotes for specified symbols.

### Check Alerts
```
/clawdfolio alerts
```
Show current portfolio alerts (price moves, RSI extremes, etc.).

### Upcoming Earnings
```
/clawdfolio earnings
```
Display earnings calendar for portfolio holdings.

### DCA Analysis
```
/clawdfolio dca AAPL --months 12 --amount 1000
```
Analyze DCA performance for a symbol.

## Configuration

Create `config.yaml` in your working directory:

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
  pnl_trigger: 500
  rsi_high: 80
  rsi_low: 20
  single_stock_threshold_top10: 0.05
  single_stock_threshold_other: 0.10

currency: USD
output_format: console
```

## Environment Variables

For Longport:
```
LONGPORT_APP_KEY=your_app_key
LONGPORT_APP_SECRET=your_app_secret
LONGPORT_ACCESS_TOKEN=your_access_token
LONGPORT_REGION=us
```

For Moomoo/Futu:
- Requires moomoo OpenD running locally on port 11111

## Installation

```bash
# Basic installation
pip install clawdfolio

# With Longport support
pip install clawdfolio[longport]

# With Moomoo/Futu support
pip install clawdfolio[futu]

# All brokers
pip install clawdfolio[all]
```
