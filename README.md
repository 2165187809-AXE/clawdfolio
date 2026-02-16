# Clawdfolio 🦙📊

[![CI](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/clawdfolio.svg)](https://pypi.org/project/clawdfolio/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-blueviolet)](https://github.com/anthropics/claude-code)

English | [中文](README_CN.md)

> **Production-grade quantitative portfolio toolkit** — multi-broker aggregation, institutional risk analytics, options lifecycle management, and 20+ automated finance workflows.
>
> *Also available as a native [Claude Code](https://github.com/anthropics/claude-code) / Clawdbot skill.*

---

## Why Clawdfolio?

| Traditional Tools | Clawdfolio |
|-------------------|------------|
| Manual data entry | Auto-sync from Longport, Moomoo/Futu |
| Basic P&L tracking | VaR, Sharpe, Beta, Max Drawdown, HHI |
| Single broker view | Multi-broker aggregation |
| Spreadsheet alerts | Smart RSI / price / P&L alerts |
| No extensibility | Python API + CLI + Claude Code skill |

---

## Features

- **Multi-Broker Support** — Longport (Longbridge), Moomoo/Futu, or demo mode
- **Risk Analytics** — Volatility, Beta, Sharpe Ratio, Value at Risk, Max Drawdown
- **Technical Analysis** — RSI, SMA, EMA, Bollinger Bands
- **Concentration Analysis** — HHI index, sector exposure, correlation warnings
- **Smart Alerts** — Price movements, RSI extremes, P&L thresholds
- **Earnings Calendar** — Track upcoming earnings for holdings
- **DCA Analysis** — Dollar-cost averaging signals
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
| **Volatility** | 20-day and 60-day annualized |
| **Beta** | Correlation with SPY/QQQ |
| **Sharpe Ratio** | Risk-adjusted returns |
| **VaR** | Value at Risk (95%/99%) |
| **Max Drawdown** | Largest peak-to-trough decline |
| **HHI** | Portfolio concentration index |

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

## Claude Code & Clawdbot Integration

Clawdfolio works as a native skill in [Claude Code](https://github.com/anthropics/claude-code) and Clawdbot environments:

```
/clawdfolio summary
/clawdfolio risk
/clawdfolio quotes AAPL MSFT NVDA
/clawdfolio alerts
/clawdfolio options chain TQQQ --expiry 2026-06-18
```

The skill is registered via [`SKILL.md`](SKILL.md) and supports all CLI commands through natural language interaction.

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

## Ecosystem

Clawdfolio is the data hub of a quantitative finance toolkit. Other projects consume its output or share its analytical methodology.

```
         ┌──────────────────────────┐
         │   ML Research Layer      │
         │  crypto-prediction       │
         │  ESG-prediction          │
         └────────────┬─────────────┘
                      │ research informs alert thresholds
         ┌────────────▼─────────────┐
         │  clawdfolio (this repo)  │
         │  brokers · risk · alerts │
         │  clawdfolio summary -o json
         └────────────┬─────────────┘
                      │ JSON data feed
         ┌────────────▼─────────────┐
         │   Visualization Layer    │
         │  investment-dashboard    │
         │  QQQ-200D-Dashboard     │
         └──────────────────────────┘
```

| Project | Layer | Relationship |
|---------|-------|-------------|
| **clawdfolio** (this repo) | Core Engine | Risk analytics, broker integration, signal generation, options strategy |
| [investment-dashboard](https://github.com/YichengYang-Ethan/investment-dashboard) | Visualization | Web frontend — consumes `clawdfolio summary -o json` for portfolio data |
| [QQQ-200D-Deviation-Dashboard](https://github.com/YichengYang-Ethan/QQQ-200D-Deviation-Dashboard) | Visualization | Implements clawdfolio's SMA deviation methodology as a standalone React dashboard |
| [crypto-return-prediction](https://github.com/YichengYang-Ethan/crypto-return-prediction-kaggle) | ML Research | Short-term momentum prediction — shares RSI/Bollinger feature engineering |
| [ESG-Driven-Stock-Value-Prediction](https://github.com/YichengYang-Ethan/ESG-Driven-Stock-Value-Prediction) | ML Research | Long-term value factor research — ESG signals complementing technical indicators |

---

<details>
<summary><strong>Changelog</strong></summary>

### v2.2.0 (2025-02-14)

- Thread-safe market data caching (`threading.Lock`)
- Batch quote fetching via `yf.download` with per-ticker fallback
- Shared `suppress_stdio` utility (DRY refactor)
- Dynamic CLI version from `__version__`
- PEP 561 compliance (`py.typed` marker)
- Structured logging across core modules
- Centralized ticker normalization (`_yf_symbol()`)
- Config path migration to `clawdfolio` namespace (backward-compatible)

### v2.1.0 (2025-01-28)

- Options Strategy Playbook v2.1 (`docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md`)
- Research-to-execution framework for CC and Sell Put lifecycle
- Explicit gamma-risk, margin, leverage, and assignment decision rules

### v2.0.0 (2025-01-15)

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
- [Claude Code](https://github.com/anthropics/claude-code)
