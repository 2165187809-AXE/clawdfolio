"""State management with file locking for safe concurrent access."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path
from typing import Any, Optional


class StateFile:
    """JSON state file with advisory file locking (fcntl.flock).

    Usage:
        sf = StateFile("data/my_state.json")
        data = sf.load()
        data["key"] = "value"
        sf.save(data)

        # Or atomic update:
        sf.update("key", "value")
    """

    def __init__(self, path: str | Path):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        self.path = p

    def load(self) -> dict:
        """Load state from file. Returns empty dict structure if missing/corrupt."""
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, data: dict) -> None:
        """Save state atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def update(self, key: str, value: Any) -> dict:
        """Atomic read-modify-write for a single key."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Use exclusive lock for the entire read-modify-write cycle
        lock_path = self.path.with_suffix(".lock")
        with open(lock_path, "w") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                data = {}
                if self.path.exists():
                    try:
                        data = json.loads(self.path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        data = {}
                data[key] = value
                self.path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                return data
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)
