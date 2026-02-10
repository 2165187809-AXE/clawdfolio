#!/usr/bin/env python3
"""Binance.com assets summary (Spot + Futures + Earn) using Read-only API keys.

Reads env vars:
- BINANCE_API_KEY
- BINANCE_API_SECRET

Outputs one JSON line (for further integration).

Safety: does NOT place orders; does not withdraw.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests

BASE_SPOT = "https://api.binance.com"
BASE_SAPI = "https://api.binance.com"
BASE_FAPI = "https://fapi.binance.com"  # USDT-M futures
BASE_DAPI = "https://dapi.binance.com"  # COIN-M futures


def _sign(params: Dict[str, Any], secret: str) -> str:
    qs = urllib.parse.urlencode(params, doseq=True)
    return hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()


def _req(method: str, base: str, path: str, key: str, secret: str, params: Optional[Dict[str, Any]] = None) -> Any:
    params = dict(params or {})
    params.setdefault("timestamp", int(time.time() * 1000))
    params.setdefault("recvWindow", 5000)
    params["signature"] = _sign(params, secret)

    url = base + path
    headers = {"X-MBX-APIKEY": key}

    r = requests.request(method, url, headers=headers, params=params, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} {path}: {r.text[:200]}")
    return r.json()


def spot_account(key: str, secret: str) -> Any:
    return _req("GET", BASE_SPOT, "/api/v3/account", key, secret)


def futures_usdt_account(key: str, secret: str) -> Any:
    return _req("GET", BASE_FAPI, "/fapi/v2/account", key, secret)


def futures_coin_account(key: str, secret: str) -> Any:
    return _req("GET", BASE_DAPI, "/dapi/v1/account", key, secret)


def earn_flexible_positions(key: str, secret: str) -> Any:
    # Simple Earn Flexible Positions
    return _req("GET", BASE_SAPI, "/sapi/v1/simple-earn/flexible/position", key, secret, {"current": 1, "size": 100})


def earn_locked_positions(key: str, secret: str) -> Any:
    return _req("GET", BASE_SAPI, "/sapi/v1/simple-earn/locked/position", key, secret, {"current": 1, "size": 100})


def main() -> None:
    key = os.getenv("BINANCE_API_KEY", "")
    secret = os.getenv("BINANCE_API_SECRET", "")
    if not key or not secret:
        raise SystemExit("Missing BINANCE_API_KEY / BINANCE_API_SECRET")

    out: Dict[str, Any] = {
        "ts": int(time.time()),
        "spot": None,
        "futures_usdt": None,
        "futures_coin": None,
        "earn_flexible": None,
        "earn_locked": None,
        "errors": {},
    }

    try:
        out["spot"] = spot_account(key, secret)
    except Exception as e:
        out["errors"]["spot"] = str(e)

    try:
        out["futures_usdt"] = futures_usdt_account(key, secret)
    except Exception as e:
        out["errors"]["futures_usdt"] = str(e)

    try:
        out["futures_coin"] = futures_coin_account(key, secret)
    except Exception as e:
        out["errors"]["futures_coin"] = str(e)

    try:
        out["earn_flexible"] = earn_flexible_positions(key, secret)
    except Exception as e:
        out["errors"]["earn_flexible"] = str(e)

    try:
        out["earn_locked"] = earn_locked_positions(key, secret)
    except Exception as e:
        out["errors"]["earn_locked"] = str(e)

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
