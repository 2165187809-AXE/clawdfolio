#!/usr/bin/env python3
"""Market News - 获取持仓相关的市场新闻

获取持仓股票的最新新闻，帮助用户了解市场动态。

数据源: yfinance news API (via lib/market)
输出: 按时间排序的新闻摘要，含链接
"""

from __future__ import annotations

import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.brokers import fetch_holdings
from lib.fmt import fmt_time
from lib.market import get_news, NewsItem


def categorize_news(title: str) -> str:
    """Categorize news based on title keywords."""
    title_lower = title.lower()

    if any(kw in title_lower for kw in ["earnings", "revenue", "profit", "loss", "beat", "miss", "eps", "财报", "营收"]):
        return "📊 财报"
    if any(kw in title_lower for kw in ["surge", "soar", "jump", "rally", "climb", "plunge", "drop", "fall", "crash", "tumble"]):
        return "📈 行情"
    if any(kw in title_lower for kw in ["upgrade", "downgrade", "rating", "price target", "analyst", "buy", "sell", "hold"]):
        return "🎯 评级"
    if any(kw in title_lower for kw in ["launch", "announce", "deal", "partnership", "acquisition", "merger", "ipo"]):
        return "💼 业务"
    if any(kw in title_lower for kw in ["sec", "fda", "ftc", "lawsuit", "investigation", "regulation", "fine"]):
        return "⚖️ 监管"
    if any(kw in title_lower for kw in ["fed", "interest rate", "inflation", "gdp", "unemployment", "fomc"]):
        return "🏛️ 宏观"
    return "📰 资讯"


def format_time_ago(dt: Optional[datetime]) -> str:
    """Format time as relative string."""
    if not dt:
        return ""
    now = datetime.now()
    diff = now - dt
    if diff.total_seconds() < 0:
        return "刚刚"
    if diff.days > 7:
        return dt.strftime("%m/%d")
    elif diff.days > 0:
        return f"{diff.days}天前"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}小时前"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}分钟前"
    else:
        return "刚刚"


def title_similar(a: str, b: str, threshold: float = 0.80) -> bool:
    """Check if two titles are similar using SequenceMatcher (ratio > threshold)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > threshold


def deduplicate_news(news_list: List[NewsItem]) -> List[NewsItem]:
    """Remove duplicate news using title similarity > 80%."""
    unique: List[NewsItem] = []
    for n in news_list:
        is_dup = False
        for u in unique:
            if title_similar(n.title, u.title):
                is_dup = True
                break
        if not is_dup:
            unique.append(n)
    return unique


def main():
    now = datetime.now()

    holdings = fetch_holdings()
    if not holdings:
        print("📰 市场新闻\n\n未找到持仓股票。请确保长桥或moomoo OpenD正在运行。")
        return

    print(f"📰 持仓相关新闻\n生成时间: {fmt_time(now)}\n")

    # Sort by market value, take top 15
    sorted_holdings = sorted(holdings.values(), key=lambda h: h.mv, reverse=True)
    top_tickers = [h.ticker for h in sorted_holdings[:15]]

    print(f"正在获取 {len(top_tickers)} 只股票的新闻...")

    all_news: List[NewsItem] = []
    for t in top_tickers:
        news = get_news(t, max_items=3)
        for n in news:
            n.ticker = t
            all_news.append(n)

    if not all_news:
        print("\n✓ 未找到相关新闻")
        return

    # Sort by time (most recent first)
    all_news.sort(key=lambda x: x.published or datetime.min, reverse=True)

    # Deduplicate using similarity > 80%
    unique_news = deduplicate_news(all_news)

    print(f"\n━━━ 最新新闻 ({len(unique_news[:20])}条) ━━━\n")

    for n in unique_news[:20]:
        category = categorize_news(n.title)
        time_str = format_time_ago(n.published)
        ticker = n.ticker
        publisher = n.publisher  # Don't truncate publisher

        title = n.title

        print(f"{category} [{ticker:5}] {title}")
        meta_parts = [publisher, time_str]
        meta = " | ".join(p for p in meta_parts if p)
        if n.link:
            print(f"   └─ {meta}")
            print(f"   🔗 {n.link}")
        else:
            print(f"   └─ {meta}")
        print()

    # Summary by ticker
    print("━━━ 按股票统计 ━━━")
    ticker_counts: Dict[str, int] = {}
    for n in unique_news:
        ticker_counts[n.ticker] = ticker_counts.get(n.ticker, 0) + 1

    sorted_tickers = sorted(ticker_counts.items(), key=lambda x: -x[1])
    for t, count in sorted_tickers[:10]:
        if count > 1:
            print(f"  {t}: {count}条新闻")

    print()
    print("提示: 新闻可能影响股价波动，重大消息请及时关注")


if __name__ == "__main__":
    main()
