""" Pricing details table
    - each pricing plan table can have multiple units. These units are stored in the
    pricing details table with their unit cost. Each unit cost (row in this table) has
    id which uniquely defines the prices at this point of the time. We always store whole
    history and do not update the rows of this table.
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata

resource_tracker_pricing_units = sa.Table(
    "resource_tracker_pricing_units",
    metadata,
    sa.Column(
        "pricing_unit_id",
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
            name="fk_resource_tracker_pricing_units_pricing_plan_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Foreign key to pricing plan",
        index=True,
    ),
    sa.Column(
        "unit_name",
        sa.String,
        nullable=False,
        doc="The custom name of the pricing plan, ex. SMALL, MEDIUM, LARGE",
    ),
    sa.Column(
        "unit_extra_info",
        JSONB,
        nullable=False,
        default="'{}'::jsonb",
        doc="Additional public information about pricing unit, ex. more detail description or how many CPUs there are.",
    ),
    sa.Column(
        "default",
        sa.Boolean(),
        nullable=False,
        default=False,
        doc="Option to mark default pricing plan by creator",
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
    sa.UniqueConstraint(
        "pricing_plan_id",
        "unit_name",
        name="pricing_plan_and_unit_constrain_key",
    ),
)
