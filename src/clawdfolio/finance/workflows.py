"""Workflow catalog for migrated local finance scripts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceWorkflow:
    """Executable legacy finance workflow definition."""

    workflow_id: str
    script: str
    category: str
    name: str
    description: str


CATEGORY_LABELS: dict[str, str] = {
    "portfolio_reports": "Portfolio Reports",
    "briefing_cards": "Briefing Cards",
    "alerts_monitors": "Alerts and Monitors",
    "market_intel": "Market Intelligence",
    "broker_snapshots": "Broker Snapshots",
    "strategy": "Strategy",
    "security": "Security",
}


WORKFLOWS: tuple[FinanceWorkflow, ...] = (
    FinanceWorkflow(
        workflow_id="account_report",
        script="account_report.py",
        category="portfolio_reports",
        name="Unified account report",
        description="Combined Longport + moomoo account snapshot and trades.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_report",
        script="portfolio_report.py",
        category="portfolio_reports",
        name="Daily portfolio report",
        description="Actionable daily report with performance, risk, and holdings.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_report_clean",
        script="portfolio_report_clean.py",
        category="portfolio_reports",
        name="Daily portfolio report (clean)",
        description="Noise-filtered wrapper around portfolio_report.py.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_analysis_enhanced",
        script="portfolio_analysis_enhanced.py",
        category="portfolio_reports",
        name="Enhanced portfolio analysis",
        description="Deep risk analytics including VaR, Beta, and correlation.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_daily_brief",
        script="portfolio_daily_brief.py",
        category="briefing_cards",
        name="Daily brief",
        description="Compact portfolio card for mobile consumption.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_daily_brief_clean",
        script="portfolio_daily_brief_clean.py",
        category="briefing_cards",
        name="Daily brief (clean)",
        description="Noise-filtered wrapper around portfolio_daily_brief.py.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_daily_brief2",
        script="portfolio_daily_brief2.py",
        category="briefing_cards",
        name="Daily brief v2",
        description="Strict compact brief with catalyst radar and volatility context.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_daily_brief2_clean",
        script="portfolio_daily_brief2_clean.py",
        category="briefing_cards",
        name="Daily brief v2 (clean)",
        description="Noise-filtered wrapper around portfolio_daily_brief2.py.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_daily_brief_tg",
        script="portfolio_daily_brief_tg.py",
        category="briefing_cards",
        name="Daily brief Telegram",
        description="Telegram-friendly markdown card with hard layout constraints.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_daily_brief_tg_clean",
        script="portfolio_daily_brief_tg_clean.py",
        category="briefing_cards",
        name="Daily brief Telegram (clean)",
        description="Noise-filtered wrapper around portfolio_daily_brief_tg.py.",
    ),
    FinanceWorkflow(
        workflow_id="portfolio_alert_monitor",
        script="portfolio_alert_monitor.py",
        category="alerts_monitors",
        name="Portfolio alert monitor",
        description="Deduplicated alert monitor for RSI, PnL, concentration, and moves.",
    ),
    FinanceWorkflow(
        workflow_id="option_buyback_monitor",
        script="option_buyback_monitor.py",
        category="alerts_monitors",
        name="Option buyback monitor",
        description="State-aware option buyback trigger monitor.",
    ),
    FinanceWorkflow(
        workflow_id="realtime_quotes",
        script="realtime_quotes.py",
        category="market_intel",
        name="Realtime quotes",
        description="Broker-first quote fetch with Yahoo fallback.",
    ),
    FinanceWorkflow(
        workflow_id="earnings_calendar",
        script="earnings_calendar.py",
        category="market_intel",
        name="Earnings calendar",
        description="Upcoming earnings for current holdings.",
    ),
    FinanceWorkflow(
        workflow_id="market_news",
        script="market_news.py",
        category="market_intel",
        name="Market news",
        description="Holding-related market news with lightweight categorization.",
    ),
    FinanceWorkflow(
        workflow_id="longport_assets_summary",
        script="longport_assets_summary.py",
        category="broker_snapshots",
        name="Longport assets summary",
        description="Longport USD asset summary in JSON.",
    ),
    FinanceWorkflow(
        workflow_id="longport_assets_message",
        script="longport_assets_message.py",
        category="broker_snapshots",
        name="Longport assets message",
        description="One-line Longport account message.",
    ),
    FinanceWorkflow(
        workflow_id="moomoo_assets_message",
        script="moomoo_assets_message.py",
        category="broker_snapshots",
        name="Moomoo assets message",
        description="One-line moomoo account message.",
    ),
    FinanceWorkflow(
        workflow_id="dca_proposal_tg",
        script="dca_proposal_tg.py",
        category="strategy",
        name="DCA proposal (Telegram)",
        description="Budget-constrained DCA/add-position proposal card.",
    ),
    FinanceWorkflow(
        workflow_id="security_pin",
        script="security_pin.py",
        category="security",
        name="Security PIN helper",
        description="PBKDF2-backed local PIN setup and verification utility.",
    ),
)


WORKFLOW_MAP: dict[str, FinanceWorkflow] = {w.workflow_id: w for w in WORKFLOWS}


def category_choices() -> list[str]:
    """Return valid category choices."""
    return list(CATEGORY_LABELS.keys())


def workflow_ids() -> list[str]:
    """Return valid workflow identifiers."""
    return [w.workflow_id for w in WORKFLOWS]


def get_workflow(workflow_id: str) -> FinanceWorkflow:
    """Resolve a workflow id to a workflow object."""
    try:
        return WORKFLOW_MAP[workflow_id]
    except KeyError as exc:
        known = ", ".join(workflow_ids())
        raise ValueError(f"Unknown workflow: {workflow_id}. Known: {known}") from exc


def iter_workflows(category: str | None = None) -> list[FinanceWorkflow]:
    """List workflows, optionally filtered by category."""
    if category is None:
        return list(WORKFLOWS)
    return [w for w in WORKFLOWS if w.category == category]


def grouped_workflows(
    category: str | None = None,
) -> list[tuple[str, str, list[FinanceWorkflow]]]:
    """Return workflows grouped by category preserving display order."""
    grouped: list[tuple[str, str, list[FinanceWorkflow]]] = []
    for cat, label in CATEGORY_LABELS.items():
        if category is not None and category != cat:
            continue
        items = [w for w in WORKFLOWS if w.category == cat]
        if items:
            grouped.append((cat, label, items))
    return grouped
