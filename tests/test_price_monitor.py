"""Tests for PriceMonitor deduplication, step logic, and leveraged ETFs."""

from decimal import Decimal

from clawdfolio.core.types import AlertType, Exchange, Portfolio, Position, Symbol
from clawdfolio.monitors.price import PriceMonitor


def _portfolio_with_move(ticker, day_pnl_pct, day_pnl=Decimal("500")):
    """Create a single-position portfolio with a specific day change %."""
    pos = Position(
        symbol=Symbol(ticker=ticker, exchange=Exchange.NYSE),
        quantity=Decimal("100"),
        avg_cost=Decimal("150"),
        market_value=Decimal("17500"),
        day_pnl=day_pnl,
        day_pnl_pct=day_pnl_pct,
        current_price=Decimal("175"),
        source="test",
    )
    return Portfolio(
        positions=[pos],
        cash=Decimal("5000"),
        net_assets=Decimal("22500"),
        market_value=Decimal("17500"),
        buying_power=Decimal("5000"),
        day_pnl=day_pnl,
        day_pnl_pct=float(day_pnl / Decimal("22500")),
        currency="USD",
        source="test",
    )


class TestStepDeduplication:
    """Tests for step-based alert deduplication."""

    def test_first_alert_fires(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
        )
        portfolio = _portfolio_with_move("AAPL", 0.06, Decimal("100"))
        alerts = monitor.check_portfolio(portfolio)
        assert len(alerts) == 1
        assert alerts[0].type == AlertType.PRICE_MOVE

    def test_same_step_no_repeat(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
        )
        portfolio = _portfolio_with_move("AAPL", 0.06, Decimal("100"))

        # First call fires
        alerts1 = monitor.check_portfolio(portfolio)
        assert len(alerts1) == 1

        # Second call at same level does NOT fire
        alerts2 = monitor.check_portfolio(portfolio)
        assert len(alerts2) == 0

    def test_next_step_fires(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
        )

        # First: 6% -> fires
        p1 = _portfolio_with_move("AAPL", 0.06, Decimal("100"))
        monitor.check_portfolio(p1)

        # Second: 8% -> crosses next step -> fires
        p2 = _portfolio_with_move("AAPL", 0.08, Decimal("100"))
        alerts = monitor.check_portfolio(p2)
        assert len(alerts) == 1

    def test_drop_below_threshold_resets(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
        )

        # Fire once
        p1 = _portfolio_with_move("AAPL", 0.06, Decimal("100"))
        monitor.check_portfolio(p1)

        # Drop below threshold
        p2 = _portfolio_with_move("AAPL", 0.02, Decimal("100"))
        monitor.check_portfolio(p2)

        # Back above threshold -> should fire again
        p3 = _portfolio_with_move("AAPL", 0.06, Decimal("100"))
        alerts = monitor.check_portfolio(p3)
        assert len(alerts) == 1

    def test_pnl_step_dedup(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.99,
            pnl_trigger=500,
            pnl_step=500,
            state_path=state_file,
        )

        p1 = _portfolio_with_move("AAPL", 0.01, Decimal("600"))
        alerts1 = monitor.check_portfolio(p1)
        pnl_alerts1 = [a for a in alerts1 if a.type == AlertType.PNL_THRESHOLD]
        assert len(pnl_alerts1) == 1

        # Same PNL level -> no repeat
        alerts2 = monitor.check_portfolio(p1)
        pnl_alerts2 = [a for a in alerts2 if a.type == AlertType.PNL_THRESHOLD]
        assert len(pnl_alerts2) == 0

        # Higher PNL crosses next step
        p2 = _portfolio_with_move("AAPL", 0.01, Decimal("1100"))
        alerts3 = monitor.check_portfolio(p2)
        pnl_alerts3 = [a for a in alerts3 if a.type == AlertType.PNL_THRESHOLD]
        assert len(pnl_alerts3) == 1


class TestLeveragedETFThresholds:
    """Tests for leveraged ETF threshold adjustment."""

    def test_leveraged_etf_wider_threshold(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
            leveraged_etfs={"TQQQ": ("QQQ", 3, "Nasdaq 100")},
        )
        # TQQQ with 10% move: threshold is 5% * 3 = 15%, so 10% should NOT alert
        portfolio = _portfolio_with_move("TQQQ", 0.10, Decimal("100"))
        alerts = monitor.check_portfolio(portfolio)
        assert len(alerts) == 0

    def test_leveraged_etf_exceeds_threshold(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
            leveraged_etfs={"TQQQ": ("QQQ", 3, "Nasdaq 100")},
        )
        # TQQQ with 16% move: threshold is 15%, should alert
        portfolio = _portfolio_with_move("TQQQ", 0.16, Decimal("100"))
        alerts = monitor.check_portfolio(portfolio)
        assert len(alerts) == 1
        assert "(3x Nasdaq 100)" in alerts[0].title

    def test_non_leveraged_normal_threshold(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
            leveraged_etfs={"TQQQ": ("QQQ", 3, "Nasdaq 100")},
        )
        # AAPL with 6% move: normal 5% threshold, should alert
        portfolio = _portfolio_with_move("AAPL", 0.06, Decimal("100"))
        alerts = monitor.check_portfolio(portfolio)
        assert len(alerts) == 1


class TestStateFilePersistence:
    """Tests for state file read/write."""

    def test_state_persists_across_instances(self, tmp_path):
        state_file = str(tmp_path / "state.json")

        # First monitor fires alert
        m1 = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
        )
        p = _portfolio_with_move("AAPL", 0.06, Decimal("100"))
        m1.check_portfolio(p)

        # New monitor instance, same state file -> should NOT fire
        m2 = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=state_file,
        )
        alerts = m2.check_portfolio(p)
        assert len(alerts) == 0

    def test_corrupted_state_file_handled(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text("NOT VALID JSON")

        monitor = PriceMonitor(
            top10_threshold=0.05,
            move_step=0.01,
            pnl_trigger=99999,
            state_path=str(state_file),
        )
        p = _portfolio_with_move("AAPL", 0.06, Decimal("100"))
        # Should not crash, treats as empty state
        alerts = monitor.check_portfolio(p)
        assert len(alerts) == 1
