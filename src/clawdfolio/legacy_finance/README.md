# Legacy Finance Scripts (v2 Migration)

Legacy finance scripts migrated from a personal automation system.

## Layout

- `scripts/`
- `scripts/lib/`
- `archive_scripts/`

## Active Workflow Groups

- Portfolio reports: `account_report.py`, `portfolio_report.py`, `portfolio_report_clean.py`, `portfolio_analysis_enhanced.py`
- Briefing cards: `portfolio_daily_brief*.py` and clean wrappers
- Alerts/monitors: `portfolio_alert_monitor.py`, `option_buyback_monitor.py`
- Market intelligence: `realtime_quotes.py`, `earnings_calendar.py`, `market_news.py`
- Broker snapshots: `longport_assets_summary.py`, `longport_assets_message.py`, `moomoo_assets_message.py`
- Strategy/security: `dca_proposal_tg.py`, `security_pin.py`

## Notes

- Scripts remain executable as standalone legacy workflows.
- Runtime state and local edits are written into the mutable workspace created by `clawdfolio finance init`.
- Historical scripts retained in `archive_scripts/` for traceability and rollback.
