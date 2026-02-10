#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone

try:
    from longport.openapi import TradeContext, Config
except Exception as e:
    raise SystemExit(f"Failed to import longport SDK. Did you install it? Error: {e}")


def main():
    # Config will read env vars: LONGPORT_APP_KEY / LONGPORT_APP_SECRET / LONGPORT_ACCESS_TOKEN / LONGPORT_REGION
    cfg = Config.from_env()

    # Use TradeContext to read account assets.
    # NOTE: API field names may vary by account type/region.
    ctx = TradeContext(cfg)
    account = ctx.account_balance(currency="USD")

    # Best-effort extract totals
    # The SDK may return an AccountBalance object or a list (multi-account). We'll parse robustly.
    text = str(account)

    import re

    m_assets = re.search(r"net_assets:\s*([-0-9.]+)", text)
    m_ccy = re.search(r"currency:\s*\"([A-Z]+)\"", text)

    net_assets = float(m_assets.group(1)) if m_assets else None
    currency = m_ccy.group(1) if m_ccy else None

    out = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "region": os.getenv("LONGPORT_REGION"),
        "net_assets": net_assets,
        "currency": currency,
        "raw": text,
    }

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
