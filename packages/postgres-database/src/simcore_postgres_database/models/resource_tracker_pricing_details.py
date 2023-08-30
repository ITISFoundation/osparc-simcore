""" Pricing details table
    - each pricing plan table can have multiple units. These units are stored in the
    pricing details table with their unit cost. Each unit cost (row in this table) has
    id which uniquely defines the prices at this point of the time. We always store whole
    history and do not update the rows of this table.
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

resource_tracker_pricing_details = sa.Table(
    "resource_tracker_pricing_details",
    metadata,
    sa.Column(
        "pricing_detail_id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Identifier index",
    ),
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
        doc="Foreign key to pricing plan",
        index=True,
    ),
    sa.Column(
        "unit_name",
        sa.String,
        nullable=False,
        doc="The custom name of the pricing plan, ex. DYNAMIC_SERVICES_TIERS, COMPUTATIONAL_SERVICES_TIERS, CPU_HOURS, STORAGE",
    ),
    sa.Column(
        "cost_per_unit",
        sa.Numeric(precision=15, scale=2),
        nullable=True,
        doc="The cost per unit of the pricing plan in credits.",
    ),
    sa.Column(
        "valid_from",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="From when the pricing unit is active",
    ),
    sa.Column(
        "valid_to",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="To when the pricing unit was active, if null it is still active",
        index=True,
    ),
    sa.Column(
        "specific_info",
        JSONB,
        nullable=False,
        default="'{}'::jsonb",
        doc="Specific internal info of the pricing unit, ex. for tiers we can store in which EC2 instance type we run the service.",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # ---------------------------
)
