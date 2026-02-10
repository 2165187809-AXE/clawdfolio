#!/usr/bin/env python3
"""Portfolio alert monitor with deduping.

Runs every 5 minutes during market hours. Sends alerts ONLY when:
- A trigger newly appears, OR
- Same trigger becomes materially more extreme.

Triggers (per config):
- Sector concentration > threshold (direct calculation)
- RSI > high or RSI < low (direct calculation)
- Intraday loss > threshold (direct calculation)
- Single-name daily move alerts: Top10 threshold 5%, others threshold 10%

State:
- data/portfolio_alert_state.json (with file locking via lib/state)

Output:
- Prints either empty string (no alert) or a full alert message.

Note: This script does NOT send messages itself; cron payload should send stdout if non-empty.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.brokers import fetch_holdings, fetch_balances, fetch_balances_and_holdings, HoldingInfo, time_limit, suppress_stdio_fds
from lib.fmt import fmt_money, fmt_pct
from lib.market import get_news, get_price, risk_free_rate
from lib.state import StateFile

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
STATE = StateFile("data/portfolio_alert_state.json")

# ---------------------------------------------------------------------------
# Global hard-kill watchdog: if the process hasn't exited after ALERT_TIMEOUT
# seconds, print empty and _exit(0) so cron won't accumulate zombie processes.
# ---------------------------------------------------------------------------
ALERT_TIMEOUT: int = 50  # overridden from config if present


def _watchdog(deadline_s: int) -> None:
    """Background thread that forcibly exits the process after *deadline_s*."""
    time.sleep(deadline_s)
    # If we're still alive, force exit. Use os._exit to bypass any stuck I/O.
    try:
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(0)


def _run_with_timeout(fn, timeout_s: int, default=None):
    """Run *fn* in a daemon thread; return *default* on timeout."""
    result = {"value": default}

    def _inner():
        try:
            result["value"] = fn()
        except Exception:
            result["value"] = default

    t = threading.Thread(target=_inner, daemon=True)
    t.start()
    t.join(timeout_s)
    return result["value"]


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


LEVERAGED_ETFS = {
    "TQQQ": ("QQQ", 3, "纳指100"),
    "SQQQ": ("QQQ", -3, "纳指100"),
    "UPRO": ("SPY", 3, "标普500"),
    "SPXU": ("SPY", -3, "标普500"),
    "TNA": ("IWM", 3, "罗素2000"),
    "TZA": ("IWM", -3, "罗素2000"),
    "SOXL": ("SOXX", 3, "半导体"),
    "SOXS": ("SOXX", -3, "半导体"),
    "FNGU": ("QQQ", 3, "FANG+"),
    "LABU": ("XBI", 3, "生物科技"),
}


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def get_qqq_last() -> Optional[float]:
    """Fetch QQQ last price via LongPort or yfinance (with timeout)."""
    def _lp():
        try:
            import io
            from contextlib import redirect_stdout, redirect_stderr

            _null = io.StringIO()
            with suppress_stdio_fds():
                with redirect_stdout(_null), redirect_stderr(_null):
                    from longport.openapi import Config, QuoteContext
                    cfg = Config.from_env()
                    quote = QuoteContext(cfg)
                    qs = quote.quote(["QQQ.US"])
            if qs:
                last = float(qs[0].last_done)
                return last if last > 0 else None
        except Exception:
            return None

    val = _run_with_timeout(_lp, 8)
    if val is not None:
        return val

    def _yf():
        try:
            p = get_price("QQQ")
            return p if p and p > 0 else None
        except Exception:
            return None

    return _run_with_timeout(_yf, 6)


def holdings_snapshot() -> Tuple[List[Tuple[str, float, float]], float, float, Dict[str, HoldingInfo]]:
    """Return ([(ticker, weight, day_pct), ...], total_net, day_pnl, holdings_dict).

    Uses lib/brokers directly. Also returns the raw holdings dict so callers
    don't need to fetch it again (avoids a second LongPort connection).
    """
    result = _run_with_timeout(fetch_balances_and_holdings, 20)
    if result is None:
        return [], 0.0, 0.0, {}

    balances, holdings = result
    combined = balances["combined"]
    total_net = combined.net_assets
    day_pnl = combined.day_pnl

    # If all brokers failed, return empty to avoid false alerts
    if total_net == 0 and combined.error:
        return [], 0.0, 0.0, {}

    out: List[Tuple[str, float, float]] = []
    for t, h in holdings.items():
        if h.mv <= 0 or total_net <= 0:
            continue
        w = h.mv / total_net
        day_pct = 0.0
        if h.price and h.prev_close and h.prev_close > 0:
            day_pct = h.price / h.prev_close - 1.0
        out.append((t, w, day_pct))

    out.sort(key=lambda x: x[1], reverse=True)
    return out, total_net, day_pnl, holdings


def compute_rsi_extremes(holdings: Dict[str, HoldingInfo], rsi_high: int, rsi_low: int) -> List[Tuple[str, int]]:
    """Compute RSI for top holdings and return extreme values."""
    import yfinance as yf
    import pandas as pd

    extremes: List[Tuple[str, int]] = []
    sorted_h = sorted(holdings.values(), key=lambda x: x.mv, reverse=True)

    for h in sorted_h[:10]:
        try:
            sym = h.ticker.replace(".", "-")
            # Per-ticker timeout via thread
            def _dl(s=sym):
                return yf.download(s, period="1mo", interval="1d", progress=False)
            hist = _run_with_timeout(_dl, 6)
            if hist is None or hist.empty or len(hist) < 15:
                continue
            prices = hist["Close"].squeeze().dropna()
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_val = int(round(rsi.iloc[-1].item()))
            if rsi_val >= rsi_high or rsi_val <= rsi_low:
                extremes.append((h.ticker, rsi_val))
        except Exception:
            continue

    return extremes


def compute_rsi_extremes_safe(
    holdings: Dict[str, HoldingInfo], rsi_high: int, rsi_low: int, timeout_s: int = 15
) -> List[Tuple[str, int]]:
    """Run RSI calculation in a daemon thread with total timeout."""
    return _run_with_timeout(
        lambda: compute_rsi_extremes(holdings, rsi_high, rsi_low),
        timeout_s,
    ) or []



def _pnl_attribution(
    holds: List[Tuple[str, float, float]], day_pnl: float, total_net: float
) -> str:
    is_gain = day_pnl > 0
    contributors: List[Tuple[str, float, float, float]] = []
    for tkr, w, day_pct in holds:
        if (is_gain and day_pct > 0) or (not is_gain and day_pct < 0):
            contrib = day_pct * w * total_net
            contributors.append((tkr, day_pct, w, contrib))

    contributors.sort(key=lambda x: x[3], reverse=is_gain)
    top = contributors[:3]
    arrow = "▲" if is_gain else "▼"
    parts = [f"{t} {arrow}{abs(dp) * 100:.1f}%(占{w * 100:.1f}%)" for t, dp, w, _ in top]

    pnl_pct = abs(day_pnl) / total_net * 100 if total_net > 0 else 0

    if is_gain:
        summary = "、".join(parts) if parts else "多只持仓小幅上涨累积"
        if pnl_pct >= 5:
            tone = "涨幅较大，可以考虑部分获利了结。"
        elif pnl_pct >= 3:
            tone = "涨势不错，关注是否有回调风险。"
        else:
            tone = "小幅盈利，继续持有观察。"
        return f"主要贡献：{summary}。{tone}"
    else:
        summary = "、".join(parts) if parts else "多只持仓小幅下跌累积"
        if pnl_pct >= 5:
            tone = "亏损幅度较大，建议审视仓位考虑减仓控制风险。"
        elif pnl_pct >= 3:
            tone = "亏损值得关注，密切跟踪走势，做好止损准备。"
        else:
            tone = "亏损尚在可控范围，可以持有观望。"
        return f"主要拖累：{summary}。{tone}"


def _rsi_advice(ticker: str, rsi: int) -> str:
    if rsi < 20:
        return f"{ticker} 连续走弱，RSI跌到{rsi}已经是极端超卖了。这种位置反弹概率不小，基本面没变的话可以考虑分批接一些。"
    elif rsi <= 30:
        return f"{ticker} 近期持续走弱，RSI {rsi}处于超卖区域，关注是否出现反弹迹象。"
    elif rsi >= 80:
        return f"{ticker} 连续走强，RSI到{rsi}已经极端超买了，可以考虑部分减仓锁定利润。"
    else:
        return f"{ticker} 近期持续走强，RSI {rsi}处于超买区域，可以适当获利了结。"



def _fetch_catalyst(ticker: str) -> str:
    def _inner():
        try:
            news_items = get_news(ticker, max_items=3)
            if not news_items:
                return ""
            n = news_items[0]
            text = (n.title + " " + n.summary).lower()
            cn = _classify_news_cn(ticker, text)
            link_str = f"\n详情：{n.link}" if n.link else ""
            return f"{cn}{link_str}"
        except Exception:
            return ""
    return _run_with_timeout(_inner, 6, "")


def _classify_news_cn(ticker: str, text: str) -> str:
    tl = text.lower()
    if any(w in tl for w in ["earnings", "quarterly", "q1 ", "q2 ", "q3 ", "q4 ", "revenue", "eps"]):
        if any(w in tl for w in ["beat", "surpass", "exceed", "record", "strong"]):
            return f"{ticker} 刚发布财报，业绩超预期"
        elif any(w in tl for w in ["miss", "disappoint", "weak", "below"]):
            return f"{ticker} 刚发布财报，业绩不及预期"
        else:
            return f"{ticker} 刚发布财报"
    if any(w in tl for w in ["crash", "plunge", "tumble", "tank", "sell-off", "selloff"]):
        return f"{ticker} 遭遇大幅抛售"
    if any(w in tl for w in ["upgrade", "overweight", "outperform"]):
        return f"{ticker} 获分析师上调评级"
    if any(w in tl for w in ["downgrade", "underweight", "underperform"]):
        return f"{ticker} 被分析师下调评级"
    if any(w in tl for w in ["fda", "approval", "drug", "trial"]):
        return f"{ticker} 有药物/FDA相关消息"
    if any(w in tl for w in ["acquisition", "acquire", "merger", "buyout", "takeover"]):
        return f"{ticker} 涉及并购消息"
    if any(w in tl for w in ["contract", "deal", "partnership", "award"]):
        return f"{ticker} 获得新合同/合作"
    if any(w in tl for w in ["buy", "bought", "stake", "position"]):
        return f"{ticker} 有机构买入/建仓消息"
    if any(w in tl for w in ["sue", "lawsuit", "investigation", "probe", "sec "]):
        return f"{ticker} 面临诉讼/调查"
    if any(w in tl for w in ["guidance", "outlook", "forecast"]):
        if any(w in tl for w in ["raise", "higher", "optimistic", "above"]):
            return f"{ticker} 上调了业绩指引"
        elif any(w in tl for w in ["lower", "cut", "below", "disappoint"]):
            return f"{ticker} 下调了业绩指引"
        return f"{ticker} 更新了业绩指引"
    if any(w in tl for w in ["dividend", "buyback", "repurchase"]):
        return f"{ticker} 有分红/回购消息"
    snippet = text.strip()[:60]
    return f"{ticker} 近期消息：{snippet}"


def _move_context(ticker: str, day_pct: float, weight: float, rank: int) -> str:
    lev = LEVERAGED_ETFS.get(ticker)
    abs_pct = abs(day_pct) * 100
    impact = abs(day_pct * weight) * 100
    direction = "跌" if day_pct < 0 else "涨"
    w_str = f"占组合{weight * 100:.1f}%"

    if impact >= 0.5:
        direction_word = "贡献" if day_pct >= 0 else "拖累"
        impact_str = f"，{direction_word}组合约{impact:.1f}%"
    elif impact >= 0.1:
        impact_str = f"，对组合影响约{impact:.1f}%"
    else:
        impact_str = "，对组合整体影响不大"

    if lev:
        underlying, mult, name = lev
        return (
            f"{ticker}（{w_str}）是{abs(mult)}倍杠杆ETF，"
            f"跟随{name}({underlying})放大波动属于正常杠杆效应{impact_str}。"
            f"关注标的指数 {underlying} 走势就好，不用盯 {ticker} 本身。"
        )

    catalyst = _fetch_catalyst(ticker) if abs_pct >= 5 else ""
    catalyst_str = f"可能催化剂：{catalyst}。" if catalyst else ""

    if abs_pct >= 10:
        return (
            f"{ticker}（{w_str}）单日{direction}了{abs_pct:.1f}%{impact_str}。"
            f"幅度比较异常。{catalyst_str}"
            f"{'建议结合上述消息评估后续走势。' if catalyst else '暂未查到明确催化剂，建议关注是否有财报、公告或评级变动。'}"
        )
    elif day_pct < -0.05:
        return (
            f"{ticker}（{w_str}）今天{direction}了{abs_pct:.1f}%{impact_str}。"
            f"{catalyst_str}"
            f"{'回调幅度较大，结合消息面判断是否继续持有。' if catalyst else '回调幅度较大，基本面没变的话可以耐心持有。'}"
        )
    elif day_pct > 0.05:
        return (
            f"{ticker}（{w_str}）今天{direction}了{abs_pct:.1f}%{impact_str}。"
            f"{catalyst_str}"
            f"{'短期涨势较强，结合消息面考虑是否获利了结。' if catalyst else '短期涨势较强，可以考虑适当获利了结一部分。'}"
        )
    else:
        return f"{ticker}（{w_str}）波动较大{impact_str}，密切关注后续走势。"


def _risk_profile_supplement(timeout_s: int = 6) -> str:
    """Generate risk profile supplement from portfolio analysis."""
    def _inner():
        try:
            from portfolio_analysis_enhanced import analyze_portfolio
            r = analyze_portfolio()

            parts = []

            if r.portfolio_volatility is not None:
                vol_level = "低" if r.portfolio_volatility < 0.15 else ("中" if r.portfolio_volatility < 0.25 else "高")
                parts.append(f"组合波动率 {r.portfolio_volatility * 100:.1f}%（{vol_level}）")

            if r.portfolio_beta is not None:
                beta_level = "防守" if r.portfolio_beta < 1 else ("中性" if r.portfolio_beta < 1.2 else "激进")
                parts.append(f"Beta {r.portfolio_beta:.2f}（{beta_level}）")

            if r.max_drawdown is not None:
                parts.append(f"最大回撤 {r.max_drawdown * 100:.1f}%")

            if r.holdings:
                top = r.holdings[0]
                if top.weight > 0.15:
                    parts.append(f"{top.ticker} 单股占比 {top.weight * 100:.1f}%（集中度偏高）")

            if r.high_corr_pairs:
                corr_items = [f"{t1}↔{t2} {c:.2f}" for t1, t2, c in r.high_corr_pairs[:2]]
                parts.append("相关性警告：" + "；".join(corr_items))

            if not parts:
                return ""

            main_part = "、".join(parts[:3])
            extra = "；".join(parts[3:])
            text = main_part + ("；" + extra if extra else "")

            return f"📋 风险概况补充：{text}"
        except Exception:
            return ""

    return _run_with_timeout(_inner, timeout_s, "")


def should_send(key: str, severity: float, step: float, last: dict) -> bool:
    prev = last.get(key)
    if prev is None:
        return True
    try:
        prev_sev = float(prev.get("severity"))
        prev_active = bool(prev.get("active", False))
    except Exception:
        return True
    if not prev_active:
        return True
    return severity >= prev_sev + step


def main() -> None:
    cfg = load_config()
    alerts_cfg = cfg.get("alerts", {})
    tqqq_cfg = cfg.get("tqqq_macro", {})

    # Global hard timeout: process will os._exit(0) after this many seconds
    global ALERT_TIMEOUT
    ALERT_TIMEOUT = alerts_cfg.get("alert_timeout", 50)

    # Start watchdog thread - kills the process if it hangs beyond ALERT_TIMEOUT
    wd = threading.Thread(target=_watchdog, args=(ALERT_TIMEOUT,), daemon=True)
    wd.start()

    PNL_TRIGGER = alerts_cfg.get("pnl_trigger", 500.0)
    PNL_STEP = alerts_cfg.get("pnl_step", 500.0)
    RSI_HIGH = alerts_cfg.get("rsi_high", 80)
    RSI_LOW = alerts_cfg.get("rsi_low", 20)
    RSI_STEP = alerts_cfg.get("rsi_step", 2)
    MOVE_TOP10_TRIGGER = alerts_cfg.get("single_stock_threshold_top10", 0.05)
    MOVE_OTHER_TRIGGER = alerts_cfg.get("single_stock_threshold_other", 0.10)
    MOVE_STEP = alerts_cfg.get("move_step", 0.01)

    QQQ_52W_HIGH = tqqq_cfg.get("qqq_52w_high", 636.60)
    L1_TRIGGER_PCT = tqqq_cfg.get("l1_trigger_pct", -0.10)
    QQQ_L1_TRIGGER = QQQ_52W_HIGH * (1 + L1_TRIGGER_PCT)
    TQQQ_L1_AMT_EACH = tqqq_cfg.get("l1_amount_each", 2301.86)
    TQQQ_L1_MIN_GAP_SECONDS = tqqq_cfg.get("l1_min_gap_seconds", 172800)

    st = STATE.load()
    last = st.setdefault("last", {})

    # ---- Step 1: Gather holdings + balances (single broker call, with timeout)
    holds, total_net, day_pnl, holdings_dict = holdings_snapshot()

    # ---- Step 2: RSI extremes (with total timeout, non-blocking)
    rsi_hits = compute_rsi_extremes_safe(holdings_dict, RSI_HIGH, RSI_LOW, timeout_s=15)

    alerts: List[str] = []

    # ---- Step 3: QQQ Level-1 trigger (with timeout)
    qqq_last = get_qqq_last()
    qqq_key = "qqq_l1"
    rec = last.get(qqq_key) or {"hitTs": None, "t1Count": 0, "t2Count": 0}
    now = int(time.time())

    if qqq_last is not None and qqq_last <= QQQ_L1_TRIGGER:
        if not rec.get("hitTs"):
            rec["hitTs"] = now

        if int(rec.get("t1Count", 0) or 0) < 3:
            n = int(rec.get("t1Count", 0) or 0) + 1
            alerts.append(
                f"📌 TQQQ 加仓触发（L1）[{n}/3]\n"
                f"QQQ ≤ {QQQ_L1_TRIGGER:.2f}（52W高点{QQQ_52W_HIGH:.2f}回撤{L1_TRIGGER_PCT * 100:.0f}%）\n"
                f"当前QQQ: {qqq_last:.2f}\n"
                f"建议金额：{fmt_money(TQQQ_L1_AMT_EACH, 2)}（第1笔/2）"
            )
            rec["t1Count"] = n
        else:
            hit_ts = int(rec.get("hitTs") or now)
            if now - hit_ts >= TQQQ_L1_MIN_GAP_SECONDS and int(rec.get("t2Count", 0) or 0) < 3:
                n = int(rec.get("t2Count", 0) or 0) + 1
                alerts.append(
                    f"📌 TQQQ 加仓再次确认（L1）[{n}/3]\n"
                    f"QQQ 仍 ≤ {QQQ_L1_TRIGGER:.2f} 且已满足48小时间隔\n"
                    f"当前QQQ: {qqq_last:.2f}\n"
                    f"建议金额：{fmt_money(TQQQ_L1_AMT_EACH, 2)}（第2笔/2）"
                )
                rec["t2Count"] = n
    else:
        rec = {"hitTs": None, "t1Count": 0, "t2Count": 0}

    last[qqq_key] = rec

    # Day PnL trigger (both gain and loss)
    if day_pnl is not None and abs(day_pnl) >= PNL_TRIGGER:
        sev = abs(day_pnl)
        if should_send("pnl", sev, PNL_STEP, last):
            detail = _pnl_attribution(holds, day_pnl, total_net)
            if day_pnl > 0:
                alerts.append(f"📈 组合日内盈利 ▲{fmt_money(sev)}\n{detail}")
            else:
                alerts.append(f"📉 组合日内亏损 ▼{fmt_money(sev)}\n{detail}")
        last["pnl"] = {"active": True, "severity": sev, "ts": now}
    else:
        last["pnl"] = {"active": False, "severity": 0, "ts": now}

    # RSI extremes
    if rsi_hits:
        for tkr, rsi in sorted(rsi_hits, key=lambda x: x[1]):
            if rsi <= RSI_LOW:
                sev = RSI_LOW - rsi
                key = f"rsi_low:{tkr}"
                if should_send(key, sev, RSI_STEP, last):
                    detail = _rsi_advice(tkr, rsi)
                    alerts.append(f"📊 RSI超卖：{tkr} RSI {rsi}\n{detail}")
                last[key] = {"active": True, "severity": sev, "ts": now, "rsi": rsi}
            elif rsi >= RSI_HIGH:
                sev = rsi - RSI_HIGH
                key = f"rsi_high:{tkr}"
                if should_send(key, sev, RSI_STEP, last):
                    detail = _rsi_advice(tkr, rsi)
                    alerts.append(f"📊 RSI超买：{tkr} RSI {rsi}\n{detail}")
                last[key] = {"active": True, "severity": sev, "ts": now, "rsi": rsi}

    active_keys = {f"rsi_low:{t}" for t, r in rsi_hits if r <= RSI_LOW} | {f"rsi_high:{t}" for t, r in rsi_hits if r >= RSI_HIGH}
    for k in list(last.keys()):
        if k.startswith("rsi_") and k not in active_keys:
            last[k] = {"active": False, "severity": 0, "ts": now}

    # Single-name move alerts
    move_active = set()
    for i, (tkr, w, day_pct) in enumerate(holds, start=1):
        thr = MOVE_TOP10_TRIGGER if i <= 10 else MOVE_OTHER_TRIGGER
        if abs(day_pct) >= thr:
            sev = abs(day_pct)
            key = f"move:{tkr}"
            move_active.add(key)
            if should_send(key, sev, MOVE_STEP, last):
                direction = "▼" if day_pct < 0 else "▲"
                emoji = "📈" if day_pct >= 0 else "📉"
                detail = _move_context(tkr, day_pct, w, i)
                alerts.append(f"{emoji} 异动：{tkr} {direction}{abs(day_pct) * 100:.1f}%\n{detail}")
            last[key] = {"active": True, "severity": sev, "ts": now, "day_pct": day_pct, "rank": i}

    for k in list(last.keys()):
        if k.startswith("move:") and k not in move_active:
            last[k] = {"active": False, "severity": 0, "ts": now}

    st["updatedAt"] = now
    STATE.save(st)

    if not alerts:
        print("")
        return

    supplement = _risk_profile_supplement(timeout_s=6)
    msg = "⚠️ 投资组合警报\n\n" + "\n\n".join(alerts)
    if supplement:
        msg += "\n\n" + supplement
    print(msg.strip())


if __name__ == "__main__":
    main()
