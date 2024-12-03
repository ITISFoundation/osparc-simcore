""" resource_tracker_service_runs table
"""

import shortuuid
import sqlalchemy as sa

from ._common import RefActions, column_modified_datetime
from .base import metadata


def _custom_id_generator():
    return f"rlc_{shortuuid.uuid()}"


resource_tracker_license_checkouts = sa.Table(
    "resource_tracker_license_checkouts",
    metadata,
    sa.Column(
        "license_checkout_id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        default=_custom_id_generator,
    ),
    sa.Column(
        "license_package_id",
        sa.BigInteger,
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
        sa.ForeignKey(
            "resource_tracker_service_runs.service_run_id",
            name="fk_resource_tracker_license_checkouts_service_run_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
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
)

# We define the partial index
# sa.Index(
#     "ix_resource_tracker_credit_transactions_status_running",
#     resource_tracker_service_runs.c.service_run_status,
#     postgresql_where=(
#         resource_tracker_service_runs.c.service_run_status
#         == ResourceTrackerServiceRunStatus.RUNNING
#     ),
# )
