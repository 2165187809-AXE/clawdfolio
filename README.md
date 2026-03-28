# Clawdfolio

[![CI](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YichengYang-Ethan/clawdfolio/branch/main/graph/badge.svg)](https://codecov.io/gh/YichengYang-Ethan/clawdfolio)
[![PyPI](https://img.shields.io/pypi/v/clawdfolio.svg)](https://pypi.org/project/clawdfolio/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Multi-broker portfolio analytics toolkit** — risk analytics, Fama-French factor exposure, GARCH forecasting, covered call strategy, and 20+ automated finance workflows.

## Install

```bash
pip install clawdfolio                  # core (demo broker included)
pip install clawdfolio[longport]        # + Longport broker
pip install clawdfolio[futu]            # + Moomoo/Futu broker
pip install clawdfolio[all]             # everything
```

## Features

**Portfolio Management**: multi-broker aggregation (Longport, Moomoo/Futu), portfolio history snapshots, NAV curves, DCA-aware rebalancing proposals.

**Risk Analytics**: VaR/CVaR, Sharpe/Sortino, Beta, Max Drawdown, GARCH volatility forecasting, HHI concentration, 5 historical stress scenarios (COVID crash, 2022 bear, etc.).

**Factor Analysis**: Fama-French 3-factor exposure with alpha estimation.

**Options**: real-time Greeks, option chain snapshots, buyback trigger monitor.

**Covered Call Strategy**: Risk-driven CC signals backtested over 11 years — **83% win rate**, **+3.0% annualized alpha** over buy-and-hold. Integrates [Market-Bubble-Index](https://github.com/YichengYang-Ethan/Market-Bubble-Index-Dashboard) bubble risk score for entry timing.

## Quick Start

```bash
clawdfolio summary                      # portfolio overview
clawdfolio risk --detailed              # risk metrics with RSI, GARCH
clawdfolio quotes AAPL TSLA NVDA        # real-time quotes
clawdfolio factors                      # Fama-French 3-factor exposure
clawdfolio covered-call scan            # covered call opportunities
```

```python
from clawdfolio import create_broker

broker = create_broker("demo")
positions = broker.get_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.quantity} shares @ {pos.cost_price}")
```

## Tech Stack

Python, Click CLI, NumPy, pandas, scipy, arch (GARCH), yfinance, Streamlit

## License

MIT — see [LICENSE](LICENSE).
