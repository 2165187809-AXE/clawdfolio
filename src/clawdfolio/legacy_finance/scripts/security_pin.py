#!/usr/bin/env python3
"""PIN verification helper for Telegram confirmations.

Design goals:
- Never print the PIN.
- Store only salted hash locally (gitignored).
- Provide a tiny API other scripts can import.

State file: data/security_pin_hash.json
Format:
  {"salt": "...", "hash": "..."}
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "security_pin_hash.json"


def _pbkdf2(pin: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)
    return dk.hex()


def is_configured() -> bool:
    return STATE_PATH.exists()


def configure(pin: str) -> None:
    if not pin or len(pin) < 6:
        raise ValueError("PIN must be at least 6 digits")
    salt = os.urandom(16)
    data = {"salt": salt.hex(), "hash": _pbkdf2(pin, salt)}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def verify(pin: str) -> bool:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        salt = bytes.fromhex(data["salt"])
        good = str(data["hash"])
        test = _pbkdf2(pin, salt)
        return hmac.compare_digest(test, good)
    except Exception:
        return False


def _cli() -> int:
    import argparse
    import getpass

    ap = argparse.ArgumentParser(description="Configure/verify Telegram trade PIN (stored as salted hash).")
    ap.add_argument("--set", action="store_true", help="Set/replace the PIN")
    ap.add_argument("--verify", action="store_true", help="Verify a PIN")
    args = ap.parse_args()

    if args.set:
        pin1 = getpass.getpass("New PIN (min 6 digits): ")
        pin2 = getpass.getpass("Repeat PIN: ")
        if pin1 != pin2:
            raise SystemExit("PINs do not match")
        configure(pin1)
        print("OK: PIN configured (hash stored locally)")
        return 0

    if args.verify:
        pin = getpass.getpass("PIN: ")
        ok = verify(pin)
        print("OK" if ok else "NO")
        return 0 if ok else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
