# pylint: disable=redefined-outer-name
"""The head migration that creates the outbox duplicates some constants from
models/comp_tasks.py (migrations must stay self-contained snapshots). These
tests pin the two copies together so they cannot drift apart silently.
"""

import importlib.util
from pathlib import Path

import pytest
import simcore_postgres_database
from simcore_postgres_database.models.comp_tasks import (
    DB_CHANNEL_NAME,
    DB_OUTBOX_KIND_COMP_TASK_SYNC,
    DB_PROCEDURE_NAME,
    DB_TRIGGER_NAME,
)

_MIGRATION_STEM = "966758d7226c_add_outbox_events_table"


@pytest.fixture(scope="module")
def outbox_migration():
    """Import the outbox migration module from its file (migrations are not an importable package)"""
    versions_dir = Path(simcore_postgres_database.__file__).parent / "migration" / "versions"
    path = next(versions_dir.glob(f"{_MIGRATION_STEM}*.py"))
    spec = importlib.util.spec_from_file_location(_MIGRATION_STEM, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_constants_match_model(outbox_migration):
    assert outbox_migration.DB_PROCEDURE_NAME == DB_PROCEDURE_NAME
    assert outbox_migration.DB_TRIGGER_NAME == DB_TRIGGER_NAME
    assert outbox_migration.DB_CHANNEL_NAME == DB_CHANNEL_NAME
    assert outbox_migration.DB_OUTBOX_KIND_COMP_TASK_SYNC == DB_OUTBOX_KIND_COMP_TASK_SYNC
