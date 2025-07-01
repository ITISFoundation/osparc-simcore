"""Computational Runs Table"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

comp_run_collections = sa.Table(
    "comp_run_collections",
    metadata,
    sa.Column(
        "collection_run_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        "client_or_system_generated_id",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "client_or_system_generated_display_name",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "generated_by_system",
        sa.Boolean,
        nullable=False,
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Index(
        "ix_comp_run_collections_client_or_system_generated_id",
        "client_or_system_generated_id",
    ),
)
