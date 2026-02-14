"""CLI entry point for Clawdfolio."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING

from .. import __version__

if TYPE_CHECKING:
    from argparse import Namespace

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    from ..finance.workflows import category_choices

    parser = argparse.ArgumentParser(
        prog="clawdfolio",
        description="AI portfolio monitoring for Clawdbot with v2 finance workflows and production-grade reliability",
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

    # Earnings command
    earnings_parser = subparsers.add_parser("earnings", help="Show upcoming earnings")
    earnings_parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Days to look ahead (default: 14)",
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


def cmd_summary(args: Namespace) -> int:
    """Handle summary command."""
    from ..brokers import get_broker
    from ..brokers.demo import DemoBroker  # noqa: F401 - registers broker
    from ..output import print_portfolio

    broker_name = args.broker if args.broker != "all" else "demo"

    try:
        broker = get_broker(broker_name)
        broker.connect()
        portfolio = broker.get_portfolio()

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
    from ..brokers import get_broker
    from ..brokers.demo import DemoBroker  # noqa: F401
    from ..output import print_risk_metrics

    broker_name = args.broker if args.broker != "all" else "demo"

    try:
        broker = get_broker(broker_name)
        broker.connect()
        portfolio = broker.get_portfolio()
        metrics = analyze_risk(portfolio)

        if args.output == "json":
            from ..output.json import JSONFormatter
            formatter = JSONFormatter()
            print(formatter.format_risk_metrics(metrics))
        else:
            print_risk_metrics(metrics)

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_alerts(args: Namespace) -> int:
    """Handle alerts command."""
    from ..brokers import get_broker
    from ..brokers.demo import DemoBroker  # noqa: F401
    from ..monitors.earnings import EarningsMonitor
    from ..monitors.price import PriceMonitor

    broker_name = args.broker if args.broker != "all" else "demo"

    try:
        broker = get_broker(broker_name)
        broker.connect()
        portfolio = broker.get_portfolio()

        # Collect alerts
        all_alerts = []
        all_alerts.extend(PriceMonitor().check_portfolio(portfolio))
        all_alerts.extend(EarningsMonitor().check_portfolio(portfolio))

        # Filter by severity if specified
        if args.severity:
            all_alerts = [a for a in all_alerts if a.severity.value == args.severity]

        if args.output == "json":
            from ..output.json import JSONFormatter
            formatter = JSONFormatter()
            print(formatter.format_alerts(all_alerts))
        else:
            if not all_alerts:
                print("No alerts")
            else:
                for alert in all_alerts:
                    print(str(alert))
                    print()

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_earnings(args: Namespace) -> int:
    """Handle earnings command."""
    from ..brokers import get_broker
    from ..brokers.demo import DemoBroker  # noqa: F401
    from ..monitors.earnings import format_earnings_calendar, get_upcoming_earnings

    broker_name = args.broker if args.broker != "all" else "demo"

    try:
        broker = get_broker(broker_name)
        broker.connect()
        portfolio = broker.get_portfolio()
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
    parser = create_parser()
    args, extras = parser.parse_known_args(argv)

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
        "dca": cmd_dca,
        "options": cmd_options,
        "finance": cmd_finance,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
