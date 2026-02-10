#!/usr/bin/env python3
"""Run portfolio_report.py and print only the clean report section.

Filters out noisy tables/logs produced by SDKs.
"""

import subprocess
import sys


def main():
    p = subprocess.run([sys.executable, "scripts/portfolio_report.py"], capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    lines = [ln.rstrip() for ln in out.splitlines()]

    # Find start
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("【Portfolio 总览】"):
            start = i
            break
    if start is None:
        # fallback: last 30 lines
        tail = "\n".join(lines[-30:]).strip()
        if p.returncode != 0 and not tail:
            tail = f"portfolio_report failed (code {p.returncode})"
        print(tail)
        sys.exit(0 if p.returncode == 0 else 1)

    clean = lines[start:]
    # Drop common noise lines if they sneak in, and remove any lingering N/A-only lines.
    clean2 = []
    for ln in clean:
        if ln.startswith("+") or ln.startswith("|") or ln.startswith("HTTP Error"):
            continue
        # If a line is mostly N/A placeholders, skip it
        if "N/A" in ln and all(x in ("N/A", "", "|", " ") for x in ln.replace("|", " ").split()):
            continue
        clean2.append(ln)

    print("\n".join(clean2).strip())
    sys.exit(0 if p.returncode == 0 else 1)


if __name__ == "__main__":
    main()
