"""Option buyback monitoring."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from ..core.config import OptionBuybackConfig, OptionBuybackTargetConfig
from ..market.data import get_option_quote

_fcntl: Any
try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    _fcntl = None


@dataclass
class OptionContractSnapshot:
    """Live snapshot for one option contract."""

    expiry: str
    strike: float
    option_type: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    ref: float | None = None
    source: str = ""


@dataclass
class OptionBuybackHit:
    """Triggered buyback target."""

    name: str
    expiry: str
    strike: float
    option_type: str
    trigger_price: float
    qty: int
    ref_price: float
    source: str = ""


@dataclass
class OptionBuybackResult:
    """Result of one buyback monitor pass."""

    symbol: str
    checked_at: int
    snapshots: list[OptionContractSnapshot] = field(default_factory=list)
    triggered: list[OptionBuybackHit] = field(default_factory=list)


@contextmanager
def _locked_file(path: Path) -> Iterator[TextIO]:
    """Open a file with exclusive lock where available."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as f:
        if _fcntl is not None:
            _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
        try:
            yield f
        finally:
            if _fcntl is not None:
                _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)


def _load_state(path: Path) -> dict:
    with _locked_file(path) as f:
        f.seek(0)
        raw = f.read().strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def _save_state(path: Path, state: dict) -> None:
    with _locked_file(path) as f:
        f.seek(0)
        f.truncate()
        f.write(json.dumps(state, ensure_ascii=False))
        f.flush()


def _contract_key(target: OptionBuybackTargetConfig) -> tuple[str, float, str]:
    return target.expiry, float(target.strike), target.option_type.upper()


def _snapshot_from_quote(target: OptionBuybackTargetConfig, quote: Any) -> OptionContractSnapshot:
    if quote is None:
        return OptionContractSnapshot(
            expiry=target.expiry,
            strike=float(target.strike),
            option_type=target.option_type.upper(),
            source="unavailable",
        )
    return OptionContractSnapshot(
        expiry=target.expiry,
        strike=float(target.strike),
        option_type=target.option_type.upper(),
        bid=quote.bid,
        ask=quote.ask,
        last=quote.last,
        ref=quote.ref_price,
        source=quote.source,
    )


class OptionBuybackMonitor:
    """Stateful option buyback trigger monitor."""

    def __init__(self, config: OptionBuybackConfig):
        self.config = config
        self.state_path = Path(config.state_path).expanduser()

    def check(self) -> OptionBuybackResult | None:
        """Evaluate buyback targets and update durable state."""
        targets = self.config.targets
        if not self.config.enabled or not targets:
            return None

        checked_at = int(time.time())
        symbol = self.config.symbol

        snapshots: dict[tuple[str, float, str], OptionContractSnapshot] = {}
        for target in targets:
            key = _contract_key(target)
            if key in snapshots:
                continue
            quote = get_option_quote(
                symbol,
                target.expiry,
                float(target.strike),
                target.option_type.upper(),
            )
            snapshots[key] = _snapshot_from_quote(target, quote)

        state = _load_state(self.state_path)
        done = state.setdefault("done", {})

        # Auto-reset target when option ref price rises above trigger * (1 + reset_pct).
        for target in targets:
            if target.name not in done:
                continue
            snap = snapshots[_contract_key(target)]
            if snap.ref is None:
                continue
            reset_threshold = float(target.trigger_price) * (1 + float(target.reset_pct))
            if snap.ref > reset_threshold:
                done.pop(target.name, None)

        hits: list[OptionBuybackHit] = []
        for target in targets:
            if done.get(target.name):
                continue
            snap = snapshots[_contract_key(target)]
            if snap.ref is None:
                continue
            if snap.ref <= float(target.trigger_price):
                hit = OptionBuybackHit(
                    name=target.name,
                    expiry=target.expiry,
                    strike=float(target.strike),
                    option_type=target.option_type.upper(),
                    trigger_price=float(target.trigger_price),
                    qty=int(target.qty),
                    ref_price=float(snap.ref),
                    source=snap.source,
                )
                hits.append(hit)
                done[target.name] = {
                    "alertedAt": checked_at,
                    "trigger": hit.trigger_price,
                    "qty": hit.qty,
                    "ref": hit.ref_price,
                    "expiry": hit.expiry,
                    "strike": hit.strike,
                    "type": hit.option_type,
                }

        state["last_quotes"] = {
            f"{exp}|{strike}|{opt}": {
                "ts": checked_at,
                "bid": snap.bid,
                "ask": snap.ask,
                "last": snap.last,
                "ref": snap.ref,
                "source": snap.source,
            }
            for (exp, strike, opt), snap in snapshots.items()
        }
        _save_state(self.state_path, state)

        ordered_snapshots = [
            snapshots[k]
            for k in sorted(
                snapshots,
                key=lambda item: (item[0], item[2], item[1]),
            )
        ]
        return OptionBuybackResult(
            symbol=symbol,
            checked_at=checked_at,
            snapshots=ordered_snapshots,
            triggered=hits,
        )


def format_buyback_report(result: OptionBuybackResult) -> str:
    """Format buyback monitor output for terminal."""
    lines = [f"Option buyback check | {result.symbol} | ts={result.checked_at}", ""]
    for snap in result.snapshots:
        contract = f"{result.symbol} {snap.expiry} {snap.option_type}{int(snap.strike)}"
        lines.append(
            f"{contract} | bid={snap.bid} ask={snap.ask} last={snap.last} "
            f"ref={snap.ref} src={snap.source}"
        )
    if not result.triggered:
        lines.extend(["", "No targets triggered."])
        return "\n".join(lines)

    lines.extend(["", "Triggered targets:"])
    for hit in result.triggered:
        lines.append(
            f"- {hit.name}: ref={hit.ref_price:.2f} <= trigger={hit.trigger_price:.2f}, qty={hit.qty}"
        )
    return "\n".join(lines)
