"""Configuration management for Clawdfolio."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigError


@dataclass
class AlertConfig:
    """Alert thresholds configuration."""

    pnl_trigger: float = 500.0
    pnl_step: float = 500.0
    rsi_high: int = 80
    rsi_low: int = 20
    rsi_step: int = 2
    single_stock_threshold_top10: float = 0.05
    single_stock_threshold_other: float = 0.10
    move_step: float = 0.01
    concentration_threshold: float = 0.25


@dataclass
class BrokerConfig:
    """Broker-specific configuration."""

    enabled: bool = True
    env_prefix: str = ""
    timeout: int = 30
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptionBuybackTargetConfig:
    """Single option buyback target."""

    name: str
    strike: float
    expiry: str
    option_type: str = "C"
    trigger_price: float = 0.0
    qty: int = 1
    reset_pct: float = 0.20


@dataclass
class OptionBuybackConfig:
    """Option buyback monitor configuration."""

    enabled: bool = False
    symbol: str = "TQQQ"
    targets: list[OptionBuybackTargetConfig] = field(default_factory=list)
    state_path: str = "~/.cache/clawdfolio/option_buyback_state.json"


@dataclass
class Config:
    """Main configuration for Portfolio Monitor."""

    # Broker configs
    brokers: dict[str, BrokerConfig] = field(default_factory=dict)

    # Alert settings
    alerts: AlertConfig = field(default_factory=AlertConfig)

    # General settings
    currency: str = "USD"
    timezone: str = "America/New_York"
    cache_ttl: int = 300  # 5 minutes

    # Leveraged ETF mappings for smart alerts
    leveraged_etfs: dict[str, tuple[str, int, str]] = field(default_factory=dict)

    # Option buyback monitor settings
    option_buyback: OptionBuybackConfig = field(default_factory=OptionBuybackConfig)

    # Output settings
    output_format: str = "console"  # console, json
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Create Config from dictionary."""
        brokers = {}
        for name, cfg in data.get("brokers", {}).items():
            brokers[name] = BrokerConfig(
                enabled=cfg.get("enabled", True),
                env_prefix=cfg.get("env_prefix", ""),
                timeout=cfg.get("timeout", 30),
                extra=cfg.get("extra", {}),
            )

        alerts_data = data.get("alerts", {})
        alerts = AlertConfig(
            pnl_trigger=alerts_data.get("pnl_trigger", 500.0),
            pnl_step=alerts_data.get("pnl_step", 500.0),
            rsi_high=alerts_data.get("rsi_high", 80),
            rsi_low=alerts_data.get("rsi_low", 20),
            rsi_step=alerts_data.get("rsi_step", 2),
            single_stock_threshold_top10=alerts_data.get(
                "single_stock_threshold_top10", 0.05
            ),
            single_stock_threshold_other=alerts_data.get(
                "single_stock_threshold_other", 0.10
            ),
            move_step=alerts_data.get("move_step", 0.01),
            concentration_threshold=alerts_data.get("concentration_threshold", 0.25),
        )

        leveraged = data.get("leveraged_etfs", {})
        leveraged_etfs = {}
        for etf, info in leveraged.items():
            if isinstance(info, list) and len(info) >= 3:
                leveraged_etfs[etf] = (info[0], info[1], info[2])

        option_buyback_data = data.get("option_buyback", {})
        option_buyback_targets: list[OptionBuybackTargetConfig] = []
        for item in option_buyback_data.get("targets", []):
            if not isinstance(item, dict):
                continue
            option_buyback_targets.append(
                OptionBuybackTargetConfig(
                    name=str(item.get("name", f"target_{len(option_buyback_targets) + 1}")),
                    strike=float(item.get("strike", 0.0)),
                    expiry=str(item.get("expiry", "")),
                    option_type=str(item.get("type", item.get("option_type", "C"))).upper(),
                    trigger_price=float(item.get("trigger_price", 0.0)),
                    qty=int(item.get("qty", 1)),
                    reset_pct=float(item.get("reset_pct", 0.20)),
                )
            )
        option_buyback = OptionBuybackConfig(
            enabled=bool(option_buyback_data.get("enabled", bool(option_buyback_targets))),
            symbol=str(option_buyback_data.get("symbol", "TQQQ")),
            targets=option_buyback_targets,
            state_path=str(
                option_buyback_data.get(
                    "state_path",
                    "~/.cache/clawdfolio/option_buyback_state.json",
                )
            ),
        )

        return cls(
            brokers=brokers,
            alerts=alerts,
            currency=data.get("currency", "USD"),
            timezone=data.get("timezone", "America/New_York"),
            cache_ttl=data.get("cache_ttl", 300),
            leveraged_etfs=leveraged_etfs,
            option_buyback=option_buyback,
            output_format=data.get("output_format", "console"),
            verbose=data.get("verbose", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert Config to dictionary."""
        return {
            "brokers": {
                name: {
                    "enabled": cfg.enabled,
                    "env_prefix": cfg.env_prefix,
                    "timeout": cfg.timeout,
                    "extra": cfg.extra,
                }
                for name, cfg in self.brokers.items()
            },
            "alerts": {
                "pnl_trigger": self.alerts.pnl_trigger,
                "pnl_step": self.alerts.pnl_step,
                "rsi_high": self.alerts.rsi_high,
                "rsi_low": self.alerts.rsi_low,
                "rsi_step": self.alerts.rsi_step,
                "single_stock_threshold_top10": self.alerts.single_stock_threshold_top10,
                "single_stock_threshold_other": self.alerts.single_stock_threshold_other,
                "move_step": self.alerts.move_step,
                "concentration_threshold": self.alerts.concentration_threshold,
            },
            "currency": self.currency,
            "timezone": self.timezone,
            "cache_ttl": self.cache_ttl,
            "leveraged_etfs": {
                etf: list(info) for etf, info in self.leveraged_etfs.items()
            },
            "option_buyback": {
                "enabled": self.option_buyback.enabled,
                "symbol": self.option_buyback.symbol,
                "state_path": self.option_buyback.state_path,
                "targets": [
                    {
                        "name": target.name,
                        "strike": target.strike,
                        "expiry": target.expiry,
                        "type": target.option_type,
                        "trigger_price": target.trigger_price,
                        "qty": target.qty,
                        "reset_pct": target.reset_pct,
                    }
                    for target in self.option_buyback.targets
                ],
            },
            "output_format": self.output_format,
            "verbose": self.verbose,
        }


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from file or environment.

    Search order:
    1. Explicit path argument
    2. CLAWDFOLIO_CONFIG environment variable (legacy: PORTFOLIO_MONITOR_CONFIG)
    3. ./config.yaml
    4. ./config.json
    5. ~/.config/clawdfolio/config.yaml
    6. ~/.config/clawdfolio/config.json
    7. ~/.config/portfolio-monitor/config.yaml  (legacy fallback)
    8. ~/.config/portfolio-monitor/config.json   (legacy fallback)
    9. Default config
    """
    search_paths: list[Path] = []

    if path:
        search_paths.append(Path(path))

    env_path = os.environ.get("CLAWDFOLIO_CONFIG") or os.environ.get(
        "PORTFOLIO_MONITOR_CONFIG"
    )
    if env_path:
        search_paths.append(Path(env_path))

    search_paths.extend(
        [
            Path("config.yaml"),
            Path("config.json"),
            Path.home() / ".config" / "clawdfolio" / "config.yaml",
            Path.home() / ".config" / "clawdfolio" / "config.json",
            # Legacy paths for backward compatibility
            Path.home() / ".config" / "portfolio-monitor" / "config.yaml",
            Path.home() / ".config" / "portfolio-monitor" / "config.json",
        ]
    )

    for p in search_paths:
        if p.exists():
            return _load_from_file(p)

    # Return default config
    return _default_config()


def _load_from_file(path: Path) -> Config:
    """Load config from YAML or JSON file."""
    try:
        content = path.read_text(encoding="utf-8")

        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content)
        elif path.suffix == ".json":
            data = json.loads(content)
        else:
            # Try YAML first, then JSON
            try:
                data = yaml.safe_load(content)
            except Exception:
                data = json.loads(content)

        if not isinstance(data, dict):
            raise ConfigError(f"Invalid config format in {path}")

        return Config.from_dict(data)
    except Exception as e:
        raise ConfigError(f"Failed to load config from {path}: {e}") from e


def _default_config() -> Config:
    """Return default configuration."""
    return Config(
        brokers={
            "longport": BrokerConfig(
                enabled=True,
                env_prefix="LONGPORT_",
            ),
            "futu": BrokerConfig(
                enabled=True,
                env_prefix="FUTU_",
                extra={"host": "127.0.0.1", "port": 11111},
            ),
            "demo": BrokerConfig(enabled=False),
        },
        alerts=AlertConfig(),
        leveraged_etfs={
            "TQQQ": ("QQQ", 3, "Nasdaq 100"),
            "SQQQ": ("QQQ", -3, "Nasdaq 100"),
            "UPRO": ("SPY", 3, "S&P 500"),
            "SPXU": ("SPY", -3, "S&P 500"),
            "TNA": ("IWM", 3, "Russell 2000"),
            "TZA": ("IWM", -3, "Russell 2000"),
            "SOXL": ("SOXX", 3, "Semiconductors"),
            "SOXS": ("SOXX", -3, "Semiconductors"),
            "FNGU": ("QQQ", 3, "FANG+"),
            "LABU": ("XBI", 3, "Biotech"),
        },
    )


def save_config(config: Config, path: str | Path) -> None:
    """Save configuration to file."""
    path = Path(path)
    data = config.to_dict()

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix in (".yaml", ".yml"):
        content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        content = json.dumps(data, indent=2, ensure_ascii=False)

    path.write_text(content, encoding="utf-8")
