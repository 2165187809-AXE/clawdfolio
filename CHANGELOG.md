# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/YichengYang-Ethan/clawdfolio/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/YichengYang-Ethan/clawdfolio/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/YichengYang-Ethan/clawdfolio/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/YichengYang-Ethan/clawdfolio/releases/tag/v2.0.0
