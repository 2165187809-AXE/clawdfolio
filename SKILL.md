---
name: clawdfolio
version: 2.3.0
description: >
  Quantitative portfolio toolkit — multi-broker aggregation (Longport, Moomoo/Futu),
  institutional risk analytics (Sharpe, Sortino, VaR, CVaR, Beta, RSI), options strategy
  lifecycle, 20+ finance workflows, and CSV/JSON export. Use when the user asks about
  portfolio analysis, risk metrics, stock quotes, DCA strategy, earnings, options, or
  financial data export.
author: YICHENG YANG
license: MIT
argument-hint: <command> [options]
allowed-tools:
  - Bash(clawdfolio *)
  - Bash(pip install clawdfolio*)
  - Bash(python -c *clawdfolio*)
  - Bash(python -m clawdfolio*)
  - Read
  - Glob
  - Grep
  - Edit
  - Write
keywords:
  - quantitative-finance
  - portfolio-analytics
  - risk-management
  - options-trading
  - finance
  - dca
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
  all:
    - longport>=1.0.0
    - futu-api>=7.0.0
---

# Clawdfolio

Quantitative portfolio toolkit for professional investors. Multi-broker aggregation (Longport, Moomoo/Futu, demo), institutional risk analytics, options strategy lifecycle management, 20+ automated finance workflows, and CSV/JSON data export.

PyPI: `pip install clawdfolio`
Repo: https://github.com/YichengYang-Ethan/clawdfolio
Python: >= 3.10 | Tested: 3.10, 3.11, 3.12, 3.13

---

## CLI Commands

All commands support `--broker {longport,futu,demo,all}`, `--output {console,json}`, and `--config PATH`.

### Portfolio

```bash
clawdfolio summary              # Portfolio overview (default command)
clawdfolio summary --top 20     # Show top 20 holdings
clawdfolio quotes AAPL MSFT     # Real-time quotes
clawdfolio alerts               # Price/RSI/PnL/concentration alerts
clawdfolio alerts --severity critical
```

### Risk Analysis

```bash
clawdfolio risk                 # Volatility, Beta, Sharpe, Sortino, VaR, CVaR, drawdown
clawdfolio risk --detailed      # + RSI extremes, concentration, sector exposure, portfolio RSI
```

Risk metrics computed:
- **Volatility**: 20d, 60d, annualized
- **Beta**: vs SPY, vs QQQ
- **Sharpe Ratio**: annualized, excess return / total volatility
- **Sortino Ratio**: annualized, excess return / downside volatility only
- **VaR**: 95% and 99% (historical), absolute and percentage
- **CVaR / Expected Shortfall**: 95% and 99% — tail risk beyond VaR
- **Max Drawdown**: historical and current
- **HHI**: Herfindahl-Hirschman concentration index
- **RSI**: portfolio-level 14-day RSI
- **Correlation**: high-correlation pair detection (>= 0.8)

### Earnings

```bash
clawdfolio earnings             # Upcoming earnings (default 14 days)
clawdfolio earnings --days 30   # 30-day lookahead
```

### DCA (Dollar-Cost Averaging)

```bash
clawdfolio dca                  # DCA signals for portfolio (rebalance + dip detection)
clawdfolio dca AAPL --months 12 --amount 1000   # Historical DCA backtest
```

Signal types: `REGULAR` (scheduled), `DIP` (price drop from recent high), `REBALANCE` (weight deviation from target).

### Export

```bash
clawdfolio export portfolio                  # CSV to stdout
clawdfolio export portfolio --format json    # JSON to stdout
clawdfolio export risk --file risk.csv       # Risk metrics to file
clawdfolio export alerts --format json --file alerts.json
```

Export targets: `portfolio`, `risk`, `alerts`. Formats: `csv`, `json`.

### Options

```bash
clawdfolio options expiries TQQQ
clawdfolio options chain TQQQ --expiry 2026-03-21 --side calls --limit 10
clawdfolio options quote TQQQ --expiry 2026-03-21 --strike 80 --type C
clawdfolio options buyback          # Check buyback triggers from config
clawdfolio options buyback --strict # Exit code 1 if no targets triggered
```

### Finance Workflows

20 bundled workflows across 7 categories. Run via:

```bash
clawdfolio finance list                          # List all workflows
clawdfolio finance list --category alerts_monitors
clawdfolio finance init                          # Bootstrap workspace
clawdfolio finance run portfolio_daily_brief_tg  # Run a workflow
clawdfolio finance run dca_proposal_tg -- --budget 5000  # Pass extra args
```

Categories: `portfolio_reports`, `briefing_cards`, `alerts_monitors`, `market_intel`, `broker_snapshots`, `strategy`, `security`.

Key workflows:
| ID | Description |
|---|---|
| `portfolio_report` | Daily portfolio report with performance, risk, holdings |
| `portfolio_daily_brief_tg` | Telegram-friendly daily brief card |
| `portfolio_alert_monitor` | Deduplicated RSI/PnL/concentration/move alerts |
| `option_buyback_monitor` | Stateful option buyback trigger monitor |
| `earnings_calendar` | Upcoming earnings for current holdings |
| `dca_proposal_tg` | Budget-constrained DCA proposal card |
| `account_report` | Combined Longport + moomoo snapshot |

Workspace: `~/.clawdfolio/finance` (configurable with `--workspace`).

---

## Configuration

Config file search order:
1. `--config` CLI argument
2. `CLAWDFOLIO_CONFIG` env var
3. `./config.yaml` (current directory)
4. `~/.config/clawdfolio/config.yaml`

Supports YAML and JSON formats.

```yaml
brokers:
  longport:
    enabled: true
    timeout: 30
  futu:
    enabled: true
    extra:
      host: "127.0.0.1"
      port: 11111

alerts:
  pnl_trigger: 500        # Absolute dollar P&L trigger
  pnl_step: 500           # Step size for P&L dedup
  rsi_high: 80            # RSI overbought threshold
  rsi_low: 20             # RSI oversold threshold
  single_stock_threshold_top10: 0.05   # 5% move for top-10 holdings
  single_stock_threshold_other: 0.10   # 10% move for other holdings
  move_step: 0.01         # 1% step for move dedup
  concentration_threshold: 0.25

# Leveraged ETF auto-scaling (threshold * leverage factor)
leveraged_etfs:
  TQQQ: ["QQQ", 3, "Nasdaq 100"]
  SOXL: ["SOXX", 3, "Semiconductors"]
  SQQQ: ["QQQ", -3, "Nasdaq 100"]
  UPRO: ["SPY", 3, "S&P 500"]

option_buyback:
  enabled: true
  symbol: TQQQ
  targets:
    - name: tqqq_mar_80c
      strike: 80.0
      expiry: "2026-03-21"
      option_type: C
      trigger_price: 0.15
      qty: 5
      reset_pct: 0.20

currency: USD
timezone: America/New_York
cache_ttl: 300           # Market data cache in seconds
output_format: console   # console | json
verbose: false
```

---

## Environment Variables

### Longport Broker
```bash
LONGPORT_APP_KEY=your_app_key
LONGPORT_APP_SECRET=your_app_secret
LONGPORT_ACCESS_TOKEN=your_access_token
LONGPORT_REGION=us                       # optional, defaults to "us"
```

### Moomoo/Futu Broker
No env vars needed. Requires moomoo OpenD running locally (default `127.0.0.1:11111`). Configure host/port in `brokers.futu.extra`.

### Config Override
```bash
CLAWDFOLIO_CONFIG=/path/to/config.yaml
```

---

## Installation

```bash
pip install clawdfolio               # Core (yfinance + demo broker)
pip install clawdfolio[longport]     # + Longport broker
pip install clawdfolio[futu]         # + Moomoo/Futu broker
pip install clawdfolio[all]          # All brokers
pip install clawdfolio[dev]          # + pytest, mypy, ruff (development)
```

---

## Python API

### Core Types

```python
from clawdfolio import Symbol, Position, Quote, Portfolio, RiskMetrics, Alert
from clawdfolio import Config, load_config
from clawdfolio.core.types import Exchange, AlertType, AlertSeverity
```

### Brokers

```python
from clawdfolio.brokers import get_broker, list_brokers, BaseBroker

broker = get_broker("longport")      # or "futu", "demo", "all"
with broker:
    portfolio = broker.get_portfolio()
    quote = broker.get_quote(Symbol(ticker="AAPL"))
```

### Risk Analysis

```python
from clawdfolio.analysis.risk import (
    analyze_risk,                    # Full analysis -> RiskMetrics
    calculate_volatility,
    calculate_beta,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_var,
    calculate_cvar,
    calculate_max_drawdown,
    calculate_correlation_matrix,
)

metrics = analyze_risk(portfolio)
print(metrics.sharpe_ratio, metrics.sortino_ratio)
print(metrics.var_95, metrics.cvar_95)
```

### Technical Indicators

```python
from clawdfolio.analysis.technical import (
    calculate_rsi,                   # Wilder-smoothed RSI (scalar)
    calculate_rsi_series,            # Full RSI series
    calculate_sma, calculate_ema,
    calculate_bollinger_bands,
    calculate_macd,
    detect_rsi_extremes,
    is_golden_cross, is_death_cross,
)
```

### Market Data

```python
from clawdfolio.market import (
    get_price, get_history, get_history_multi,
    get_quotes_yfinance, get_news, get_earnings_date,
    get_option_quote, get_option_chain, get_option_expiries,
    is_market_open, get_market_status, is_trading_day,
    risk_free_rate,
)
```

### DCA Strategy

```python
from clawdfolio.strategies.dca import (
    DCAStrategy, check_dca_signals, calculate_dca_performance,
)

strategy = DCAStrategy(targets={"AAPL": 0.30, "MSFT": 0.20}, monthly_amount=2000)
signals = strategy.check_signals(portfolio)
alloc = strategy.get_regular_allocation()
perf = calculate_dca_performance("AAPL", monthly_amount=1000, months=12)
```

### Export

```python
from clawdfolio.output import (
    export_portfolio_csv, export_portfolio_json,
    export_risk_csv, export_risk_json,
    export_alerts_csv, export_alerts_json,
)

csv_str = export_portfolio_csv(portfolio)
json_str = export_risk_json(metrics)
```

---

## Monitors

### Price Monitor
Step-based deduplication: fires once per threshold crossing, then only on new steps. Leveraged ETFs auto-scale thresholds by leverage factor. State persisted to `~/.cache/clawdfolio/price_alert_state.json`.

### Earnings Monitor
Alerts for upcoming earnings within configurable window. Severity escalates when earnings are within 1 day or position weight >= 10%.

### Options Buyback Monitor
Stateful trigger monitor with file locking. Auto-resets when price rises above `trigger_price * (1 + reset_pct)`. State persisted to `~/.cache/clawdfolio/option_buyback_state.json`.

---

## Broker Support

| Broker | Package | Auth | Notes |
|---|---|---|---|
| **Longport** | `clawdfolio[longport]` | Env vars | US equities, fd-level noise suppression for Rust SDK |
| **Moomoo/Futu** | `clawdfolio[futu]` | Local OpenD | US equities, TCP to `127.0.0.1:11111` |
| **Demo** | Built-in | None | 10 hardcoded positions, +/-2% random variance |
| **Aggregator** | Built-in | Per-broker | Merges multiple brokers, deduplicates positions |

Custom brokers: subclass `BaseBroker` and use `@register_broker("name")`.

---

## Trading Calendar

Algorithmic US holiday generation for any year (NYSE holidays: New Year, MLK, Presidents, Good Friday, Memorial, Juneteenth, Independence, Labor, Thanksgiving, Christmas). Hardcoded 2024-2027 fast-path cache. Easter computed via anonymous Gregorian algorithm.

```python
from clawdfolio.market import is_trading_day, next_trading_day, trading_days_between
```
