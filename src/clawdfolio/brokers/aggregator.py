"""Multi-broker aggregator for combining portfolios from multiple brokers."""

from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ..core.exceptions import BrokerError
from ..core.types import Portfolio, Position

if TYPE_CHECKING:
    from .base import BaseBroker


def aggregate_portfolios(brokers: list[BaseBroker]) -> Portfolio:
    """Fetch and merge portfolios from multiple brokers.

    Positions with the same ticker are combined (quantity, market_value,
    day_pnl summed; avg_cost weighted-averaged). Brokers that fail to
    connect are skipped with a warning.

    Args:
        brokers: List of broker instances to aggregate.

    Returns:
        Merged Portfolio.

    Raises:
        BrokerError: If no broker succeeds.
    """
    all_positions: list[Position] = []
    total_cash = Decimal("0")
    total_net = Decimal("0")
    total_mv = Decimal("0")
    total_buying = Decimal("0")
    total_day_pnl = Decimal("0")
    sources: list[str] = []
    succeeded = 0

    for broker in brokers:
        try:
            if not broker.is_connected():
                broker.connect()
            port = broker.get_portfolio()
            all_positions.extend(port.positions)
            total_cash += port.cash
            total_net += port.net_assets
            total_mv += port.market_value
            total_buying += port.buying_power
            total_day_pnl += port.day_pnl
            sources.append(port.source)
            succeeded += 1
        except Exception as exc:
            print(f"Warning: {broker.name} failed: {exc}", file=sys.stderr)

    if succeeded == 0:
        raise BrokerError("all", "No broker returned data")

    # Merge positions with same ticker
    merged = _merge_positions(all_positions)

    day_pnl_pct = float(total_day_pnl / total_net) if total_net > 0 else 0.0

    return Portfolio(
        positions=merged,
        cash=total_cash,
        net_assets=total_net,
        market_value=total_mv,
        buying_power=total_buying,
        day_pnl=total_day_pnl,
        day_pnl_pct=day_pnl_pct,
        currency="USD",
        source="+".join(sources),
        timestamp=datetime.now(),
    )


def _merge_positions(positions: list[Position]) -> list[Position]:
    """Merge positions with the same ticker.

    For duplicate tickers: sum quantity/market_value/day_pnl,
    weighted-average avg_cost, take latest current_price.
    """
    by_ticker: dict[str, list[Position]] = {}
    for pos in positions:
        by_ticker.setdefault(pos.symbol.ticker, []).append(pos)

    merged: list[Position] = []
    for _ticker, group in by_ticker.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        # Combine
        base = group[0]
        total_qty = sum((p.quantity for p in group), Decimal("0"))
        total_mv = sum((p.market_value for p in group), Decimal("0"))
        total_day_pnl = sum((p.day_pnl for p in group), Decimal("0"))
        total_unrealized = sum((p.unrealized_pnl for p in group), Decimal("0"))

        # Weighted average cost
        cost_sum = Decimal("0")
        qty_sum = Decimal("0")
        for p in group:
            if p.avg_cost and p.quantity > 0:
                cost_sum += p.avg_cost * p.quantity
                qty_sum += p.quantity
        avg_cost = (cost_sum / qty_sum) if qty_sum > 0 else base.avg_cost

        # Use whichever has a current_price
        current_price = None
        prev_close = None
        for p in group:
            if p.current_price is not None:
                current_price = p.current_price
                prev_close = p.prev_close
                break

        unrealized_pct = 0.0
        if avg_cost and avg_cost > 0 and current_price:
            unrealized_pct = float((current_price - avg_cost) / avg_cost)

        day_pnl_pct = 0.0
        if total_mv > 0 and total_day_pnl != 0:
            start_val = total_mv - total_day_pnl
            if start_val > 0:
                day_pnl_pct = float(total_day_pnl / start_val)

        merged.append(Position(
            symbol=base.symbol,
            quantity=total_qty,
            avg_cost=avg_cost,
            market_value=total_mv,
            unrealized_pnl=total_unrealized,
            unrealized_pnl_pct=unrealized_pct,
            day_pnl=total_day_pnl,
            day_pnl_pct=day_pnl_pct,
            current_price=current_price,
            prev_close=prev_close,
            name=base.name,
            source="+".join(p.source for p in group),
        ))

    return merged
