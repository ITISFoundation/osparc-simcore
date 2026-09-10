"""Transactional Outbox Events Table

Outbox pattern for event sourcing. Events written here are guaranteed to be captured
within the same transaction as the domain entity update, enabling reliable event
distribution to subscribers.
"""

import sqlalchemy as sa

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
        doc="Event type/handler key (e.g., 'comp_task.sync.v1')",
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
    # Indexes for worker queries
    sa.Index("ix_outbox_events_kind", "kind"),
)

register_modified_datetime_auto_update_trigger(outbox_events)
