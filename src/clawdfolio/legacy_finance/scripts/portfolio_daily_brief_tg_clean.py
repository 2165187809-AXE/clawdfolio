#!/usr/bin/env python3
"""Run portfolio_daily_brief_tg.py and output only the markdown code block.

Strips any noisy SDK tables that might appear before the code block.
"""

import subprocess
import sys


def main():
    p = subprocess.run([sys.executable, "scripts/portfolio_daily_brief_tg.py"], capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    lines = [ln.rstrip() for ln in out.splitlines()]

    start = None
    end = None
    for i, ln in enumerate(lines):
        if ln.strip() == "```text":
            start = i
            break
    if start is None:
        # fallback
        print((p.stdout or p.stderr or "").strip())
        sys.exit(1)

    for j in range(start + 1, len(lines)):
        if lines[j].strip() == "```":
            end = j
            break
    if end is None:
        end = len(lines)

    block = lines[start : end + 1]
    print("\n".join(block).strip())
    sys.exit(0 if p.returncode == 0 else 1)


if __name__ == "__main__":
    main()
