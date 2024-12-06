""" resource_tracker_service_runs table
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._common import RefActions, column_modified_datetime
from .base import metadata

resource_tracker_licensed_items_usage = sa.Table(
    "resource_tracker_licensed_items_usage",
    metadata,
    sa.Column(
        "licensed_item_usage_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column(
        "licensed_item_id",
        sa.String,
        nullable=True,
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
        index=True,
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        nullable=False,
    ),
    sa.Column(
        "user_email",
        sa.String,
        nullable=True,
    ),
    sa.Column("product_name", sa.String, nullable=False, doc="Product name"),
    sa.Column(
        "service_run_id",
        sa.String,
        nullable=True,
    ),
    sa.Column(
        "started_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when the service was started",
    ),
    sa.Column(
        "stopped_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the service was stopped",
    ),
    sa.Column(
        "num_of_seats",
        sa.SmallInteger,
        nullable=False,
    ),
    column_modified_datetime(timezone=True),
    # ---------------------------
    sa.ForeignKeyConstraint(
        ["product_name", "service_run_id"],
        [
            "resource_tracker_service_runs.product_name",
            "resource_tracker_service_runs.service_run_id",
        ],
        name="resource_tracker_license_checkouts_service_run_id_fkey",
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.RESTRICT,
    ),
)
