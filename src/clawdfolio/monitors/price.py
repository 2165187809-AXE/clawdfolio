"""Price movement monitoring and alerts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.types import Alert, AlertSeverity, AlertType

if TYPE_CHECKING:
    from ..core.config import Config
    from ..core.types import Portfolio


DEFAULT_STATE_PATH = "~/.cache/clawdfolio/price_alert_state.json"


@dataclass
class PriceAlert:
    """Price alert result."""
    ticker: str
    price_change_pct: float
    weight: float
    is_gain: bool
    threshold: float
    rank: int


@dataclass
class PriceMonitor:
    """Monitor for price movement alerts.

    Supports step-based deduplication: an alert fires when a threshold is
    first crossed, then only fires again when the value crosses the next
    step boundary (e.g. every additional ``move_step`` of change, or
    every additional ``pnl_step`` of dollar P&L).
    """

    # Thresholds
    top10_threshold: float = 0.05  # 5% for top 10
    other_threshold: float = 0.10  # 10% for others
    pnl_trigger: float = 500.0  # Absolute P&L trigger

    # Step sizes for deduplication
    move_step: float = 0.01  # 1% step for price moves
    pnl_step: float = 500.0  # $500 step for P&L
    rsi_step: int = 2  # RSI step (not used here, kept for config parity)

    # Leveraged ETF mappings: ticker -> (underlying, leverage, label)
    leveraged_etfs: dict[str, tuple[str, int, str]] = field(default_factory=dict)

    # State file path for deduplication
    state_path: str = DEFAULT_STATE_PATH

    # In-memory state (loaded from/saved to state_path)
    _state: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_config(cls, config: Config) -> PriceMonitor:
        """Create monitor from config."""
        return cls(
            top10_threshold=config.alerts.single_stock_threshold_top10,
            other_threshold=config.alerts.single_stock_threshold_other,
            pnl_trigger=config.alerts.pnl_trigger,
            move_step=config.alerts.move_step,
            pnl_step=config.alerts.pnl_step,
            rsi_step=config.alerts.rsi_step,
            leveraged_etfs=config.leveraged_etfs,
        )

    def _load_state(self) -> dict[str, Any]:
        """Load deduplication state from disk."""
        path = Path(self.state_path).expanduser()
        if path.exists():
            try:
                result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
                return result
            except Exception:
                return {}
        return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save deduplication state to disk."""
        path = Path(self.state_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _should_alert_price(self, ticker: str, day_pct: float, threshold: float) -> bool:
        """Check if a price alert should fire based on step deduplication.

        Fires on first threshold crossing, then only when crossing the
        next ``move_step`` boundary.
        """
        if self.move_step <= 0:
            return True

        key = f"price:{ticker}"
        last_step = self._state.get(key)

        # Current step number (how many steps above threshold)
        steps_above = math.floor((abs(day_pct) - threshold) / self.move_step)
        current_step = max(0, steps_above)

        if last_step is None:
            # First time crossing threshold
            self._state[key] = current_step
            return True

        if current_step > last_step:
            # Crossed a new step boundary
            self._state[key] = current_step
            return True

        return False

    def _should_alert_pnl(self, pnl: float) -> bool:
        """Check if a P&L alert should fire based on step deduplication."""
        if self.pnl_step <= 0:
            return True

        key = "pnl:portfolio"
        last_step = self._state.get(key)

        current_step = math.floor(abs(pnl) / self.pnl_step)

        if last_step is None:
            self._state[key] = current_step
            return True

        if current_step > last_step:
            self._state[key] = current_step
            return True

        return False

    def _effective_threshold(self, ticker: str, base_threshold: float) -> float:
        """Get effective alert threshold, adjusting for leveraged ETFs.

        For a 3x leveraged ETF with a 5% threshold, the effective
        threshold becomes 5% * 3 = 15% (the ETF is expected to move 3x
        as much as the underlying).
        """
        if ticker in self.leveraged_etfs:
            _underlying, leverage, _label = self.leveraged_etfs[ticker]
            return base_threshold * abs(leverage)
        return base_threshold

    def check_portfolio(self, portfolio: Portfolio) -> list[Alert]:
        """Check portfolio for price alerts.

        Uses step-based deduplication: alerts only fire when crossing a
        new step boundary rather than every time the monitor runs.

        Args:
            portfolio: Portfolio to check

        Returns:
            List of triggered alerts
        """
        self._state = self._load_state()
        alerts: list[Alert] = []

        # Sort positions by weight
        sorted_positions = portfolio.sorted_by_weight

        for i, pos in enumerate(sorted_positions, start=1):
            base_threshold = self.top10_threshold if i <= 10 else self.other_threshold
            threshold = self._effective_threshold(pos.symbol.ticker, base_threshold)
            day_pct = pos.day_pnl_pct

            if abs(day_pct) >= threshold:
                if not self._should_alert_price(pos.symbol.ticker, day_pct, threshold):
                    continue

                severity = AlertSeverity.WARNING
                if abs(day_pct) >= threshold * 2:
                    severity = AlertSeverity.CRITICAL

                direction = "up" if day_pct > 0 else "down"
                etf_note = ""
                if pos.symbol.ticker in self.leveraged_etfs:
                    _u, lev, label = self.leveraged_etfs[pos.symbol.ticker]
                    etf_note = f" ({lev}x {label})"

                alerts.append(Alert(
                    type=AlertType.PRICE_MOVE,
                    severity=severity,
                    title=f"{pos.symbol.ticker}{etf_note} {direction} {abs(day_pct)*100:.1f}%",
                    message=self._format_price_message(pos, i),
                    ticker=pos.symbol.ticker,
                    value=day_pct,
                    threshold=threshold,
                    metadata={"rank": i, "weight": pos.weight},
                ))
            else:
                # Below threshold — clear any saved state so it can re-fire
                key = f"price:{pos.symbol.ticker}"
                self._state.pop(key, None)

        # Check total P&L
        pnl_val = float(portfolio.day_pnl)
        if abs(pnl_val) >= self.pnl_trigger:
            if self._should_alert_pnl(pnl_val):
                is_gain = portfolio.day_pnl > 0
                severity = AlertSeverity.WARNING
                if abs(pnl_val) >= self.pnl_trigger * 2:
                    severity = AlertSeverity.CRITICAL

                alerts.append(Alert(
                    type=AlertType.PNL_THRESHOLD,
                    severity=severity,
                    title=f"Portfolio {'gained' if is_gain else 'lost'} ${abs(portfolio.day_pnl):,.0f} today",
                    message=self._format_pnl_message(portfolio, is_gain),
                    value=pnl_val,
                    threshold=self.pnl_trigger,
                ))
        else:
            # Below trigger — clear saved state
            self._state.pop("pnl:portfolio", None)

        self._save_state(self._state)
        return alerts

    def _format_price_message(self, pos: Any, rank: int) -> str:
        """Format price alert message."""
        direction = "up" if pos.day_pnl_pct > 0 else "down"
        return (
            f"{pos.symbol.ticker} (rank #{rank}, {pos.weight*100:.1f}% of portfolio) "
            f"is {direction} {abs(pos.day_pnl_pct)*100:.1f}% today. "
            f"Day P&L: ${float(pos.day_pnl):,.2f}"
        )

    def _format_pnl_message(self, portfolio: Portfolio, is_gain: bool) -> str:
        """Format P&L alert message."""
        # Get top contributors
        sorted_pos = sorted(
            portfolio.positions,
            key=lambda p: abs(float(p.day_pnl)),
            reverse=True
        )[:3]

        contributors = []
        for p in sorted_pos:
            direction = "+" if p.day_pnl > 0 else ""
            contributors.append(f"{p.symbol.ticker}: {direction}${float(p.day_pnl):,.0f}")

        return (
            f"Total day P&L: {'+'if is_gain else '-'}${abs(portfolio.day_pnl):,.2f} "
            f"({portfolio.day_pnl_pct*100:+.2f}%)\n"
            f"Top contributors: {', '.join(contributors)}"
        )


def detect_price_alerts(
    portfolio: Portfolio,
    top10_threshold: float = 0.05,
    other_threshold: float = 0.10,
) -> list[PriceAlert]:
    """Quick function to detect price alerts.

    Args:
        portfolio: Portfolio to check
        top10_threshold: Threshold for top 10 positions
        other_threshold: Threshold for other positions

    Returns:
        List of price alerts
    """
    alerts = []
    sorted_positions = portfolio.sorted_by_weight

    for i, pos in enumerate(sorted_positions, start=1):
        threshold = top10_threshold if i <= 10 else other_threshold
        day_pct = pos.day_pnl_pct

        if abs(day_pct) >= threshold:
            alerts.append(PriceAlert(
                ticker=pos.symbol.ticker,
                price_change_pct=day_pct,
                weight=pos.weight,
                is_gain=day_pct > 0,
                threshold=threshold,
                rank=i,
            ))

    return alerts


def detect_gap(
    prev_close: float,
    open_price: float,
    threshold: float = 0.02,
) -> tuple[bool, float]:
    """Detect gap up/down at market open.

    Args:
        prev_close: Previous close price
        open_price: Today's open price
        threshold: Gap threshold (default 2%)

    Returns:
        Tuple of (is_gap, gap_percentage)
    """
    if prev_close <= 0:
        return False, 0.0

    gap_pct = (open_price - prev_close) / prev_close
    is_gap = abs(gap_pct) >= threshold

    return is_gap, gap_pct
