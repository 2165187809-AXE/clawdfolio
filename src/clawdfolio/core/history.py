"""Portfolio snapshot persistence — read/write/query history.csv."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.types import Portfolio

DEFAULT_HISTORY_PATH = "~/.clawdfolio/history.csv"

COLUMNS = ["date", "net_assets", "market_value", "cash", "day_pnl", "day_pnl_pct"]


@dataclass
class SnapshotRow:
    """A single snapshot entry."""

    date: date
    net_assets: float
    market_value: float
    cash: float
    day_pnl: float
    day_pnl_pct: float


def _resolve_path(path: str | None) -> Path:
    return Path(path or DEFAULT_HISTORY_PATH).expanduser()


def append_snapshot(portfolio: Portfolio, path: str | None = None) -> tuple[bool, str]:
    """Append today's snapshot. Returns (written, message)."""
    fp = _resolve_path(path)
    today = date.today().isoformat()

    # Check idempotency
    if fp.exists():
        existing = read_snapshots(path)
        if any(row.date.isoformat() == today for row in existing):
            return False, f"Snapshot for {today} already exists, skipping."

    fp.parent.mkdir(parents=True, exist_ok=True)
    write_header = not fp.exists() or fp.stat().st_size == 0

    with open(fp, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(COLUMNS)
        writer.writerow([
            today,
            f"{float(portfolio.net_assets):.2f}",
            f"{float(portfolio.market_value):.2f}",
            f"{float(portfolio.cash):.2f}",
            f"{float(portfolio.day_pnl):.2f}",
            f"{portfolio.day_pnl_pct:.6f}",
        ])

    return True, f"Snapshot saved for {today} -> {fp}"


def read_snapshots(path: str | None = None) -> list[SnapshotRow]:
    """Read all snapshots from history.csv."""
    fp = _resolve_path(path)
    if not fp.exists():
        return []

    rows: list[SnapshotRow] = []
    with open(fp, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append(SnapshotRow(
                    date=datetime.strptime(r["date"], "%Y-%m-%d").date(),
                    net_assets=float(r["net_assets"]),
                    market_value=float(r["market_value"]),
                    cash=float(r["cash"]),
                    day_pnl=float(r["day_pnl"]),
                    day_pnl_pct=float(r["day_pnl_pct"]),
                ))
            except (KeyError, ValueError):
                continue
    return rows


def filter_by_period(
    rows: list[SnapshotRow], period: str = "all"
) -> list[SnapshotRow]:
    """Filter snapshots by period string (1m, 3m, 6m, 1y, all)."""
    if not rows or period == "all":
        return rows

    from datetime import timedelta

    today = date.today()
    mapping = {"1m": 30, "3m": 91, "6m": 182, "1y": 365}
    days = mapping.get(period)
    if days is None:
        return rows

    cutoff = today - timedelta(days=days)
    return [r for r in rows if r.date >= cutoff]


def compute_performance(rows: list[SnapshotRow]) -> dict:
    """Compute performance stats from snapshot rows."""
    if not rows:
        return {"error": "No snapshot data available."}

    sorted_rows = sorted(rows, key=lambda r: r.date)
    start_nav = sorted_rows[0].net_assets
    end_nav = sorted_rows[-1].net_assets

    total_return_pct = ((end_nav - start_nav) / start_nav * 100) if start_nav else 0.0

    # Max drawdown
    peak = sorted_rows[0].net_assets
    max_dd = 0.0
    best_day = sorted_rows[0]
    worst_day = sorted_rows[0]

    for r in sorted_rows:
        if r.net_assets > peak:
            peak = r.net_assets
        dd = (r.net_assets - peak) / peak if peak else 0.0
        if dd < max_dd:
            max_dd = dd
        if r.day_pnl_pct > best_day.day_pnl_pct:
            best_day = r
        if r.day_pnl_pct < worst_day.day_pnl_pct:
            worst_day = r

    return {
        "start_date": sorted_rows[0].date.isoformat(),
        "end_date": sorted_rows[-1].date.isoformat(),
        "start_nav": start_nav,
        "end_nav": end_nav,
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "best_day": {"date": best_day.date.isoformat(), "pnl_pct": round(best_day.day_pnl_pct * 100, 2)},
        "worst_day": {"date": worst_day.date.isoformat(), "pnl_pct": round(worst_day.day_pnl_pct * 100, 2)},
        "data_points": len(sorted_rows),
        "time_series": [
            {"date": r.date.isoformat(), "nav": r.net_assets} for r in sorted_rows
        ],
    }


def format_performance_table(perf: dict) -> str:
    """Format performance dict as a human-readable table."""
    if "error" in perf:
        return str(perf["error"])

    lines = [
        "Portfolio Performance",
        "=" * 45,
        f"Period:        {perf['start_date']} to {perf['end_date']}",
        f"Start NAV:     ${perf['start_nav']:>14,.2f}",
        f"End NAV:       ${perf['end_nav']:>14,.2f}",
        f"Total Return:  {perf['total_return_pct']:>+13.2f}%",
        f"Max Drawdown:  {perf['max_drawdown_pct']:>13.2f}%",
        f"Best Day:      {perf['best_day']['date']}  {perf['best_day']['pnl_pct']:+.2f}%",
        f"Worst Day:     {perf['worst_day']['date']}  {perf['worst_day']['pnl_pct']:+.2f}%",
        f"Data Points:   {perf['data_points']}",
    ]
    return "\n".join(lines)
