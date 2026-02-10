#!/usr/bin/env python3
"""Run portfolio_daily_brief.py and output only the brief body (strip any noisy tables)."""

import subprocess
import sys


def main():
    p = subprocess.run([sys.executable, "scripts/portfolio_daily_brief.py"], capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    lines = [ln.rstrip() for ln in out.splitlines()]

    # Start at the brief header
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("📊 Daily Brief"):
            start = i
            break
    if start is None:
        print((p.stderr or p.stdout or "").strip())
        sys.exit(1 if p.returncode != 0 else 0)

    clean = []
    for ln in lines[start:]:
        if ln.startswith("+") or ln.startswith("|") or ln.startswith("HTTP Error"):
            continue
        clean.append(ln)

    print("\n".join(clean).strip())
    sys.exit(0 if p.returncode == 0 else 1)


if __name__ == "__main__":
    main()
