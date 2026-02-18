"""CLI entry point for Clawdfolio."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING, Any

from .. import __version__

if TYPE_CHECKING:
    from argparse import Namespace

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    from ..finance.workflows import category_choices

    parser = argparse.ArgumentParser(
        prog="clawdfolio",
        description="Quantitative portfolio toolkit with multi-broker aggregation, risk analytics, and finance workflows",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--broker",
        choices=["longport", "futu", "demo", "all"],
        default="all",
        help="Broker to use (default: all)",
    )

    parser.add_argument(
        "--output",
        "-o",
        choices=["console", "json"],
        default="console",
        help="Output format (default: console)",
    )

    parser.add_argument(
        "--config",
        "-c",
        help="Path to config file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Show portfolio summary")
    summary_parser.add_argument(
        "--top", "-n",
        type=int,
        default=10,
        help="Number of top holdings to show (default: 10)",
    )

    # Quotes command
    quotes_parser = subparsers.add_parser("quotes", help="Get real-time quotes")
    quotes_parser.add_argument(
        "symbols",
        nargs="+",
        help="Symbols to get quotes for",
    )

    # Risk command
    risk_parser = subparsers.add_parser("risk", help="Show risk metrics")
    risk_parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="Show detailed risk analysis",
    )

    # Alerts command
    alerts_parser = subparsers.add_parser("alerts", help="Show current alerts")
    alerts_parser.add_argument(
        "--severity",
        choices=["info", "warning", "critical"],
        help="Filter by severity",
    )
    alerts_parser.add_argument(
        "--notify",
        choices=["telegram", "email"],
        help="Send alerts via notification channel",
    )
    alerts_parser.add_argument(
        "--bot-token",
        help="Telegram bot token (overrides config)",
    )
    alerts_parser.add_argument(
        "--chat-id",
        help="Telegram chat ID (overrides config)",
    )
    alerts_parser.add_argument(
        "--smtp-host",
        help="SMTP host (overrides config)",
    )
    alerts_parser.add_argument(
        "--smtp-user",
        help="SMTP username (overrides config)",
    )
    alerts_parser.add_argument(
        "--to",
        help="Email recipient (overrides config)",
    )

    # Earnings command
    earnings_parser = subparsers.add_parser("earnings", help="Show upcoming earnings")
    earnings_parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Days to look ahead (default: 14)",
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export portfolio data to CSV or JSON files")
    export_parser.add_argument(
        "what",
        choices=["portfolio", "risk", "alerts"],
        help="What to export",
    )
    export_parser.add_argument(
        "--format", "-f",
        choices=["csv", "json"],
        default="csv",
        help="Export format (default: csv)",
    )
    export_parser.add_argument(
        "--file",
        help="Output file path (default: stdout)",
    )

    # DCA command
    dca_parser = subparsers.add_parser("dca", help="DCA signals and analysis")
    dca_parser.add_argument(
        "symbol",
        nargs="?",
        help="Symbol to analyze DCA performance",
    )
    dca_parser.add_argument(
        "--months",
        type=int,
        default=12,
        help="Months to analyze (default: 12)",
    )
    dca_parser.add_argument(
        "--amount",
        type=float,
        default=1000.0,
        help="Monthly DCA amount (default: 1000)",
    )

    # Options command
    options_parser = subparsers.add_parser(
        "options",
        help="Option quote, chain, expiry list, and buyback monitor",
    )
    options_subparsers = options_parser.add_subparsers(
        dest="options_command",
        help="Options subcommands",
    )

    options_quote_parser = options_subparsers.add_parser(
        "quote",
        help="Get single option quote with Greeks",
    )
    options_quote_parser.add_argument("symbol", help="Underlying ticker, e.g. TQQQ")
    options_quote_parser.add_argument(
        "--expiry",
        required=True,
        help="Expiry date (YYYY-MM-DD)",
    )
    options_quote_parser.add_argument(
        "--strike",
        required=True,
        type=float,
        help="Strike price",
    )
    options_quote_parser.add_argument(
        "--type",
        dest="option_type",
        choices=["C", "P", "c", "p"],
        default="C",
        help="Option type: C or P",
    )

    options_chain_parser = options_subparsers.add_parser(
        "chain",
        help="Get option chain snapshot",
    )
    options_chain_parser.add_argument("symbol", help="Underlying ticker, e.g. TQQQ")
    options_chain_parser.add_argument(
        "--expiry",
        required=True,
        help="Expiry date (YYYY-MM-DD)",
    )
    options_chain_parser.add_argument(
        "--side",
        choices=["both", "calls", "puts"],
        default="both",
        help="Which side of chain to display",
    )
    options_chain_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Rows per side (default: 10)",
    )

    options_expiries_parser = options_subparsers.add_parser(
        "expiries",
        help="List available option expiries",
    )
    options_expiries_parser.add_argument("symbol", help="Underlying ticker, e.g. TQQQ")

    options_buyback_parser = options_subparsers.add_parser(
        "buyback",
        help="Run buyback trigger check from config option_buyback.targets",
    )
    options_buyback_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if no target is triggered",
    )

    # Factors command
    subparsers.add_parser("factors", help="Fama-French factor exposure analysis")

    # Stress command
    subparsers.add_parser("stress", help="Leverage-adjusted stress testing")

    # Greeks command
    subparsers.add_parser("greeks", help="Aggregate portfolio-level Greeks")

    # Snapshot command
    snapshot_parser = subparsers.add_parser("snapshot", help="Save portfolio snapshot to history")
    snapshot_parser.add_argument(
        "--file",
        help="Path to history CSV (default: ~/.clawdfolio/history.csv)",
    )

    # Performance command
    performance_parser = subparsers.add_parser("performance", help="Show portfolio performance over time")
    performance_parser.add_argument(
        "--period",
        choices=["1m", "3m", "6m", "1y", "all"],
        default="all",
        help="Period to display (default: all)",
    )
    performance_parser.add_argument(
        "--file",
        help="Path to history CSV (default: ~/.clawdfolio/history.csv)",
    )

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare portfolio vs benchmark")
    compare_parser.add_argument(
        "benchmark",
        help="Benchmark ticker (e.g. SPY, QQQ)",
    )
    compare_parser.add_argument(
        "--period",
        choices=["1m", "3m", "6m", "1y", "all"],
        default="1y",
        help="Period to compare (default: 1y)",
    )
    compare_parser.add_argument(
        "--file",
        help="Path to history CSV (default: ~/.clawdfolio/history.csv)",
    )

    # Finance command
    finance_parser = subparsers.add_parser(
        "finance",
        help="Run migrated local finance workflows (v2)",
    )
    finance_subparsers = finance_parser.add_subparsers(
        dest="finance_command",
        help="Finance workflow actions",
    )

    finance_list_parser = finance_subparsers.add_parser(
        "list",
        help="List available finance workflows",
    )
    finance_list_parser.add_argument(
        "--category",
        choices=category_choices(),
        help="Filter by workflow category",
    )

    finance_init_parser = finance_subparsers.add_parser(
        "init",
        help="Initialize local finance workspace",
    )
    finance_init_parser.add_argument(
        "--workspace",
        help="Workspace path (default: ~/.clawdfolio/finance)",
    )
    finance_init_parser.add_argument(
        "--sync",
        action="store_true",
        help="Force sync all bundled workflow scripts into workspace",
    )

    finance_run_parser = finance_subparsers.add_parser(
        "run",
        help="Run one finance workflow by id",
    )
    finance_run_parser.add_argument(
        "workflow",
        help="Workflow id, e.g. portfolio_daily_brief_tg",
    )
    finance_run_parser.add_argument(
        "--workspace",
        help="Workspace path (default: ~/.clawdfolio/finance)",
    )
    finance_run_parser.add_argument(
        "--sync",
        action="store_true",
        help="Force sync scripts before run",
    )

    return parser


def _get_portfolio(args: Namespace):  # type: ignore[no-untyped-def]
    """Get portfolio from the selected broker(s)."""
    from ..brokers import get_broker
    from ..brokers.demo import DemoBroker  # noqa: F401 - registers broker

    if args.broker == "all":
        from ..brokers.aggregator import aggregate_portfolios
        from ..core.config import load_config

        # Import broker modules to register them
        try:
            from ..brokers.futu import FutuBroker  # noqa: F401
        except ImportError:
            pass
        try:
            from ..brokers.longport import LongportBroker  # noqa: F401
        except ImportError:
            pass

        config = load_config(getattr(args, "config", None))
        brokers = []
        for name, bcfg in config.brokers.items():
            if not bcfg.enabled or name == "demo":
                continue
            try:
                brokers.append(get_broker(name, bcfg))
            except KeyError:
                pass

        if not brokers:
            # Fall back to demo if no real brokers configured
            broker = get_broker("demo")
            broker.connect()
            return broker.get_portfolio()

        return aggregate_portfolios(brokers)

    broker = get_broker(args.broker)
    broker.connect()
    return broker.get_portfolio()


def cmd_summary(args: Namespace) -> int:
    """Handle summary command."""
    from ..output import print_portfolio

    try:
        portfolio = _get_portfolio(args)

        if args.output == "json":
            from ..output.json import JSONFormatter
            formatter = JSONFormatter()
            print(formatter.format_portfolio(portfolio))
        else:
            print_portfolio(portfolio)

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_quotes(args: Namespace) -> int:
    """Handle quotes command."""
    from ..market.data import get_quotes_yfinance
    from ..output.json import to_json

    quotes = get_quotes_yfinance(args.symbols)

    if args.output == "json":
        data = {
            ticker: {
                "price": float(q.price),
                "prev_close": float(q.prev_close) if q.prev_close else None,
                "change_pct": q.change_pct,
            }
            for ticker, q in quotes.items()
        }
        print(to_json(data))
    else:
        print("\nQuotes:")
        print("-" * 50)
        for ticker, q in quotes.items():
            change = q.change_pct or 0
            sign = "+" if change > 0 else ""
            print(f"{ticker:8} ${float(q.price):>10,.2f}  {sign}{change*100:.2f}%")

    return 0


def cmd_risk(args: Namespace) -> int:
    """Handle risk command."""
    from ..analysis.risk import analyze_risk
    from ..output import print_risk_metrics

    try:
        portfolio = _get_portfolio(args)
        metrics = analyze_risk(portfolio)

        if args.output == "json":
            from ..output.json import JSONFormatter
            formatter = JSONFormatter()
            print(formatter.format_risk_metrics(metrics))
        else:
            print_risk_metrics(metrics)

            if args.detailed:
                _print_detailed_risk(portfolio, metrics)

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _print_detailed_risk(portfolio: Any, metrics: Any) -> None:
    """Print additional detailed risk info: correlation, sectors, RSI, concentration."""
    from ..analysis.concentration import analyze_concentration
    from ..analysis.technical import detect_rsi_extremes

    tickers = [p.symbol.ticker for p in portfolio.positions]

    # RSI extremes
    rsi_results = detect_rsi_extremes(tickers, overbought=70, oversold=30)
    if rsi_results:
        print("\nRSI Extremes:")
        print("-" * 40)
        for r in rsi_results:
            label = "OVERBOUGHT" if r.is_overbought else "OVERSOLD"
            print(f"  {r.ticker:8} RSI={r.rsi:5.1f}  [{label}]")

    # GARCH volatility
    if metrics.garch_vol_forecast is not None:
        print(f"\nGARCH(1,1) Vol Forecast: {metrics.garch_vol_forecast*100:.1f}%")

    # Concentration
    conc = analyze_concentration(portfolio)
    if conc:
        cm = conc.get("metrics")
        if cm:
            print(f"\nConcentration: HHI={cm.hhi:.3f}  "
                  f"Top-5={cm.top_5_weight*100:.1f}%  "
                  f"Max={cm.max_position_ticker} {cm.max_position_weight*100:.1f}%")
        eff_n = conc.get("effective_n")
        n_pos = conc.get("n_positions")
        if eff_n is not None and n_pos is not None:
            print(f"Effective N: {eff_n:.1f} (out of {n_pos} positions)")
        sectors = conc.get("sectors", [])
        if sectors:
            print("\nSector Exposure:")
            for s in sectors[:5]:
                print(f"  {s.sector or 'Unknown':20} {s.weight*100:5.1f}%  ({len(s.tickers)} positions)")

    # Portfolio RSI
    if metrics.rsi_portfolio is not None:
        print(f"\nPortfolio RSI (14d): {metrics.rsi_portfolio:.1f}")


def cmd_alerts(args: Namespace) -> int:
    """Handle alerts command."""
    from ..core.config import load_config
    from ..monitors.earnings import EarningsMonitor
    from ..monitors.price import PriceMonitor

    try:
        portfolio = _get_portfolio(args)
        config = load_config(getattr(args, "config", None))

        # Collect alerts
        all_alerts = []
        monitor = PriceMonitor.from_config(config)
        monitor.leveraged_etfs = config.leveraged_etfs
        all_alerts.extend(monitor.check_portfolio(portfolio))
        all_alerts.extend(EarningsMonitor().check_portfolio(portfolio))

        # Filter by severity if specified
        if args.severity:
            all_alerts = [a for a in all_alerts if a.severity.value == args.severity]

        if args.output == "json":
            from ..output.json import JSONFormatter
            formatter = JSONFormatter()
            print(formatter.format_alerts(all_alerts))
        else:
            from ..output.console import RICH_AVAILABLE, ConsoleFormatter
            if RICH_AVAILABLE:
                ConsoleFormatter().print_alerts(all_alerts)
            elif not all_alerts:
                print("No alerts")
            else:
                for alert in all_alerts:
                    print(str(alert))
                    print()

        # Send notifications if requested
        notify_method = getattr(args, "notify", None)
        if notify_method and all_alerts:
            _send_alert_notifications(args, config, all_alerts, notify_method)

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _send_alert_notifications(args: Any, config: Any, alerts: Any, method: str) -> None:
    """Send alert notifications via the specified method."""
    from ..notifications import send_notification

    # Build message text
    lines = [f"Clawdfolio Alerts ({len(alerts)} triggered)\n"]
    for a in alerts:
        lines.append(f"[{a.severity.value.upper()}] {a.title}")
        lines.append(a.message)
        lines.append("")
    message = "\n".join(lines)

    # Build config from CLI args + config file fallback
    if method == "telegram":
        notif_config = dict(config.notifications.telegram)
        if getattr(args, "bot_token", None):
            notif_config["bot_token"] = args.bot_token
        if getattr(args, "chat_id", None):
            notif_config["chat_id"] = args.chat_id
    elif method == "email":
        notif_config = dict(config.notifications.email)
        if getattr(args, "smtp_host", None):
            notif_config["smtp_host"] = args.smtp_host
        if getattr(args, "smtp_user", None):
            notif_config["username"] = args.smtp_user
        if getattr(args, "to", None):
            notif_config["to"] = args.to
    else:
        print(f"Unknown notification method: {method}", file=sys.stderr)
        return

    try:
        send_notification(method, notif_config, message)
        print(f"Notifications sent via {method}.")
    except Exception as e:
        print(f"Failed to send {method} notification: {e}", file=sys.stderr)


def cmd_earnings(args: Namespace) -> int:
    """Handle earnings command."""
    from ..monitors.earnings import format_earnings_calendar, get_upcoming_earnings

    try:
        portfolio = _get_portfolio(args)
        events = get_upcoming_earnings(portfolio, days_ahead=args.days)

        if args.output == "json":
            from ..output.json import to_json
            data = [
                {
                    "ticker": e.ticker,
                    "date": e.date.isoformat(),
                    "timing": e.timing,
                    "days_until": e.days_until,
                    "weight": e.weight,
                }
                for e in events
            ]
            print(to_json(data))
        else:
            print(format_earnings_calendar(events))

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_export(args: Namespace) -> int:
    """Handle export command."""
    from ..brokers import get_broker
    from ..brokers.demo import DemoBroker  # noqa: F401
    from ..output.export import (
        export_alerts_csv,
        export_alerts_json,
        export_portfolio_csv,
        export_portfolio_json,
        export_risk_csv,
        export_risk_json,
    )

    broker_name = args.broker if args.broker != "all" else "demo"

    try:
        broker = get_broker(broker_name)
        broker.connect()
        portfolio = broker.get_portfolio()

        if args.what == "portfolio":
            content = export_portfolio_csv(portfolio) if args.format == "csv" else export_portfolio_json(portfolio)
        elif args.what == "risk":
            from ..analysis.risk import analyze_risk
            metrics = analyze_risk(portfolio)
            content = export_risk_csv(metrics) if args.format == "csv" else export_risk_json(metrics)
        elif args.what == "alerts":
            from ..monitors.earnings import EarningsMonitor
            from ..monitors.price import PriceMonitor
            all_alerts = []
            all_alerts.extend(PriceMonitor().check_portfolio(portfolio))
            all_alerts.extend(EarningsMonitor().check_portfolio(portfolio))
            content = export_alerts_csv(all_alerts) if args.format == "csv" else export_alerts_json(all_alerts)
        else:
            print(f"Unknown export target: {args.what}", file=sys.stderr)
            return 1

        if args.file:
            with open(args.file, "w") as f:
                f.write(content)
            print(f"Exported to {args.file}")
        else:
            print(content, end="")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_dca(args: Namespace) -> int:
    """Handle DCA command."""
    from ..output.json import to_json
    from ..strategies.dca import calculate_dca_performance

    if not args.symbol:
        print("Usage: clawdfolio dca SYMBOL [--months N] [--amount N]")
        return 1

    try:
        result = calculate_dca_performance(
            args.symbol,
            monthly_amount=args.amount,
            months=args.months,
        )

        if not result:
            print(f"Could not fetch data for {args.symbol}")
            return 1

        if args.output == "json":
            print(to_json(result))
        else:
            print(f"\nDCA Analysis: {args.symbol}")
            print("-" * 40)
            print(f"Period: {result['months']} months")
            print(f"Monthly Amount: ${args.amount:,.2f}")
            print(f"Total Invested: ${result['total_invested']:,.2f}")
            print(f"Shares Accumulated: {result['total_shares']:,.2f}")
            print(f"Avg Cost Basis: ${result['avg_cost_basis']:,.2f}")
            print(f"Current Price: ${result['current_price']:,.2f}")
            print(f"Current Value: ${result['current_value']:,.2f}")
            sign = "+" if result['total_return'] > 0 else ""
            print(f"Total Return: {sign}{result['total_return_pct']:.1f}%")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_snapshot(args: Namespace) -> int:
    """Handle snapshot command — save portfolio snapshot to history."""
    from ..core.history import append_snapshot

    try:
        portfolio = _get_portfolio(args)
        written, msg = append_snapshot(portfolio, path=getattr(args, "file", None))
        print(msg)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_performance(args: Namespace) -> int:
    """Handle performance command — show NAV curve and stats."""
    from ..core.history import (
        compute_performance,
        filter_by_period,
        format_performance_table,
        read_snapshots,
    )
    from ..output.json import to_json

    try:
        rows = read_snapshots(path=getattr(args, "file", None))
        rows = filter_by_period(rows, period=args.period)
        perf = compute_performance(rows)

        if args.output == "json":
            print(to_json(perf))
        else:
            print(format_performance_table(perf))

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_compare(args: Namespace) -> int:
    """Handle compare command — portfolio vs benchmark."""
    from ..core.history import filter_by_period, read_snapshots
    from ..market.data import get_history
    from ..output.json import to_json

    try:
        rows = read_snapshots(path=getattr(args, "file", None))
        rows = filter_by_period(rows, period=args.period)

        if not rows:
            print("No snapshot data available. Run 'clawdfolio snapshot' first.")
            return 1

        sorted_rows = sorted(rows, key=lambda r: r.date)
        port_start = sorted_rows[0].net_assets
        port_end = sorted_rows[-1].net_assets
        port_return = ((port_end - port_start) / port_start * 100) if port_start else 0.0

        # Fetch benchmark
        period_map = {"1m": "1mo", "3m": "3mo", "6m": "6mo", "1y": "1y", "all": "5y"}
        yf_period = period_map.get(args.period, "1y")
        bench_df = get_history(args.benchmark, period=yf_period)

        if bench_df is None or bench_df.empty or "Close" not in bench_df.columns:
            print(f"Could not fetch benchmark data for {args.benchmark}")
            return 1

        close = bench_df["Close"].dropna()
        if close.empty:
            print(f"No price data for {args.benchmark}")
            return 1

        bench_start = float(close.iloc[0])
        bench_end = float(close.iloc[-1])
        bench_return = ((bench_end - bench_start) / bench_start * 100) if bench_start else 0.0

        alpha = port_return - bench_return

        result = {
            "benchmark": args.benchmark,
            "period": args.period,
            "portfolio_return_pct": round(port_return, 2),
            "benchmark_return_pct": round(bench_return, 2),
            "alpha_pct": round(alpha, 2),
        }

        if args.output == "json":
            print(to_json(result))
        else:
            print(f"\nPortfolio vs {args.benchmark} ({args.period})")
            print("=" * 45)
            print(f"Portfolio Return: {port_return:>+10.2f}%")
            print(f"{args.benchmark:8} Return: {bench_return:>+10.2f}%")
            print(f"Alpha:            {alpha:>+10.2f}%")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_options(args: Namespace) -> int:
    """Handle options command."""
    import pandas as pd

    from ..core.config import load_config
    from ..market.data import get_option_chain, get_option_expiries, get_option_quote
    from ..monitors.options import OptionBuybackMonitor, format_buyback_report
    from ..output.json import to_json

    if args.options_command is None:
        print("Usage: clawdfolio options [quote|chain|expiries|buyback] ...")
        return 1

    if args.options_command == "expiries":
        expiries = get_option_expiries(args.symbol)
        if args.output == "json":
            print(to_json({"symbol": args.symbol, "expiries": expiries}))
        else:
            if not expiries:
                print(f"No option expiries found for {args.symbol}.")
            else:
                print(f"Option expiries for {args.symbol}:")
                for exp in expiries:
                    print(f"- {exp}")
        return 0

    if args.options_command == "quote":
        quote = get_option_quote(
            args.symbol,
            args.expiry,
            float(args.strike),
            option_type=args.option_type.upper(),
        )
        if quote is None:
            print(
                f"Could not fetch option quote for {args.symbol} {args.expiry} "
                f"{args.option_type.upper()}{args.strike}",
                file=sys.stderr,
            )
            return 1
        if args.output == "json":
            print(to_json(quote))
        else:
            print(f"Option quote: {args.symbol} {args.expiry} {quote.option_type}{int(quote.strike)}")
            print(f"Source: {quote.source}")
            print(f"Bid: {quote.bid}  Ask: {quote.ask}  Last: {quote.last}  Ref: {quote.ref_price}")
            print(
                "IV/Greeks: "
                f"iv={quote.implied_volatility} delta={quote.delta} gamma={quote.gamma} "
                f"theta={quote.theta} vega={quote.vega} rho={quote.rho}"
            )
            print(f"OI/Volume: oi={quote.open_interest} volume={quote.volume}")
        return 0

    if args.options_command == "chain":
        chain = get_option_chain(args.symbol, args.expiry)
        if chain is None:
            print(
                f"Could not fetch option chain for {args.symbol} {args.expiry}",
                file=sys.stderr,
            )
            return 1

        def _pick_columns(df: pd.DataFrame) -> pd.DataFrame:
            wanted = [
                "contractSymbol",
                "strike",
                "bid",
                "ask",
                "lastPrice",
                "impliedVolatility",
                "delta",
                "gamma",
                "theta",
                "vega",
                "openInterest",
                "volume",
            ]
            if df is None or df.empty:
                return pd.DataFrame(columns=wanted)
            out = df.copy()
            for col in wanted:
                if col not in out.columns:
                    out[col] = None
            out = out[wanted]
            if "strike" in out.columns:
                out = out.sort_values("strike")
            return out.head(max(int(args.limit), 1)).reset_index(drop=True)

        calls = _pick_columns(chain.calls)
        puts = _pick_columns(chain.puts)

        if args.output == "json":
            payload = {
                "symbol": args.symbol,
                "expiry": args.expiry,
                "calls": calls.to_dict(orient="records"),
                "puts": puts.to_dict(orient="records"),
            }
            if args.side == "calls":
                payload["puts"] = []
            elif args.side == "puts":
                payload["calls"] = []
            print(to_json(payload))
        else:
            print(f"Option chain: {args.symbol} {args.expiry}")
            with pd.option_context("display.max_columns", 20, "display.width", 140):
                if args.side in ("both", "calls"):
                    print("\nCalls:")
                    print(calls.to_string(index=False) if not calls.empty else "(empty)")
                if args.side in ("both", "puts"):
                    print("\nPuts:")
                    print(puts.to_string(index=False) if not puts.empty else "(empty)")
        return 0

    if args.options_command == "buyback":
        config = load_config(args.config)
        monitor = OptionBuybackMonitor(config.option_buyback)
        result = monitor.check()
        if result is None:
            print(
                "Option buyback monitor is disabled or has no targets. "
                "Set option_buyback.enabled=true and targets in config.",
                file=sys.stderr,
            )
            return 1

        if args.output == "json":
            print(to_json(result))
        else:
            print(format_buyback_report(result))

        if args.strict and not result.triggered:
            return 1
        return 0

    print(f"Unknown options subcommand: {args.options_command}", file=sys.stderr)
    return 1


def cmd_factors(args: Namespace) -> int:
    """Handle factors command — Fama-French factor exposure."""
    from ..analysis.factors import analyze_factor_exposure
    from ..market.data import get_history_multi

    try:
        portfolio = _get_portfolio(args)
        if not portfolio.positions:
            print("No positions in portfolio.")
            return 1

        tickers = [p.symbol.ticker for p in portfolio.positions]
        weights = [p.weight for p in portfolio.positions]

        prices = get_history_multi(tickers, period="1y")
        if prices.empty:
            print("Could not fetch price data.")
            return 1

        returns = prices.pct_change().dropna()
        available = [t for t in tickers if t in returns.columns]
        if not available:
            print("No matching return data.")
            return 1

        import numpy as np

        w = np.array([wt for t, wt in zip(tickers, weights, strict=False) if t in available])
        if w.sum() == 0:
            print("All weights are zero.")
            return 1
        w = w / w.sum()
        port_returns = (returns[available] * w).sum(axis=1)

        exposure = analyze_factor_exposure(port_returns, period="1y")

        if args.output == "json":
            from ..output.json import to_json
            print(to_json({
                "factor_loadings": exposure.factor_loadings,
                "t_stats": exposure.t_stats,
                "p_values": exposure.p_values,
                "r_squared": exposure.r_squared,
                "alpha_annualized": exposure.alpha_annualized,
                "alpha_t_stat": exposure.alpha_t_stat,
                "alpha_p_value": exposure.alpha_p_value,
            }))
        else:
            print("\nFama-French 3-Factor Exposure")
            print("=" * 55)
            print(f"{'Factor':<10} {'Loading':>10} {'t-stat':>10} {'p-value':>10}")
            print("-" * 55)
            for factor in ["Mkt-RF", "SMB", "HML"]:
                loading = exposure.factor_loadings.get(factor, 0.0)
                t_stat = exposure.t_stats.get(factor, 0.0)
                p_val = exposure.p_values.get(factor, 1.0)
                sig = "*" if p_val < 0.05 else ""
                print(f"{factor:<10} {loading:>10.4f} {t_stat:>10.2f} {p_val:>9.4f} {sig}")
            print("-" * 55)
            alpha_sig = "*" if exposure.alpha_p_value < 0.05 else ""
            print(
                f"{'Alpha':<10} {exposure.alpha_annualized:>9.4f}% "
                f"{exposure.alpha_t_stat:>10.2f} {exposure.alpha_p_value:>9.4f} {alpha_sig}"
            )
            print(f"\nR-squared: {exposure.r_squared:.4f}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_stress(args: Namespace) -> int:
    """Handle stress command — leverage-adjusted stress testing."""
    from ..analysis.stress import stress_test_portfolio

    try:
        portfolio = _get_portfolio(args)
        if not portfolio.positions:
            print("No positions in portfolio.")
            return 1

        results = stress_test_portfolio(portfolio)

        if args.output == "json":
            from ..output.json import to_json
            data = [
                {
                    "scenario": r.scenario,
                    "portfolio_impact": r.portfolio_impact,
                    "position_impacts": r.position_impacts,
                }
                for r in results
            ]
            print(to_json(data))
        else:
            net_assets = float(portfolio.net_assets)
            print("\nStress Test Results")
            print("=" * 60)
            for r in results:
                pct = r.portfolio_impact * 100
                loss_str = ""
                if net_assets > 0:
                    loss_str = f"  (${r.portfolio_impact * net_assets:,.0f})"
                print(f"  {r.scenario:<30} {pct:>+7.2f}%{loss_str}")

            # Show top 3 most impacted positions for worst scenario
            worst = max(results, key=lambda r: abs(r.portfolio_impact))
            print(f"\nWorst scenario: {worst.scenario}")
            sorted_impacts = sorted(
                worst.position_impacts, key=lambda x: abs(x["impact"]), reverse=True  # type: ignore[arg-type]
            )
            print("  Top impacted positions:")
            for pi in sorted_impacts[:5]:
                lev = f" ({pi['leverage']}x)" if pi["leverage"] != 1.0 else ""
                print(
                    f"    {pi['ticker']:8}{lev:8} "
                    f"wt={float(pi['weight'])*100:5.1f}%  impact={float(pi['impact'])*100:>+6.2f}%"
                )

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_greeks(args: Namespace) -> int:
    """Handle greeks command — aggregate portfolio-level Greeks."""
    try:
        portfolio = _get_portfolio(args)
        option_positions = [p for p in portfolio.positions if p.is_option]

        if not option_positions:
            print("No option positions found in portfolio.")
            return 0

        print("\nPortfolio Greeks Aggregation")
        print("=" * 60)

        for pos in option_positions:
            qty = float(pos.quantity)
            ticker = pos.symbol.ticker
            # For option positions, the greeks are per contract
            # We'd need to fetch current greeks; for now, display what we have
            print(f"  {ticker}: qty={qty:.0f}")

        # Note: Full Greeks aggregation requires live option quotes per position.
        # This is a summary placeholder that works with the current data model.
        print("\nNote: Full Greeks aggregation requires live option quote data.")
        print("Use 'clawdfolio options quote' to view Greeks for individual options.")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_finance(args: Namespace) -> int:
    """Handle finance workflow orchestration command."""
    from ..finance.runner import default_workspace_path, initialize_workspace, run_workflow
    from ..finance.workflows import CATEGORY_LABELS, grouped_workflows
    from ..output.json import to_json

    if args.finance_command is None:
        args.finance_command = "list"

    if args.finance_command == "list":
        groups = grouped_workflows(category=getattr(args, "category", None))
        if args.output == "json":
            list_payload = {
                "groups": [
                    {
                        "category": cat,
                        "label": label,
                        "workflows": [
                            {
                                "id": wf.workflow_id,
                                "name": wf.name,
                                "script": wf.script,
                                "description": wf.description,
                            }
                            for wf in items
                        ],
                    }
                    for cat, label, items in groups
                ],
                "workspace_default": str(default_workspace_path()),
            }
            print(to_json(list_payload))
            return 0

        print("Finance workflows (v2):")
        for cat, label, items in groups:
            print(f"\n[{label}] ({cat})")
            for wf in items:
                print(f"- {wf.workflow_id:30} {wf.name} [{wf.script}]")
                print(f"  {wf.description}")
        return 0

    if args.finance_command == "init":
        result = initialize_workspace(
            workspace=getattr(args, "workspace", None),
            sync=bool(getattr(args, "sync", False)),
        )
        if args.output == "json":
            init_payload = {
                "workspace": str(result.workspace),
                "scripts_synced": result.scripts_synced,
                "archive_synced": result.archive_synced,
                "config_created": result.config_created,
                "data_created": result.data_created,
                "categories": CATEGORY_LABELS,
            }
            print(to_json(init_payload))
            return 0

        print(f"Finance workspace: {result.workspace}")
        print(f"Scripts synced: {result.scripts_synced}")
        print(f"Archive scripts synced: {result.archive_synced}")
        print(f"Config created: {'yes' if result.config_created else 'no'}")
        print(f"Data dir created: {'yes' if result.data_created else 'no'}")
        return 0

    if args.finance_command == "run":
        script_args = list(getattr(args, "script_args", []) or [])
        if script_args and script_args[0] == "--":
            script_args = script_args[1:]
        try:
            return run_workflow(
                args.workflow,
                workspace=getattr(args, "workspace", None),
                sync=bool(getattr(args, "sync", False)),
                script_args=script_args,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    print(f"Unknown finance subcommand: {args.finance_command}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    from ..core.config import load_config
    from ..market.data import set_default_ttl

    parser = create_parser()
    args, extras = parser.parse_known_args(argv)

    # Apply cache_ttl from config
    config = load_config(getattr(args, "config", None))
    if config.cache_ttl:
        set_default_ttl(config.cache_ttl)

    if extras:
        if args.command == "finance" and args.finance_command == "run":
            args.script_args = extras
        else:
            parser.error(f"unrecognized arguments: {' '.join(extras)}")

    if args.command is None:
        # Default to summary
        args.command = "summary"
        args.top = 10

    commands = {
        "summary": cmd_summary,
        "quotes": cmd_quotes,
        "risk": cmd_risk,
        "alerts": cmd_alerts,
        "earnings": cmd_earnings,
        "export": cmd_export,
        "dca": cmd_dca,
        "snapshot": cmd_snapshot,
        "performance": cmd_performance,
        "compare": cmd_compare,
        "options": cmd_options,
        "factors": cmd_factors,
        "stress": cmd_stress,
        "greeks": cmd_greeks,
        "finance": cmd_finance,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
