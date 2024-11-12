""" resource_tracker_service_runs table
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_modified_datetime
from .base import metadata

resource_tracker_project_metadata = sa.Table(
    "resource_tracker_project_metadata",
    metadata,
    sa.Column(
        "project_id",  # UUID
        sa.String,
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        "project_name",
        sa.String,
        nullable=False,
        doc="we want to store the project name for tracking/billing purposes and be sure it stays there even when the project is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "project_tags",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="we want to store the project tags for tracking/billing purposes and be sure it stays there even when the project is deleted (that's also reason why we do not introduce foreign key)",
    ),
    column_modified_datetime(timezone=True),
)
