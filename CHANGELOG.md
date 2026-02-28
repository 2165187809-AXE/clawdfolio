# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Bubble Risk Score integration** — Real-time drawdown risk scoring (0-100) from [Market-Bubble-Index-Dashboard](https://github.com/YichengYang-Ethan/Market-Bubble-Index-Dashboard), with SMA-200 deviation, trend acceleration, and volatility regime components.
- **Risk-driven Covered Call strategy** (`strategies/covered_call.py`) — Quantitative CC signal generation using Bubble Risk Score. Backtested over 11 years (2014-2026): Risk >= 66 threshold, 83% win rate, +3.0% annualized alpha, 1.5% assignment rate.
- `BubbleRiskResult.should_sell_cc` and `BubbleRiskResult.cc_delta` convenience properties for quick decision-making.
- `CoveredCallStrategy` class with configurable thresholds, delta targets, and DTE parameters.
- `check_cc_signals()` and `get_cc_recommendation()` convenience functions.
- `fetch_bubble_risk()` — Dashboard API integration with automatic fallback to live calculation.
- Tests for covered call strategy (26 tests) and bubble risk score (21 tests), boosting coverage above 70%.

### Fixed

- Ruff lint errors in `analysis/bubble.py` (E402: module-level imports not at top) and `strategies/covered_call.py` (F401: unused import, UP035/UP045: modern type annotation style).

## [2.3.0] - 2026-02-16

### Added

- **Sortino ratio** (`calculate_sortino_ratio()`) — penalises only downside volatility, complementing Sharpe for leveraged-ETF portfolios.
- **CVaR / Expected Shortfall** (`calculate_cvar()`) at 95% and 99% confidence — answers "how bad is it when VaR is breached?"
- **Portfolio RSI** — `rsi_portfolio` field now populated in `analyze_risk()` using the portfolio cumulative-return series.
- **Portfolio data export** — new `clawdfolio export` CLI command with CSV and JSON output for portfolio, risk metrics, and alerts (`output/export.py`).
- **Dynamic trading calendar** — algorithmic US holiday generation for any year (Easter via anonymous Gregorian algorithm, nth-weekday rules for MLK, Presidents, Memorial, Labor, Thanksgiving). Hardcoded 2024-2026 sets retained as fast-path cache.
- Tests for previously untested modules: `test_price_monitor.py`, `test_earnings_monitor.py`, `test_dca.py`, `test_json_output.py`, `test_export.py`.
- Python 3.13 added to CI matrix and `pyproject.toml` classifiers.
- `pip-audit` security scanning step in CI.
- Coverage enforcement: `--cov-fail-under=48` in CI pytest step (baseline floor; CLI and broker modules need additional coverage).

### Changed

- **Version bumped to 2.3.0.**
- `analyze_risk()` fetches SPY and QQQ benchmarks in a single `get_history_multi()` call instead of two sequential `get_history()` calls.
- `Portfolio.get_position()` now uses O(1) dict lookup via `_ticker_index` instead of O(n) linear scan.
- `calculate_ema()` replaced Python for-loop with `pd.Series.ewm()` for better performance.

### Fixed

- `calculate_dca_performance()` no longer passes invalid period strings (e.g. `"12mo"`) to yfinance; uses `_months_to_period()` mapping.
- `Position._weight` attribute properly declared as a dataclass field (`field(default=0.0, init=False, repr=False)`), eliminating `getattr` fallback.
- Cache TOCTOU race in `_cached()` — per-key locking prevents redundant expensive calls from concurrent threads.

## [2.2.0] - 2026-02-14

### Added

- `py.typed` marker file for PEP 561 compliance, enabling downstream type-checking support.
- `clawdfolio.utils.suppress` shared module with `suppress_stdio` context manager (DRY refactor from `brokers/futu.py` and `brokers/longport.py`).
- `CHANGELOG.md` to track version history.
- Structured `logging` across core modules (`market/data.py`, `brokers/futu.py`, `brokers/longport.py`, `cli/main.py`).
- `_yf_symbol()` centralised ticker normalisation helper in `market/data.py`.

### Changed

- **Version bumped to 2.2.0.**
- CLI `--version` flag now reads dynamically from `clawdfolio.__version__` instead of a hardcoded string.
- `get_quotes_yfinance()` rewritten to use `yf.download` for batch retrieval with per-ticker fallback, significantly reducing API calls.
- Market data cache (`_cache`) is now protected by `threading.Lock` for thread-safe concurrent access.
- NaN check in `_safe_float()` replaced from `num == num` idiom to explicit `math.isnan(num)`.
- Config search now prefers `CLAWDFOLIO_CONFIG` env var and `~/.config/clawdfolio/` paths, with backward-compatible fallback to `PORTFOLIO_MONITOR_CONFIG` and `~/.config/portfolio-monitor/`.
- Module docstring in `core/config.py` and `core/exceptions.py` updated from "Portfolio Monitor" to "Clawdfolio".

### Fixed

- All repository URLs in `pyproject.toml`, `README.md`, and `README_CN.md` corrected from `2165187809-AXE/clawdfolio` to `YichengYang-Ethan/clawdfolio`.
- Removed unused `import io` side-effect in `brokers/longport.py` (kept only where actually needed).

## [2.1.0] - 2026-01-28

### Added

- Dedicated options strategy playbook (`docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md`).
- Research-to-execution alignment for CC and Sell Put lifecycle management.
- Explicit gamma-risk, margin, leverage, roll, assignment, and pause-condition decision rules.
- Feature mapping connecting strategy decisions to `clawdfolio options` and `clawdfolio finance` workflows.

## [2.0.0] - 2026-01-15

### Added

- Full finance migration from `~/clawd/scripts` (20 production workflows).
- `clawdfolio finance` command group (list, init, run).
- Categorized workflow catalog and bundled `legacy_finance` package.
- Mutable workspace bootstrap (`~/.clawdfolio/finance`).
- Wilder RSI smoothing, Longport symbol fix, yfinance hardening.
- Options quote/chain/buyback monitor.

[Unreleased]: https://github.com/YichengYang-Ethan/clawdfolio/compare/v2.3.0...HEAD
[2.3.0]: https://github.com/YichengYang-Ethan/clawdfolio/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/YichengYang-Ethan/clawdfolio/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/YichengYang-Ethan/clawdfolio/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/YichengYang-Ethan/clawdfolio/releases/tag/v2.0.0
