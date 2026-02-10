"""Unified formatting functions for all portfolio scripts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


def fmt_money(x: float, decimals: int = 0) -> str:
    """Format dollar amount: $1,234 or $1,234.56"""
    import math
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "$N/A"
    if decimals == 0:
        return f"${int(round(x)):,}"
    return f"${x:,.{decimals}f}"


def fmt_pct(x: float, decimals: int = 1) -> str:
    """Format percentage from ratio: 0.015 -> '1.5%'"""
    return f"{x * 100:.{decimals}f}%"


def fmt_arrow(x: float) -> str:
    """Return directional arrow: '▲1.5%' or '▼0.3%'"""
    if abs(x) < 1e-9:
        return "▲0.0%"
    sign = "▲" if x > 0 else "▼"
    return f"{sign}{abs(x) * 100:.1f}%"


def fmt_change(x: float, pct: Optional[float] = None) -> str:
    """Format price change: '▲$123 (+1.5%)' or '▼$45 (-0.3%)'"""
    sign = "▲" if x >= 0 else "▼"
    s = f"{sign}{fmt_money(abs(x))}"
    if pct is not None:
        ps = f"+{pct * 100:.1f}%" if pct >= 0 else f"{pct * 100:.1f}%"
        s += f" ({ps})"
    return s


def fmt_time(dt: Optional[datetime] = None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime consistently."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def fmt_ticker(sym: str) -> str:
    """Normalize ticker: strip .US / US. prefixes/suffixes."""
    s = sym.strip()
    if s.endswith(".US"):
        s = s[:-3]
    if s.startswith("US."):
        s = s[3:]
    return s


def arrow_sign(x: float) -> str:
    """Just the arrow character."""
    if abs(x) < 1e-9:
        return "▲"
    return "▲" if x > 0 else "▼"


def signed_money(x: float) -> str:
    """▲$123 or ▼$45"""
    return f"{arrow_sign(x)}{fmt_money(abs(x))}"


def signed_pct(x: float, decimals: int = 1) -> str:
    """▲1.5% or ▼0.3%"""
    r = round(abs(x) * 100, decimals)
    s = "▲" if x >= 0 else "▼"
    if r == 0.0:
        s = "▲"
    return f"{s}{r:.{decimals}f}%"


def clamp_line(s: str, max_cols: int = 88) -> str:
    """Truncate line with ellipsis if too long."""
    return s if len(s) <= max_cols else s[: max_cols - 1] + "\u2026"


def clamp_lines(lines: list[str], max_lines: int = 22) -> list[str]:
    """Truncate line list, appending overflow notice."""
    if len(lines) <= max_lines:
        return lines
    overflow = len(lines) - max_lines + 1
    return lines[: max_lines - 1] + [f"\u2026 ({overflow} more)"]


def yf_sym(t: str) -> str:
    """Convert ticker to yfinance symbol (BRK.B -> BRK-B)."""
    return fmt_ticker(t).replace(".", "-")
