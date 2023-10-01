""" Pricing details table
    - each pricing plan table can have multiple units. These units are stored in the
    pricing details table with their unit cost. Each unit cost (row in this table) has
    id which uniquely defines the prices at this point of the time. We always store whole
    history and do not update the rows of this table.
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import NUMERIC_KWARGS, column_created_datetime, column_modified_datetime
from .base import metadata

resource_tracker_pricing_unit_costs = sa.Table(
    "resource_tracker_pricing_unit_costs",
    metadata,
    sa.Column(
        "pricing_unit_cost_id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Identifier index",
    ),
    sa.Column(
        "pricing_plan_id",
        sa.BigInteger,
        nullable=False,
        doc="Parent pricing plan",
        index=True,
    ),
    sa.Column(
        "pricing_plan_key",
        sa.String,
        nullable=False,
        doc="Parent pricing key (storing for historical reasons)",
    ),
    sa.Column(
        "pricing_unit_id",
        sa.BigInteger,
        nullable=False,
        doc="Parent pricing unit",
        index=True,
    ),
    sa.Column(
        "pricing_unit_name",
        sa.String,
        nullable=False,
        doc="Parent pricing unit name (storing for historical reasons)",
    ),
    sa.Column(
        "cost_per_unit",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
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
    sa.Column(
        "comment",
        sa.String,
        nullable=True,
        doc="Option to store comment",
    ),
    column_modified_datetime(timezone=True),
    # sa.Column(
    #     "version",
    #     sa.Integer,
    #     nullable=False,
    #     doc="Version of specific pricing unit in the pricing plan (ex. In case of change in cost_per_unit, the version is increased)",
    # ),
    # ---------------------------
    # sa.UniqueConstraint(
    #     "pricing_plan_id",
    #     "unit_name",
    #     "version",
    #     name="pricing_details_unit_constrain_key",
    # ),
)
