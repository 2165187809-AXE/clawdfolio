"""Environment loading helpers.

Clawdbot often runs scripts via cron/daemon, which won't source ~/.zshrc.
We keep broker API credentials in a local, git-ignored file: data/longport_env.sh
("export KEY=..." lines).

This module loads those exports into os.environ at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union


def load_env_exports(path: Union[str, Path]) -> bool:
    """Load simple `export KEY=...` lines from a shell file into os.environ.

    - Does NOT overwrite existing environment variables.
    - Supports single/double quotes.
    - Ignores comments/blank lines.

    Returns True if file existed and was parsed.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return False

    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        return False

    return True


def load_longport_env(repo_root: Union[str, Path] | None = None) -> bool:
    """Load LongPort env from data/longport_env.sh (best effort)."""
    if repo_root is None:
        # scripts/lib/env_loader.py -> scripts/lib -> scripts -> repo root
        repo_root = Path(__file__).resolve().parents[2]
    return load_env_exports(Path(repo_root) / "data" / "longport_env.sh")
