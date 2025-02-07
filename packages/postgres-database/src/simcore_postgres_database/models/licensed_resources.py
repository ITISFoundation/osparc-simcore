""" resource_tracker_service_runs table
"""


import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    column_trashed_datetime,
)
from .base import metadata
from .licenses import LicensedResourceType

licensed_resources = sa.Table(
    "licensed_resources",
    metadata,
    sa.Column(
        "licensed_resource_id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column(
        "display_name",
        sa.String,
        nullable=False,
        doc="Display name for front-end",
    ),
    sa.Column(
        "licensed_resource_name",
        sa.String,
        nullable=False,
        doc="Resource name identifier",
    ),
    sa.Column(
        "licensed_resource_type",
        sa.Enum(LicensedResourceType),
        nullable=False,
        doc="Resource type, ex. VIP_MODEL",
    ),
    sa.Column(
        "licensed_resource_data",
        postgresql.JSONB,
        nullable=True,
        doc="Resource metadata. Used for read-only purposes",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    column_trashed_datetime("licensed_item"),
    sa.UniqueConstraint(
        "licensed_resource_name",
        "licensed_resource_type",
        name="uq_licensed_resource_name_type2",
    ),
)
