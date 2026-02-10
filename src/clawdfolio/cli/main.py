"""CLI entry point for Clawdfolio."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="clawdfolio",
        description="AI portfolio monitoring for Claude Code with production-grade data reliability",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.2",
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


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

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
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
