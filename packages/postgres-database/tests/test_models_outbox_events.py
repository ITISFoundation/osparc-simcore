# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""outbox_events must be reachable through the package's metadata facade: consumers
that create tables from `metadata` (utils.create_tables, alembic autogenerate) only
see what webserver_models/storage_models import."""

import sqlalchemy as sa
from simcore_postgres_database import webserver_models
from simcore_postgres_database.models.base import metadata


def test_outbox_events_registered_in_metadata():
    assert "outbox_events" in metadata.tables
    assert webserver_models.outbox_events is metadata.tables["outbox_events"]


def test_outbox_events_claim_index_matches_claim_query_ordering():
    table = metadata.tables["outbox_events"]
    index = next(ix for ix in table.indexes if ix.name == "ix_outbox_events_claim")
    assert isinstance(index, sa.Index)
    # kind is the claim query's only equality column: it must come first so the index
    # can also provide the "ORDER BY modified, id" without a sort step
    assert [c.name for c in index.columns] == ["kind", "modified", "id"]


def test_outbox_events_has_retry_backoff_column():
    table = metadata.tables["outbox_events"]
    column = table.c.next_attempt_at
    # claims gate on it ("not claimable until"), so it must never be NULL and fresh
    # events must be immediately claimable
    assert not column.nullable
    assert column.server_default is not None
    assert isinstance(column.type, sa.DateTime)
    assert column.type.timezone
