#!/usr/bin/env python3
"""Basic usage example for Clawdfolio."""

from clawdfolio import load_config
from clawdfolio.brokers import get_broker
from clawdfolio.brokers.demo import DemoBroker  # noqa: F401 - registers broker
from clawdfolio.analysis import analyze_risk, calculate_concentration
from clawdfolio.monitors import PriceMonitor, EarningsMonitor
from clawdfolio.output import print_portfolio, print_risk_metrics


def main():
    # Load configuration (uses default if no config file found)
    config = load_config()
    print(f"Loaded config with currency: {config.currency}")
    print()

    # Connect to demo broker (replace with "longport" or "futu" for real data)
    with get_broker("demo") as broker:
        # Get portfolio
        portfolio = broker.get_portfolio()

        # Print portfolio summary
        print("=" * 60)
        print("PORTFOLIO SUMMARY")
        print("=" * 60)
        print_portfolio(portfolio)
        print()

        # Calculate and display risk metrics
        print("=" * 60)
        print("RISK METRICS")
        print("=" * 60)
        metrics = analyze_risk(portfolio)
        print_risk_metrics(metrics)
        print()

        # Check concentration
        print("=" * 60)
        print("CONCENTRATION ANALYSIS")
        print("=" * 60)
        conc = calculate_concentration(portfolio)
        print(f"HHI Index: {conc.hhi:.4f}")
        print(f"Top 5 Weight: {conc.top_5_weight*100:.1f}%")
        print(f"Max Position: {conc.max_position_ticker} at {conc.max_position_weight*100:.1f}%")
        print(f"Is Concentrated: {conc.is_concentrated}")
        print()

        # Check for alerts
        print("=" * 60)
        print("ALERTS")
        print("=" * 60)
        price_monitor = PriceMonitor.from_config(config)
        earnings_monitor = EarningsMonitor()

        alerts = []
        alerts.extend(price_monitor.check_portfolio(portfolio))
        alerts.extend(earnings_monitor.check_portfolio(portfolio))

        if alerts:
            for alert in alerts:
                print(str(alert))
                print()
        else:
            print("No alerts at this time.")
        print()

        # Display top holdings
        print("=" * 60)
        print("TOP HOLDINGS")
        print("=" * 60)
        for i, pos in enumerate(portfolio.top_holdings[:5], 1):
            pnl_sign = "+" if pos.day_pnl > 0 else ""
            print(
                f"{i}. {pos.symbol.ticker:6} | "
                f"Weight: {pos.weight*100:5.1f}% | "
                f"Day P&L: {pnl_sign}${float(pos.day_pnl):,.0f}"
            )


if __name__ == "__main__":
    main()
