"""Snapshot test for registered workflow signatures.

If this test fails, run ``make workflows-signatures`` in the service root
to regenerate ``workflows_signatures.json``, then flag the PR for OPS
to shut down Temporal workflows before deploying.
"""

from pathlib import Path

from simcore_service_dynamic_scheduler.services.workflows._snapshot import (
    compute_workflows_signatures,
)


def test_registered_workflows_snapshot(project_slug_dir: Path):
    snapshot_path = project_slug_dir / "workflows_signatures.json"

    assert snapshot_path.exists(), (
        f"{snapshot_path.name} not found. Run `make workflows-signatures` in the service root to generate it."
    )

    expected = compute_workflows_signatures()
    actual = snapshot_path.read_text()

    assert actual == expected, (
        "Workflow signatures changed! "
        "Run `make workflows-signatures` in the service root, "
        "then flag this PR for OPS to shut down Temporalio workflows before deploying."
    )
