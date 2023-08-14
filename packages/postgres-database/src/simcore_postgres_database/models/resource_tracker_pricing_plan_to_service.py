""" Pricing plan to credits table
  - Usecase: when client wants to ask for pricing plan for a concrete service
"""

import sqlalchemy as sa

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

resource_tracker_pricing_plan_to_service = sa.Table(
    "resource_tracker_pricing_plan_to_service",
    metadata,
    sa.Column(
        "pricing_plan_id",
        sa.BigInteger,
        sa.ForeignKey(
            "resource_tracker_pricing_plans.pricing_plan_id",
            name="fk_resource_tracker_pricing_details_pricing_plan_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
        doc="Identifier index",
        index=True,
    ),
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Hierarchical identifier of the service e.g. simcore/services/dynamic/my-super-service",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="MAJOR.MINOR.PATCH semantic versioning (see https://semver.org)",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # ---------------------------
    sa.UniqueConstraint(
        "service_key",
        "service_version",
        name="resource_tracker_pricing_plan_to_service__service_unique_key",
    ),
)
