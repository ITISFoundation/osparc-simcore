"""Transactional outbox events table.

Stores events atomically with the domain-entity update that produced them, so a
separate worker can reliably pick them up afterwards. This is a work queue, not
an event log: a successfully processed row is deleted, not retained.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata

outbox_events = sa.Table(
    "outbox_events",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        sa.Identity(start=1, cycle=False),
        primary_key=True,
        doc="Unique event identifier",
    ),
    sa.Column(
        "kind",
        sa.String,
        nullable=False,
        doc="Event type/handler key (e.g., comp_tasks.DB_OUTBOX_KIND_COMP_TASK_SYNC)",
    ),
    sa.Column(
        "aggregate_type",
        sa.String,
        nullable=False,
        doc="Domain entity type (e.g., 'comp_task')",
    ),
    sa.Column(
        "aggregate_id",
        sa.String,
        nullable=False,
        doc="Logical source entity ID encoded as text (e.g., task_id::text)",
    ),
    sa.Column(
        "changed_columns",
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
        doc="Source-entity column names that changed and triggered this event (e.g., ['outputs', 'state'])",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Column(
        "attempts",
        sa.Integer,
        nullable=False,
        server_default="0",
        doc="Number of processing attempts",
    ),
    sa.Column(
        "last_error",
        sa.Text,
        nullable=True,
        doc="Last error message if processing failed",
    ),
    # serves the claim query's "WHERE kind=... ORDER BY modified, id" (oldest-first):
    # kind is the only equality column, so it must come first for the index to provide
    # the ordering. The "attempts < N" filter is applied on top (dead-lettered rows are
    # rare here since successful events are deleted, so filtering them costs nothing)
    sa.Index("ix_outbox_events_claim", "kind", "modified", "id"),
)

register_modified_datetime_auto_update_trigger(outbox_events)
