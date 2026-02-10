"""Runner utilities for migrated legacy finance workflows."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .workflows import get_workflow


@dataclass(frozen=True)
class FinanceWorkspaceInit:
    """Result metadata for finance workspace bootstrap."""

    workspace: Path
    scripts_synced: int
    archive_synced: int
    config_created: bool
    data_created: bool


def default_workspace_path() -> Path:
    """Default mutable workspace for migrated scripts."""
    return Path.home() / ".clawdfolio" / "finance"


def package_legacy_root() -> Path:
    """Return bundled legacy finance root inside the package."""
    return Path(__file__).resolve().parent.parent / "legacy_finance"


def _sync_tree(source: Path, target: Path, *, sync: bool) -> int:
    """Copy source tree to target, preserving user files unless sync=True."""
    copied = 0
    if not source.exists():
        return copied

    for src in source.rglob("*"):
        if src.is_dir():
            continue

        rel = src.relative_to(source)
        if "__pycache__" in rel.parts or src.suffix == ".pyc":
            continue

        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if sync or not dst.exists():
            shutil.copy2(src, dst)
            copied += 1

    return copied


def initialize_workspace(
    workspace: str | Path | None = None,
    *,
    sync: bool = False,
    source_root: str | Path | None = None,
) -> FinanceWorkspaceInit:
    """Initialize mutable workspace used to run legacy workflows."""
    root = Path(workspace).expanduser() if workspace else default_workspace_path()
    root.mkdir(parents=True, exist_ok=True)

    source = Path(source_root).expanduser() if source_root else package_legacy_root()
    scripts_source = source / "scripts"
    archive_source = source / "archive_scripts"
    if not scripts_source.exists():
        raise FileNotFoundError(f"Missing bundled scripts directory: {scripts_source}")

    scripts_target = root / "scripts"
    archive_target = root / "archive_scripts"

    scripts_synced = _sync_tree(scripts_source, scripts_target, sync=sync)
    archive_synced = _sync_tree(archive_source, archive_target, sync=sync)

    config_created = False
    config_example = scripts_target / "config.example.json"
    config_file = scripts_target / "config.json"
    if config_example.exists() and not config_file.exists():
        shutil.copy2(config_example, config_file)
        config_created = True

    data_dir = scripts_target / "data"
    data_created = False
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        data_created = True

    return FinanceWorkspaceInit(
        workspace=root,
        scripts_synced=scripts_synced,
        archive_synced=archive_synced,
        config_created=config_created,
        data_created=data_created,
    )


def run_workflow(
    workflow_id: str,
    *,
    script_args: Sequence[str] | None = None,
    workspace: str | Path | None = None,
    sync: bool = False,
    source_root: str | Path | None = None,
    python_bin: str | None = None,
) -> int:
    """Run a workflow by id and stream output to current terminal."""
    workflow = get_workflow(workflow_id)
    init_result = initialize_workspace(workspace, sync=sync, source_root=source_root)

    script_rel = Path("scripts") / workflow.script
    script_path = init_result.workspace / script_rel
    if not script_path.exists():
        raise FileNotFoundError(
            f"Workflow script not found in workspace: {script_path}"
        )

    cmd = [python_bin or sys.executable, str(script_rel)]
    if script_args:
        cmd.extend(script_args)

    completed = subprocess.run(
        cmd,
        cwd=init_result.workspace,
        check=False,
    )
    return int(completed.returncode)
