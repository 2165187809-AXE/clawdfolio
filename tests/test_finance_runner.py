"""Tests for finance workflow catalog and workspace runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clawdfolio.finance.runner import initialize_workspace, run_workflow
from clawdfolio.finance.workflows import get_workflow, workflow_ids


def _make_fake_source(tmp_path: Path) -> Path:
    source = tmp_path / "legacy_finance_source"
    scripts = source / "scripts"
    archive = source / "archive_scripts"
    (scripts / "lib").mkdir(parents=True)
    archive.mkdir(parents=True)

    (scripts / "config.example.json").write_text('{"demo": true}\n', encoding="utf-8")
    (archive / "old.py").write_text("print('archive')\n", encoding="utf-8")
    (scripts / "account_report.py").write_text(
        (
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            "base = Path(__file__).resolve().parent / 'data'\n"
            "base.mkdir(parents=True, exist_ok=True)\n"
            "(base / 'run.json').write_text("
            "json.dumps({'argv': sys.argv[1:]}), encoding='utf-8')\n"
            "print('ok')\n"
        ),
        encoding="utf-8",
    )
    return source


def test_workflow_catalog_has_expected_entries():
    ids = workflow_ids()
    assert len(ids) == 20
    assert len(ids) == len(set(ids))

    wf = get_workflow("portfolio_daily_brief_tg")
    assert wf.script == "portfolio_daily_brief_tg.py"


def test_initialize_workspace_bootstraps_files(tmp_path):
    source = _make_fake_source(tmp_path)
    workspace = tmp_path / "workspace"

    result = initialize_workspace(workspace=workspace, source_root=source)

    assert result.workspace == workspace
    assert result.scripts_synced >= 2
    assert result.archive_synced >= 1
    assert result.config_created is True
    assert result.data_created is True
    assert (workspace / "scripts" / "config.json").exists()
    assert (workspace / "archive_scripts" / "old.py").exists()


def test_run_workflow_executes_script_with_args(tmp_path):
    source = _make_fake_source(tmp_path)
    workspace = tmp_path / "workspace"

    rc = run_workflow(
        "account_report",
        workspace=workspace,
        source_root=source,
        script_args=["--foo", "bar"],
    )

    assert rc == 0
    payload = json.loads(
        (workspace / "scripts" / "data" / "run.json").read_text(encoding="utf-8")
    )
    assert payload["argv"] == ["--foo", "bar"]


def test_run_workflow_rejects_unknown_id(tmp_path):
    source = _make_fake_source(tmp_path)
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError):
        run_workflow(
            "unknown_workflow",
            workspace=workspace,
            source_root=source,
        )
